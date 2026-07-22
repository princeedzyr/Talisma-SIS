from wingman_ai.exception_intelligence.message_safety import safe_exception_message


class RootCauseAnalyzer:
    def analyze(self, classification, exc=None, response=None, context=None):
        context = context or {}
        root = classification.get("root_cause") or "The operation could not be completed safely."
        specific = first_business_message(exc=exc, response=response, context=context)
        if specific:
            root = enrich_root_cause(root, specific)

        return {
            "operation": human_operation(context.get("operation"), context.get("doctype")),
            "crud_action": context.get("operation"),
            "target_doctype": context.get("doctype"),
            "docname": context.get("docname"),
            "conversation_id": context.get("conversation_id"),
            "erpnext_api": context.get("erpnext_api"),
            "current_user": context.get("user"),
            "current_company": context.get("company"),
            "current_step": context.get("current_step") or context.get("failure_stage") or context.get("operation"),
            "failure_stage": context.get("failure_stage") or context.get("operation"),
            "category": classification.get("category"),
            "severity": classification.get("severity") or "High",
            "root_cause": root,
            "business_impact": classification.get("business_impact"),
            "responsible_team": classification.get("team"),
            "recommended_recovery": classification.get("recovery"),
            "framework_component": context.get("component") or infer_component(context),
            "role_profile": role_profile(context),
            "technical_reference": {
                "exception_type": type(exc).__name__ if exc else None,
                "trace_id": trace_id(response, context),
                "original_exception": safe_exception_message(exc) if exc else None,
            },
        }


def first_business_message(exc=None, response=None, context=None):
    if isinstance(response, dict):
        for issue in response.get("validation_issues") or []:
            if isinstance(issue, dict) and issue.get("message"):
                return append_context_value(safe_exception_message(issue), issue, context)
        for error in response.get("errors") or []:
            if isinstance(error, dict) and error.get("message"):
                return safe_exception_message(error)
        if response.get("message"):
            return safe_exception_message(response.get("message"))
    if exc:
        return safe_exception_message(exc)
    return None


def append_context_value(message, issue, context=None):
    fieldname = (issue or {}).get("fieldname")
    data = (context or {}).get("data") or {}
    if not fieldname or fieldname not in data:
        return message
    value = data.get(fieldname)
    if value in (None, "", []):
        return message
    return f"{message} Requested value: {value}."


def enrich_root_cause(root, specific):
    specific = str(specific or "").strip()
    if not specific:
        return root
    if specific.lower() in str(root or "").lower():
        return root
    return f"{root} Talisma OneCampus reported: {specific}"


def human_operation(operation, doctype=None):
    operation = str(operation or "Operation").replace("_", " ").title()
    return f"{operation} {doctype}".strip() if doctype else operation


def infer_component(context):
    operation = str((context or {}).get("operation") or "").lower()
    if "create" in operation:
        return "UniversalCreateService"
    if "update" in operation:
        return "UniversalUpdateService"
    if "delete" in operation:
        return "UniversalDeleteService"
    if "search" in operation or "read" in operation:
        return "UniversalERPService"
    return "Wingman Framework"


def role_profile(context):
    explicit = (context or {}).get("role_profile") or (context or {}).get("viewer_role")
    if explicit:
        return str(explicit).lower()
    user = str((context or {}).get("user") or "").lower()
    if user in {"administrator", "admin"}:
        return "administrator"
    if "developer" in user:
        return "developer"
    return "business_user"


def trace_id(response, context):
    if context.get("trace_id"):
        return context.get("trace_id")
    if isinstance(response, dict):
        return response.get("trace_id")
    return None
