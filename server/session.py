import uuid
import random
from dataclasses import dataclass, field


@dataclass
class SessionState:
    session_id: str
    user_id: str
    messages: list[dict] = field(default_factory=list)
    extract_result: str = ""


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def create(self) -> SessionState:
        session_id = uuid.uuid4().hex
        user_id = str(random.randint(1001, 9999))
        state = SessionState(session_id=session_id, user_id=user_id)
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get(session_id)
        if session:
            session.messages.append({"role": role, "content": content})

    def get_conversation_text(self, session_id: str) -> str:
        session = self.get(session_id)
        if not session:
            return ""
        lines = []
        for msg in session.messages:
            role = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)


session_manager = SessionManager()
