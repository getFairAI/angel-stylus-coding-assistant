from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
import os

from retrieve_chroma_docs import retrieve_stylus_context
from basic_logs import write_request_log

app = FastAPI()

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


def prompt_preview(value: str, max_chars: int = 180) -> str:
    return (value or "").replace("\n", " ").strip()[:max_chars]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/stylus-chat")
def stylus_chat(request: StylusRequest):
    preview = prompt_preview(request.prompt)
    write_request_log(f"User started a request | Prompt preview: {preview}")
    start_time = time.time()

    try:
        result = retrieve_stylus_context(request.prompt)
    except Exception as exc:
        write_request_log(f"[error] Retrieval failed | {type(exc).__name__}: {exc}")
        result = {
            "found": False,
            "context": "",
            "reason": "Retrieval failed due to an internal error.",
            "agent_guidance": DEFAULT_AGENT_GUIDANCE,
            "references": [],
        }

    duration = round(time.time() - start_time, 2)
    preview = (result.get("context") or result.get("reason") or "")[:80]
    write_request_log(f"✅ Finished retrieval | Time: {duration}s | Preview: {preview}...")

    # Return retrieval payload (MCP/IDE/LLM will decide what to do with it)
    return result


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host=host, port=port)
