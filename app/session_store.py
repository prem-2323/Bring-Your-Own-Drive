import secrets
from typing import Any

# Development-only in-memory store. Use Redis + encryption for production.
SESSIONS: dict[str, dict[str, Any]] = {}

def new_session_id() -> str:
    sid = secrets.token_urlsafe(32)
    SESSIONS[sid] = {}
    return sid

def get_session(sid: str | None) -> dict[str, Any] | None:
    if not sid:
        return None
    return SESSIONS.get(sid)

def destroy_session(sid: str | None) -> None:
    if sid:
        SESSIONS.pop(sid, None)
