import threading
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    messages: list[dict[str, str]] = field(default_factory=list)


class SessionStore:
    def __init__(self, max_messages: int = 40) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._max_messages = max_messages

    def create(self) -> Session:
        sid = uuid.uuid4().hex
        session = Session(id=sid)
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def append(self, session: Session, role: str, content: str) -> None:
        with self._lock:
            session.messages.append({"role": role, "content": content})
            if len(session.messages) > self._max_messages:
                session.messages = session.messages[-self._max_messages :]
