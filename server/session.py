import json
import os
import uuid
import random
from datetime import datetime
from dataclasses import dataclass, field

from utils.path_tool import get_abs_path

SESSIONS_FILE = get_abs_path("data/sessions.json")


@dataclass
class SessionState:
    session_id: str
    user_id: str
    title: str = "新对话"
    messages: list[dict] = field(default_factory=list)
    extract_result: str = ""
    created_at: str = ""


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}
        self._load()

    def _load(self):
        if not os.path.exists(SESSIONS_FILE):
            return
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                state = SessionState(
                    session_id=item["session_id"],
                    user_id=item["user_id"],
                    title=item.get("title", "新对话"),
                    messages=item.get("messages", []),
                    extract_result=item.get("extract_result", ""),
                    created_at=item.get("created_at", ""),
                )
                self._sessions[state.session_id] = state
        except Exception:
            pass

    def _save(self):
        os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
        data = []
        for s in self._sessions.values():
            data.append({
                "session_id": s.session_id,
                "user_id": s.user_id,
                "title": s.title,
                "messages": s.messages,
                "extract_result": s.extract_result,
                "created_at": s.created_at,
            })
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create(self) -> SessionState:
        session_id = uuid.uuid4().hex
        user_id = str(random.randint(1001, 9999))
        state = SessionState(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        self._sessions[session_id] = state
        self._save()
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def list_all(self) -> list[dict]:
        result = []
        for s in self._sessions.values():
            result.append({
                "session_id": s.session_id,
                "title": s.title,
                "created_at": s.created_at,
                "message_count": len(s.messages),
            })
        result.sort(key=lambda x: x["created_at"], reverse=True)
        return result

    def delete(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        self._save()
        return True

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get(session_id)
        if session:
            session.messages.append({"role": role, "content": content})
            if role == "user" and session.title == "新对话":
                session.title = content[:40] + ("..." if len(content) > 40 else "")
            self._save()

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
