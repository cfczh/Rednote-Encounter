from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from persona_agent.agents import AgentPool
from persona_agent.config import default_persona_id, openai_model, skills_dir
from persona_agent.registry import PersonaRegistry
from persona_agent.sessions import SessionStore

store = SessionStore()
registry = PersonaRegistry()
pool: AgentPool | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global pool
    registry.refresh()
    if not registry.list_ids():
        raise RuntimeError(f"skills 目录下无人设: {skills_dir()}")
    pool = AgentPool(registry)
    yield


app = FastAPI(
    title="Persona Agent",
    description="按 persona_id 动态加载人设的对话服务",
    version="0.2.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = None
    persona_id: str | None = Field(
        None,
        description="人设 ID，对应 skills/<persona_id> 或 meta.json 的 slug",
    )


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    persona_id: str
    persona_name: str


class SessionResponse(BaseModel):
    session_id: str
    persona_id: str


@app.get("/health")
def health():
    assert pool is not None
    sample = pool.get(default_persona_id())
    return {
        "status": "ok",
        "skills_dir": str(skills_dir()),
        "default_persona_id": default_persona_id(),
        "personas": [
            {"persona_id": p.persona_id, "name": p.name, "path": str(p.path)}
            for p in registry.list()
        ],
        "model": sample.model,
    }


@app.get("/v1/personas")
def list_personas():
    return {
        "personas": [
            {"persona_id": p.persona_id, "name": p.name}
            for p in registry.list()
        ]
    }


@app.post("/v1/sessions", response_model=SessionResponse)
def create_session(persona_id: str | None = None):
    pid = persona_id or default_persona_id()
    try:
        registry.get(pid)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    session = store.create(pid)
    return SessionResponse(session_id=session.id, persona_id=pid)


@app.delete("/v1/sessions/{session_id}")
def delete_session(session_id: str):
    if not store.delete(session_id):
        raise HTTPException(404, "session not found")
    return {"ok": True}


@app.post("/v1/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    if pool is None:
        raise HTTPException(503, "agent pool not ready")

    pid = body.persona_id or default_persona_id()

    if body.session_id:
        session = store.get(body.session_id)
        if session is None:
            raise HTTPException(404, "session not found")
        if body.persona_id and body.persona_id != session.persona_id:
            raise HTTPException(
                400,
                f"session 已绑定 persona_id={session.persona_id}，"
                f"与请求的 {body.persona_id} 不一致",
            )
        pid = session.persona_id
    else:
        try:
            registry.get(pid)
        except KeyError as e:
            raise HTTPException(400, str(e)) from e
        session = store.create(pid)

    try:
        agent = pool.get(pid)
        reply = agent.reply(session, body.message.strip())
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"LLM error: {e}") from e

    return ChatResponse(
        reply=reply,
        session_id=session.id,
        persona_id=pid,
        persona_name=registry.display_name(pid),
    )


def run_server() -> None:
    import uvicorn

    from persona_agent.config import server_host, server_port

    uvicorn.run(
        "persona_agent.server:app",
        host=server_host(),
        port=server_port(),
        reload=False,
    )
