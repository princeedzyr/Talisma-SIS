import frappe

from wingman_ai.conversation.service import ConversationService
from wingman_ai.intent.service import IntentRecognitionService
from wingman_ai.services.context import get_context_object, parse_context, summarize_context


@frappe.whitelist()
def parse_intent(message=None, context=None, conversation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    intent_context = build_intent_context(context=context, conversation_id=conversation_id, user=user)
    return IntentRecognitionService().parse(message=message, context=intent_context)


@frappe.whitelist()
def explain_intent(message=None, context=None, conversation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    intent_context = build_intent_context(context=context, conversation_id=conversation_id, user=user)
    return IntentRecognitionService().explain(message=message, context=intent_context)


@frappe.whitelist()
def conversation_state(conversation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    history = ConversationService().get_history(conversation_id, user=user, limit=12) if conversation_id else []
    return {
        "conversation_id": conversation_id,
        "history_count": len(history),
        "last_messages": sanitize_history(history[-4:]),
    }


@frappe.whitelist()
def supported_intents():
    return IntentRecognitionService().supported()


@frappe.whitelist()
def health_check():
    return IntentRecognitionService().health()


def build_intent_context(context=None, conversation_id=None, user=None):
    raw_context = parse_context(context)
    if conversation_id:
        raw_context["conversation_id"] = conversation_id

    return {
        "raw": raw_context,
        "object": get_context_object(raw_context),
        "summary": summarize_context(raw_context),
        "conversation_id": conversation_id or raw_context.get("conversation_id"),
        "history": ConversationService().get_history(conversation_id, user=user, limit=12) if conversation_id else [],
        "user": user,
    }


def sanitize_history(history):
    sanitized = []
    for item in history or []:
        sanitized.append(
            {
                "role": item.get("role"),
                "created_at": item.get("created_at"),
                "metadata": item.get("metadata") or {},
            }
        )
    return sanitized
