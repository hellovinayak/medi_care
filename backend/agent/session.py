"""Multi-turn session management for conversation continuity."""

from datetime import datetime, timedelta
from typing import Optional
import uuid


class SessionManager:
    """Manages conversation sessions for multi-turn AI interactions.

    Stores conversation history in memory (per-session).
    In production, this could be backed by Redis or a database.
    """

    def __init__(self, max_session_age_hours: int = 24):
        self._sessions: dict = {}
        self._max_age = timedelta(hours=max_session_age_hours)

    def create_session(self, user_id: int) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        return session_id

    def get_session(self, session_id: str) -> dict:
        """Get or create a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "user_id": None,
                "messages": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

        session = self._sessions[session_id]
        session["updated_at"] = datetime.utcnow()

        # Trim old messages to prevent context overflow (keep last 20 exchanges)
        if len(session["messages"]) > 40:
            session["messages"] = session["messages"][-40:]

        return session

    def clear_session(self, session_id: str):
        """Clear a session's conversation history."""
        if session_id in self._sessions:
            self._sessions[session_id]["messages"] = []
            self._sessions[session_id]["updated_at"] = datetime.utcnow()

    def delete_session(self, session_id: str):
        """Delete a session entirely."""
        self._sessions.pop(session_id, None)

    def cleanup_old_sessions(self):
        """Remove sessions older than max_age."""
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session["updated_at"] > self._max_age
        ]
        for sid in expired:
            del self._sessions[sid]

    def get_session_history(self, session_id: str) -> list:
        """Get formatted conversation history for display."""
        session = self._sessions.get(session_id, {})
        messages = session.get("messages", [])

        history = []
        for msg in messages:
            role = msg.get("role", "")
            parts = msg.get("parts", [])

            for part in parts:
                if "text" in part:
                    history.append({
                        "role": "user" if role == "user" else "assistant",
                        "content": part["text"]
                    })

        return history
