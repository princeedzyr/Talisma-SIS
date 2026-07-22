from wingman_ai.integrations.erpnext.metadata import get_doctype_summary
from wingman_ai.services.context import get_context_object, parse_context, summarize_context


def build_context(raw_context=None, user=None):
    parsed = parse_context(raw_context)
    context_object = get_context_object(parsed)
    doctype = context_object.get("doctype")

    return {
        "raw": parsed,
        "object": context_object,
        "summary": summarize_context(parsed),
        "doctype": get_doctype_summary(doctype) if doctype else None,
        "user": user,
    }

