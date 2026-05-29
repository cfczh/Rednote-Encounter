from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from zhang_agent.chat import ZhangBossAgent
from zhang_agent.config import server_host, server_port, skill_dir
from zhang_agent.sessions import SessionStore

store = SessionStore()
agent: ZhangBossAgent | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global agent
    root = skill_dir()
    if not (root / "assets" / "persona.md").exists():
        raise RuntimeError(f"张总 Skill 目录无效: {root}")
    agent = ZhangBossAgent()
    yield


app = FastAPI(
    title="张总 Agent",
    description="独立后台服务 — 仅张总对话人设",
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class SessionResponse(BaseModel):
    session_id: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "skill_dir": str(skill_dir()),
        "model": agent._model if agent else None,
    }


@app.post("/v1/sessions", response_model=SessionResponse)
def create_session():
    session = store.create()
    return SessionResponse(session_id=session.id)


@app.delete("/v1/sessions/{session_id}")
def delete_session(session_id: str):
    if not store.delete(session_id):
        raise HTTPException(404, "session not found")
    return {"ok": True}


@app.post("/v1/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    if agent is None:
        raise HTTPException(503, "agent not ready")

    if body.session_id:
        session = store.get(body.session_id)
        if session is None:
            raise HTTPException(404, "session not found")
    else:
        session = store.create()

    try:
        reply = agent.reply(session, body.message.strip())
    except Exception as e:
        raise HTTPException(502, f"LLM error: {e}") from e

    return ChatResponse(reply=reply, session_id=session.id)


def run_server() -> None:
    import uvicorn

    uvicorn.run(
        "zhang_agent.server:app",
        host=server_host(),
        port=server_port(),
        reload=False,
    )
