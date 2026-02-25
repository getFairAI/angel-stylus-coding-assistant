from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn
import time
import os
import requests

from augmentation_contract import (
    build_porting_augmentation_contract,
    compare_porting_analysis_with_augmentation,
    validate_porting_augmentation,
)
from basic_logs import write_request_log
from skill_registry import (
    SKILL_ID_PORTING_AUDITOR,
    SKILL_ID_RESEARCH,
    get_skill,
    list_skills,
    run_skill_search,
)

app = FastAPI()
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

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


def parse_cors_origins() -> list:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StylusRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class PortingAugmentationValidationRequest(BaseModel):
    augmentation: object


class PortingAugmentationCompareRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    augmentation: object


def prompt_preview(value: str, max_chars: int = 180) -> str:
    return (value or "").replace("\n", " ").strip()[:max_chars]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/skills")
def skills_index():
    return {"skills": list_skills()}


def execute_skill_search(skill_id: str, request: StylusRequest):
    preview = prompt_preview(request.prompt)
    write_request_log(f"User started a skill request | skill={skill_id} | Prompt preview: {preview}")
    start_time = time.time()

    try:
        result = run_skill_search(skill_id, request.prompt)
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


@app.post("/skills/{skill_id}/search")
def skill_search(skill_id: str, request: StylusRequest):
    if not get_skill(skill_id):
        raise HTTPException(status_code=404, detail=f"Unsupported skill '{skill_id}'.")
    return execute_skill_search(skill_id, request)


@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest):
    return execute_skill_search(SKILL_ID_RESEARCH, request)


@app.post("/stylus-porting-audit")
def stylus_porting_audit(request: StylusRequest):
    return execute_skill_search(SKILL_ID_PORTING_AUDITOR, request)


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
