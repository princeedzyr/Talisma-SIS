import frappe

from wingman_ai.application.orchestrator import get_orchestrator


@frappe.whitelist()
def run(request=None, message=None, context=None, conversation_id=None, plan_id=None, strategy=None, correlation_id=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    text = message or request or "Analyze this request"
    return get_orchestrator().handle_message(text, raw_context=context, user=user)
