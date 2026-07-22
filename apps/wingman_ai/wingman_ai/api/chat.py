import frappe
import re

from wingman_ai.application.orchestrator import get_orchestrator


@frappe.whitelist()
def send(message=None, context=None, conversation_id=None, request_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    cache_key = response_cache_key(user, conversation_id, request_id)
    if cache_key:
        cached = frappe.cache().get_value(cache_key)
        if cached is not None:
            return cached

    response = get_orchestrator().handle_message(
        message,
        raw_context=context,
        user=user,
        conversation_id=conversation_id,
        request_id=request_id,
    )
    if cache_key:
        frappe.cache().set_value(cache_key, response, expires_in_sec=60 * 60)
    return response


def response_cache_key(user, conversation_id, request_id):
    safe_request_id = re.sub(r"[^A-Za-z0-9_-]", "", str(request_id or ""))[:80]
    safe_conversation_id = re.sub(r"[^A-Za-z0-9_-]", "", str(conversation_id or ""))[:80]
    if not safe_request_id or not safe_conversation_id:
        return None
    return f"wingman_ai:chat_response:{user or 'Guest'}:{safe_conversation_id}:{safe_request_id}"
