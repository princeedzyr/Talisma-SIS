import json

import frappe

from wingman_ai.application.orchestrator import get_orchestrator
from wingman_ai.services.context import parse_context


@frappe.whitelist()
def chat(message=None, doctype=None, compiled_data=None):
    context = {"doctype": doctype} if doctype else {}
    if compiled_data:
        context["compiled_data"] = parse_context(compiled_data)

    user = getattr(getattr(frappe, "session", None), "user", None)
    return get_orchestrator().handle_message(
        message=message,
        raw_context=json.dumps(context),
        user=user,
    )


@frappe.whitelist()
def submit_missing_field(doctype=None, persona=None, compiled_data=None, fieldname=None, value=None):
    context = {
        "doctype": doctype,
        "persona": persona,
        "compiled_data": parse_context(compiled_data),
        "fieldname": fieldname,
    }
    user = getattr(getattr(frappe, "session", None), "user", None)
    message = f"Update {fieldname} for {doctype} to {value}"
    response = get_orchestrator().handle_message(
        message=message,
        raw_context=json.dumps(context),
        user=user,
    )
    response["requires_confirmation"] = True
    return response

