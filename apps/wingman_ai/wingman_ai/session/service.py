from datetime import datetime, timedelta, timezone
from uuid import uuid4


_MEMORY_SESSIONS = {}
DEFAULT_SESSION_EXPIRY_SECONDS = 60 * 60 * 8


class SessionService:
    def start_session(self, user=None, browser_id=None, conversation_id=None, metadata=None):
        session_id = uuid4().hex
        session = {
            "session_id": session_id,
            "user": user,
            "browser_id": browser_id,
            "conversation_id": conversation_id,
            "metadata": metadata or {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_SESSION_EXPIRY_SECONDS)).isoformat(),
        }
        set_session(session_id, session)
        return session

    def get_session(self, session_id, user=None):
        session = get_session(session_id)
        if not session:
            return None
        if user and session.get("user") and session.get("user") != user:
            return None
        return session

    def recover_session(self, session_id=None, user=None, browser_id=None):
        if session_id:
            session = self.get_session(session_id, user=user)
            if session:
                return session
        return self.start_session(user=user, browser_id=browser_id)

    def end_session(self, session_id, user=None):
        session = self.get_session(session_id, user=user)
        if not session:
            return None
        session["ended_at"] = utc_now()
        set_session(session_id, session)
        return session


def get_session(session_id):
    if not session_id:
        return None
    key = session_key(session_id)
    try:
        import frappe

        return frappe.cache().get_value(key)
    except Exception:
        return _MEMORY_SESSIONS.get(key)


def set_session(session_id, session):
    key = session_key(session_id)
    try:
        import frappe

        frappe.cache().set_value(key, session, expires_in_sec=DEFAULT_SESSION_EXPIRY_SECONDS)
    except Exception:
        _MEMORY_SESSIONS[key] = session


def session_key(session_id):
    return f"wingman_ai:session:{session_id}"


def utc_now():
    return datetime.now(timezone.utc).isoformat()
