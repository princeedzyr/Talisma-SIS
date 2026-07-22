import frappe

from wingman_ai.application.orchestrator import get_orchestrator


@frappe.whitelist()
def propose(message=None, context=None):
    user = getattr(getattr(frappe, "session", None), "user", None)
    text = message or "Create an approval workflow"
    return get_orchestrator().handle_message(text, raw_context=context, user=user)

