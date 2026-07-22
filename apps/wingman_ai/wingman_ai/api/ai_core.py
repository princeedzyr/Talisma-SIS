import frappe

from wingman_ai.application.orchestrator import get_orchestrator
from wingman_ai.conversation.service import ConversationService
from wingman_ai.integrations.ai import get_ai_provider_status


@frappe.whitelist()
def start_conversation(metadata=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    return ConversationService().start_conversation(user=user, metadata=metadata)


@frappe.whitelist()
def send_message(message=None, context=None, conversation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    return get_orchestrator().handle_message(
        message,
        raw_context=context,
        user=user,
        conversation_id=conversation_id,
    )


@frappe.whitelist()
def end_conversation(conversation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    return ConversationService().end_conversation(conversation_id, user=user)


@frappe.whitelist()
def clear_conversation(conversation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    return ConversationService().clear_conversation(conversation_id, user=user)


@frappe.whitelist()
def conversation_history(conversation_id=None, limit=50):
    user = getattr(getattr(frappe, "session", None), "user", None)
    return ConversationService().get_history(conversation_id, user=user, limit=limit)


@frappe.whitelist()
def provider_status():
    return get_ai_provider_status()


@frappe.whitelist()
def health_check():
    return {
        "status": "ok",
        "provider": get_ai_provider_status(),
    }
