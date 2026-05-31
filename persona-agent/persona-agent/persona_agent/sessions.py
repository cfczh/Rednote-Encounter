import threading
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    persona_id: str
    messages: list[dict[str, str]] = field(default_factory=list)


class SessionStore:
    def __init__(self, max_messages: int = 40) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._max_messages = max_messages

    def create(self, persona_id: str) -> Session:
        sid = uuid.uuid4().hex
        session = Session(id=sid, persona_id=persona_id)
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None
