from fastapi import Depends, FastAPI
from fastapi import HTTPException
from fastapi import Header
from fastapi import Request, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
import uvicorn
import time
import os
import hmac
import hashlib
import base64
import json
import secrets
import requests
from typing import Optional, List, Dict, Any
import dotenv

dotenv.load_dotenv()

from augmentation_contract import (
    build_porting_augmentation_contract,
    compare_porting_analysis_with_augmentation,
    validate_porting_augmentation,
)
from basic_logs import (
    INGESTION_LOG_FILE,
    REQUEST_LOG_FILE,
    write_request_log,
)
from ingestion.incremental_utils import INGESTION_STATS_PATH
from feedback_store import record_feedback, index_conversation_turn
from conversation_store import (
    start_conversation,
    append_turn,
    get_conversation,
    export_conversations,
)
from feedback_models import FeedbackPayload
from skill_registry import (
    SKILL_ID_PORTING_AUDITOR,
    SKILL_ID_RESEARCH,
    SKILL_ID_CODE_HELPER,
    get_skill,
    list_skills,
    run_skill_search,
)

app = FastAPI()
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
ADMIN_TOKEN_ENV_KEY = "ADMIN_BEARER_TOKEN"
ADMIN_HASHED_PASSWORD_ENV_KEY = "ADMIN_HASHED_PASSWORD"
ADMIN_TOKEN_TTL_SECONDS = int(os.getenv("ADMIN_TOKEN_TTL_SECONDS", "3600"))

DEFAULT_AGENT_GUIDANCE = {
    "behavior": "references_first",
    "code_generation": "disallowed",
    "instructions": [
        "Do not write or synthesize contract/application code.",
        "Return references, tools, and links first.",
        "When possible, point to exact repos/docs/pages for implementation details.",
        "If retrieval context is insufficient, say so explicitly instead of guessing.",
    ],
}

SESSION_HEADER = "X-Session-Id"


def parse_cors_origins() -> list:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _admin_token() -> str:
    return os.getenv(ADMIN_TOKEN_ENV_KEY, "").strip()


def _admin_hashed_password() -> str:
    return os.getenv(ADMIN_HASHED_PASSWORD_ENV_KEY, "").strip()


