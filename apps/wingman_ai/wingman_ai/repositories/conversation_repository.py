from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4


_MEMORY_STORE = {}
DEFAULT_EXPIRY_SECONDS = 60 * 60 * 8
PENDING_CREATE_DRAFT_KEY = "pending_create_draft"
PENDING_UPDATE_DRAFT_KEY = "pending_update_draft"
PENDING_WORKFLOW_SESSION_KEY = "pending_workflow_session"
CONVERSATION_STATE_KEY = "conversation_state"


def create_conversation(user=None, metadata=None, conversation_id=None):
    conversation_id = conversation_id or uuid4().hex
    now = utc_now()
    conversation = {
        "conversation_id": conversation_id,
        "user": user,
        "metadata": metadata or {},
        "messages": [],
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_EXPIRY_SECONDS)).isoformat(),
    }
    set_conversation(conversation_id, conversation)
    add_user_conversation(user, conversation_id)
    return deepcopy(conversation)


def get_conversation(conversation_id, user=None):
    if not conversation_id:
        return None

    conversation = get_cached_value(conversation_key(conversation_id))
    if not conversation:
        return None

    if user and conversation.get("user") and conversation.get("user") != user:
        return None

    return deepcopy(conversation)


def set_conversation(conversation_id, conversation):
    set_cached_value(conversation_key(conversation_id), conversation, DEFAULT_EXPIRY_SECONDS)


def list_conversations(user=None):
    ids = get_cached_value(user_conversations_key(user)) or []
    conversations = []
    for conversation_id in ids:
        conversation = get_conversation(conversation_id, user=user)
        if conversation:
            conversations.append(conversation)
    return conversations


def append_message(conversation_id, role, content, user=None, metadata=None):
    if not conversation_id:
        return {
            "stored": False,
            "conversation_id": conversation_id,
            "role": role,
            "user": user,
            "reason": "No conversation ID was provided.",
        }

    conversation = get_conversation(conversation_id, user=user) or create_conversation(user=user, conversation_id=conversation_id)
    conversation["messages"].append(
        {
            "message_id": uuid4().hex,
            "role": role,
            "content": content or "",
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
    )
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)

    return {
        "stored": True,
        "conversation_id": conversation_id,
        "role": role,
        "user": user,
    }


def get_pending_create_draft(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    return deepcopy((conversation.get("metadata") or {}).get(PENDING_CREATE_DRAFT_KEY))


def set_pending_create_draft(conversation_id, draft, user=None):
    if not conversation_id:
        return None
    conversation = get_conversation(conversation_id, user=user) or create_conversation(user=user, conversation_id=conversation_id)
    metadata = dict(conversation.get("metadata") or {})
    metadata[PENDING_CREATE_DRAFT_KEY] = deepcopy(draft or {})
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(metadata[PENDING_CREATE_DRAFT_KEY])


def clear_pending_create_draft(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    metadata = dict(conversation.get("metadata") or {})
    removed = metadata.pop(PENDING_CREATE_DRAFT_KEY, None)
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(removed)


def get_pending_update_draft(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    return deepcopy((conversation.get("metadata") or {}).get(PENDING_UPDATE_DRAFT_KEY))


def set_pending_update_draft(conversation_id, draft, user=None):
    if not conversation_id:
        return None
    conversation = get_conversation(conversation_id, user=user) or create_conversation(user=user, conversation_id=conversation_id)
    metadata = dict(conversation.get("metadata") or {})
    metadata[PENDING_UPDATE_DRAFT_KEY] = deepcopy(draft or {})
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(metadata[PENDING_UPDATE_DRAFT_KEY])


def clear_pending_update_draft(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    metadata = dict(conversation.get("metadata") or {})
    removed = metadata.pop(PENDING_UPDATE_DRAFT_KEY, None)
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(removed)


def get_pending_workflow_session(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    return deepcopy((conversation.get("metadata") or {}).get(PENDING_WORKFLOW_SESSION_KEY))


def set_pending_workflow_session(conversation_id, session, user=None):
    if not conversation_id:
        return None
    conversation = get_conversation(conversation_id, user=user) or create_conversation(user=user, conversation_id=conversation_id)
    metadata = dict(conversation.get("metadata") or {})
    metadata[PENDING_WORKFLOW_SESSION_KEY] = deepcopy(session or {})
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(metadata[PENDING_WORKFLOW_SESSION_KEY])


def clear_pending_workflow_session(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    metadata = dict(conversation.get("metadata") or {})
    removed = metadata.pop(PENDING_WORKFLOW_SESSION_KEY, None)
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(removed)


def get_conversation_state(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    return deepcopy((conversation.get("metadata") or {}).get(CONVERSATION_STATE_KEY))


def set_conversation_state(conversation_id, state, user=None):
    if not conversation_id:
        return None
    conversation = get_conversation(conversation_id, user=user) or create_conversation(user=user, conversation_id=conversation_id)
    metadata = dict(conversation.get("metadata") or {})
    metadata[CONVERSATION_STATE_KEY] = deepcopy(state or {})
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(metadata[CONVERSATION_STATE_KEY])


def clear_conversation_state(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    metadata = dict(conversation.get("metadata") or {})
    removed = metadata.pop(CONVERSATION_STATE_KEY, None)
    conversation["metadata"] = metadata
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(removed)


def get_history(conversation_id, user=None, limit=50):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return []
    return conversation.get("messages", [])[-int(limit):]


def end_conversation(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    conversation["status"] = "ended"
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(conversation)


def clear_conversation(conversation_id, user=None):
    conversation = get_conversation(conversation_id, user=user)
    if not conversation:
        return None
    conversation["messages"] = []
    conversation["updated_at"] = utc_now()
    set_conversation(conversation_id, conversation)
    return deepcopy(conversation)


def add_user_conversation(user, conversation_id):
    key = user_conversations_key(user)
    ids = get_cached_value(key) or []
    if conversation_id not in ids:
        ids.append(conversation_id)
    set_cached_value(key, ids, DEFAULT_EXPIRY_SECONDS)


def conversation_key(conversation_id):
    return f"wingman_ai:conversation:{conversation_id}"


def user_conversations_key(user):
    return f"wingman_ai:user_conversations:{user or 'Guest'}"


def get_cached_value(key):
    try:
        import frappe

        return frappe.cache().get_value(key)
    except Exception:
        return deepcopy(_MEMORY_STORE.get(key))


def set_cached_value(key, value, expires_in_sec=None):
    try:
        import frappe

        frappe.cache().set_value(key, value, expires_in_sec=expires_in_sec)
    except Exception:
        _MEMORY_STORE[key] = deepcopy(value)


def utc_now():
    return datetime.now(timezone.utc).isoformat()