def hash_password(password: str) -> str:
    """Hash a password using SHA256; used for comparison with env-stored hash."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def issue_bearer_token() -> str:
    now = int(time.time())
    exp = now + ADMIN_TOKEN_TTL_SECONDS
    payload = {"exp": exp, "iat": now, "nonce": secrets.token_urlsafe(10)}
    payload_json = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(_admin_token().encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii") + "." + base64.urlsafe_b64encode(signature).decode("ascii")
    return token


def validate_bearer_token(token: str):
    try:
        raw_payload, raw_sig = token.split(".", 1)
        payload_json = base64.urlsafe_b64decode(raw_payload.encode("ascii")).decode("utf-8")
        payload = json.loads(payload_json)
        signature = base64.urlsafe_b64decode(raw_sig.encode("ascii"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid bearer token format.")

    expected_sig = hmac.new(_admin_token().encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid bearer token signature.")

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise HTTPException(status_code=401, detail="Bearer token has expired.")

    return True


def require_admin_token(authorization: str = Header(default="")):
    secret = _admin_token()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail=f"{ADMIN_TOKEN_ENV_KEY} is not configured on the backend.",
        )

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must use Bearer scheme.")

    provided = authorization.split(" ", 1)[1].strip()
    if not provided:
        raise HTTPException(status_code=401, detail="Invalid bearer token.")

    validate_bearer_token(provided)
    return True


LOG_SOURCES = {
    "request": REQUEST_LOG_FILE,
    "ingestion": INGESTION_LOG_FILE,
    "stats": INGESTION_STATS_PATH,
}


def resolve_log_path(source: str) -> str:
    path = LOG_SOURCES.get(source)
    if not path:
        raise HTTPException(status_code=400, detail="Unsupported log source. Use 'request' or 'ingestion'.")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Log file for '{source}' does not exist yet.")
    return path


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StylusRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class SkillSearchRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    augmentation: Optional[object] = None


class PortingStylusRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    augmentation: object


class PortingAugmentationValidationRequest(BaseModel):
    augmentation: object


class PortingAugmentationCompareRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    augmentation: object


class ConversationStartRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, max_length=200)
    metadata: Optional[Dict[str, Any]] = None


class ConversationStartResponse(BaseModel):
    session_id: str


class ConversationTurnRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    response: str = Field(min_length=1, max_length=10000)
    rating: Optional[int] = Field(default=None, description="one of {-1,0,1}")
    skill: Optional[str] = Field(default=None, max_length=200)
    metadata: Optional[Dict[str, Any]] = None


class ConversationTurnResponse(BaseModel):
    turn_id: str


class ConversationTurn(BaseModel):
    turn_id: str
    prompt: str
    response: str
    timestamp: Optional[int] = None
    rating: Optional[int] = None
    skill: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    session_id: str
    started_at: Optional[int] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    turns: List[ConversationTurn] = Field(default_factory=list)


class RatedTurnExport(BaseModel):
    session_id: str
    turn_id: str
    prompt: str
    response: str
    rating: int
    skill: Optional[str] = None
    timestamp: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationExportResponse(BaseModel):
    turns: List[RatedTurnExport]
class FeedbackResponse(BaseModel):
    feedback_id: str
    stored: bool


def prompt_preview(value: str, max_chars: int = 180) -> str:
    return (value or "").replace("\n", " ").strip()[:max_chars]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/skills")
def skills_index():
    return {"skills": list_skills()}


def execute_skill_search(skill_id: str, prompt: str, augmentation: object = None, session_id: Optional[str] = None):
    preview = prompt_preview(prompt)
    write_request_log(f"User started a skill request | skill={skill_id} | Prompt preview: {preview}")
    start_time = time.time()

    try:
        if augmentation is None:
            result = run_skill_search(skill_id, prompt, session_id=session_id)
        else:
            result = run_skill_search(skill_id, prompt, augmentation, session_id=session_id)
    except Exception as exc:
        write_request_log(f"[error] Skill retrieval failed | skill={skill_id} | {type(exc).__name__}: {exc}")
        result = {
            "found": False,
            "context": "",
            "reason": "Retrieval failed due to an internal error.",
            "agent_guidance": DEFAULT_AGENT_GUIDANCE,
            "references": [],
            "skill": skill_id,
        }

    duration = round(time.time() - start_time, 2)
    preview = (result.get("context") or result.get("reason") or "")[:80]
    write_request_log(f"✅ Finished skill retrieval | skill={skill_id} | Time: {duration}s | Preview: {preview}...")

    # Return retrieval payload (MCP/IDE/LLM will decide what to do with it)
    return result

def _ensure_session_and_log_turn(
    *,
    request: Request,
    response: Response,
    skill_id: str,
    prompt: str,
    result: dict,
):
    """Append a turn to the conversation log for a known session."""

    try:
        append_turn(
            session_id=request.state.session_id,
            prompt=prompt,
            response=json.dumps(result, ensure_ascii=False)[:10000],
            rating=None,
            skill=skill_id,
            metadata={"path": request.url.path},
        )
    except Exception as exc:  # best-effort; do not break primary flow
        write_request_log(f"[warn] Failed to append conversation turn | session={request.state.session_id} | {type(exc).__name__}: {exc}")


def _get_or_create_session(request: Request, response: Response) -> str:
    session_id = request.headers.get(SESSION_HEADER, "").strip()
    if not session_id:
        session_id = start_conversation()
        response.headers[SESSION_HEADER] = session_id
    request.state.session_id = session_id
    return session_id


@app.post("/skills/{skill_id}/search")
def skill_search(skill_id: str, request: SkillSearchRequest, raw_request: Request, raw_response: Response):
    if not get_skill(skill_id):
        raise HTTPException(status_code=404, detail=f"Unsupported skill '{skill_id}'.")
    if skill_id == SKILL_ID_PORTING_AUDITOR and request.augmentation is None:
        raise HTTPException(
            status_code=422,
            detail="Porting skill requires an 'augmentation' payload object.",
        )
    session_id = _get_or_create_session(raw_request, raw_response)
    result = execute_skill_search(skill_id, request.prompt, request.augmentation, session_id=session_id)
    _ensure_session_and_log_turn(
        request=raw_request,
        response=raw_response,
        skill_id=skill_id,
        prompt=request.prompt,
        result=result,
    )
    return result


@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest, raw_request: Request, raw_response: Response):
    session_id = _get_or_create_session(raw_request, raw_response)
    result = execute_skill_search(SKILL_ID_RESEARCH, request.prompt, session_id=session_id)
    _ensure_session_and_log_turn(
        request=raw_request,
        response=raw_response,
        skill_id=SKILL_ID_RESEARCH,
        prompt=request.prompt,
        result=result,
    )
    return result


@app.post("/stylus-porting-audit")
def stylus_porting_audit(request: PortingStylusRequest, raw_request: Request, raw_response: Response):
    session_id = _get_or_create_session(raw_request, raw_response)
    result = execute_skill_search(SKILL_ID_PORTING_AUDITOR, request.prompt, request.augmentation, session_id=session_id)
    _ensure_session_and_log_turn(
        request=raw_request,
        response=raw_response,
        skill_id=SKILL_ID_PORTING_AUDITOR,
        prompt=request.prompt,
        result=result,
    )
    return result

@app.post("/stylus-code-help")
def stylus_code_help(request: StylusRequest, raw_request: Request, raw_response: Response):
    session_id = _get_or_create_session(raw_request, raw_response)
    result = execute_skill_search(SKILL_ID_CODE_HELPER, request.prompt, session_id=session_id)
    _ensure_session_and_log_turn(
        request=raw_request,
        response=raw_response,
        skill_id=SKILL_ID_CODE_HELPER,
        prompt=request.prompt,
        result=result,
    )
    return result

@app.post("/conversations/start", response_model=ConversationStartResponse)
def conversations_start(request: ConversationStartRequest):
    session_id = start_conversation(user_id=request.user_id, metadata=request.metadata)
    return ConversationStartResponse(session_id=session_id)


@app.post("/conversations/{session_id}/turn", response_model=ConversationTurnResponse)
def conversations_append_turn(session_id: str, request: ConversationTurnRequest):
    try:
        turn_id = append_turn(
            session_id=session_id,
            prompt=request.prompt,
            response=request.response,
            rating=request.rating,
            skill=request.skill,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if request.rating is not None and request.rating > 0:
        index_conversation_turn(
            session_id=session_id,
            turn_id=turn_id,
            prompt=request.prompt,
            response=request.response,
            rating=request.rating,
            skill=request.skill,
            metadata=request.metadata or {},
        )
    return ConversationTurnResponse(turn_id=turn_id)


@app.get("/conversations/{session_id}", response_model=ConversationResponse)
def conversations_get(session_id: str):
    convo = get_conversation(session_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    # pydantic will coerce dict into ConversationResponse
    return convo


# Admin export of rated answers for retraining
@app.get("/admin/conversations/export", response_model=ConversationExportResponse)
def conversations_export(
    min_rating: Optional[int] = None,
    since_timestamp: Optional[int] = None,
    max_turns: int = 500,
    _=Depends(require_admin_token),
):
    try:
        turns = export_conversations(
            min_rating=min_rating,
            since_timestamp=since_timestamp,
            max_turns=max_turns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"turns": turns}


@app.post("/skills/sift-stylus-porting-auditor/validate-augmentation")
def validate_porting_augmentation_endpoint(request: PortingAugmentationValidationRequest):
    contract = build_porting_augmentation_contract()
    validated = validate_porting_augmentation(request.augmentation, contract=contract)
    return {
        "skill": SKILL_ID_PORTING_AUDITOR,
        "llm_augmentation_contract": contract,
        "llm_augmentation": validated,
    }


@app.post("/skills/sift-stylus-porting-auditor/compare-augmentation")
def compare_porting_augmentation_endpoint(request: PortingAugmentationCompareRequest):
    base_payload = run_skill_search(SKILL_ID_PORTING_AUDITOR, request.prompt)
    analysis = base_payload.get("codebase_analysis") if isinstance(base_payload, dict) else None

    contract = build_porting_augmentation_contract()
    validated = validate_porting_augmentation(request.augmentation, contract=contract)
    comparison = compare_porting_analysis_with_augmentation(
        analysis,
        validated,
        contract=contract,
    )
    return {
        "skill": SKILL_ID_PORTING_AUDITOR,
        "codebase_analysis": analysis,
        "llm_augmentation_contract": contract,
        "llm_augmentation": validated,
        "augmentation_comparison": comparison,
    }


# ------------------------------------
# Admin-protected log proxy endpoints
# ------------------------------------


def stream_file_lines(file_path: str, chunk_size: int = 1024):
    """Generator that streams a file in small chunks to avoid loading into memory."""
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


@app.get("/admin/logs/{source}/paginate")
def get_logs_paginated(
    source: str,
    offset: int = 0,
    limit: int = 5000,
    _=Depends(require_admin_token),
):
    """Return a slice of the log file as text for simple pagination."""
    path = resolve_log_path(source)

    if offset < 0 or limit <= 0:
        raise HTTPException(status_code=400, detail="offset must be >=0 and limit must be >0")

    try:
        with open(path, "r", encoding="utf-8") as f:
            f.seek(offset)
            data = f.read(limit)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {exc}") from exc

    next_offset = offset + len(data)
    return {
        "source": source,
        "offset": offset,
        "next_offset": next_offset,
        "has_more": len(data) == limit,
        "data": data,
    }


@app.get("/admin/logs/{source}/stream")
def stream_logs(source: str, _=Depends(require_admin_token)):
    """Stream the entire log file in small chunks."""
    path = resolve_log_path(source)
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    return StreamingResponse(stream_file_lines(path), headers=headers)


@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackPayload):
    """Accepts thumbs up/down feedback for a prompt/response pair."""

    feedback_id = record_feedback(
        prompt=payload.prompt,
        response=payload.response,
        rating=payload.rating,
        skill=payload.skill,
        metadata=payload.metadata,
    )
    # We always log; storage to Chroma is best-effort, so we return stored=True when rating>0.
    stored = payload.rating > 0
    return FeedbackResponse(feedback_id=feedback_id, stored=stored)


class AdminAuthRequest(BaseModel):
    password: str = Field(min_length=1)


class AdminAuthResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int = ADMIN_TOKEN_TTL_SECONDS


@app.post("/admin/auth", response_model=AdminAuthResponse)
def admin_auth(request: AdminAuthRequest):
    configured_hash = _admin_hashed_password()
    bearer_secret = _admin_token()

    if not configured_hash:
        raise HTTPException(status_code=503, detail=f"{ADMIN_HASHED_PASSWORD_ENV_KEY} is not configured on the backend.")
    if not bearer_secret:
        raise HTTPException(status_code=503, detail=f"{ADMIN_TOKEN_ENV_KEY} is not configured on the backend.")

    provided_hash = hash_password(request.password)
    if not hmac.compare_digest(provided_hash, configured_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    token = issue_bearer_token()
    return AdminAuthResponse(token=token)


@app.post("/openrouter/chat/completions")
def openrouter_chat_completions(payload: dict):
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is not configured on the backend.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object.")

    proxy_payload = dict(payload)
    proxy_payload["stream"] = False

    try:
        upstream = requests.post(
            OPENROUTER_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=proxy_payload,
            timeout=45,
        )
    except requests.RequestException as exc:
        write_request_log(f"[error] OpenRouter proxy request failed | {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail="OpenRouter proxy request failed.") from exc

    content_type = upstream.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return JSONResponse(status_code=upstream.status_code, content=upstream.json())
        except ValueError:
            return PlainTextResponse(status_code=upstream.status_code, content=upstream.text)
    return PlainTextResponse(status_code=upstream.status_code, content=upstream.text)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host=host, port=port)
