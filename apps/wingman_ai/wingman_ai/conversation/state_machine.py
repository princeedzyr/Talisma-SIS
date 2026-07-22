from copy import deepcopy
from datetime import datetime, timezone


STATE_START = "START"
STATE_DISCOVER = "DISCOVER"
STATE_COLLECT = "COLLECT"
STATE_DEPENDENCY = "DEPENDENCY"
STATE_VALIDATE = "VALIDATE"
STATE_RECOVER = "RECOVER"
STATE_REVIEW = "REVIEW"
STATE_EXECUTE = "EXECUTE"
STATE_VERIFY = "VERIFY"
STATE_COMPLETE = "COMPLETE"
STATE_FAILED = "FAILED"

PIPELINE = [
    STATE_START,
    STATE_DISCOVER,
    STATE_COLLECT,
    STATE_DEPENDENCY,
    STATE_VALIDATE,
    STATE_RECOVER,
    STATE_REVIEW,
    STATE_EXECUTE,
    STATE_VERIFY,
    STATE_COMPLETE,
]


class ConversationStateMachine:
    """Canonical operation state model shared by all Wingman conversations."""

    def build_turn_state(self, context=None, intent=None, result=None, legacy_state=None):
        context = context or {}
        legacy_state = deepcopy(legacy_state or {})
        result_data = getattr(result, "data", {}) or {}
        inner = result_data.get("result") or {}
        actions = getattr(result, "actions", []) or []
        operation = operation_name(intent, inner, result_data)
        target_doctype = inner.get("doctype") or inner.get("target_doctype") or doctype_from_context(context)
        current_state = infer_state(intent, result, inner, actions)

        session = {
            "original_intent": getattr(intent, "name", None),
            "intent_category": ((getattr(intent, "structured_intent", None) or {}).get("intent_category")),
            "operation": operation,
            "target_doctype": target_doctype,
            "docname": inner.get("docname") or docname_from_context(context),
            "current_state": current_state,
            "collected_values": collected_values(inner),
            "missing_values": missing_values(inner),
            "dependencies": dependencies(inner),
            "validation_status": validation_status(inner),
            "review_data": review_data(inner),
            "execution_status": execution_status(inner, result),
            "retry_information": retry_information(inner, result),
            "conversation_id": context.get("conversation_id"),
            "updated_at": now(),
        }

        return {
            "state_machine": "UniversalConversationStateMachine",
            "current_state": current_state,
            "operation": operation,
            "target_doctype": target_doctype,
            "session": session,
            "pipeline": pipeline_status(current_state),
            "legacy_state": {
                "active_state": legacy_state.get("active_state"),
                "stack": legacy_state.get("stack") or [],
                "completion_reason": legacy_state.get("completion_reason"),
            },
        }


def infer_state(intent, result, inner, actions):
    if getattr(result, "status", "success") != "success":
        return STATE_FAILED
    if inner.get("cancelled"):
        return STATE_COMPLETE
    if inner.get("missing_dependencies") or inner.get("missing_link_dependencies"):
        return STATE_DEPENDENCY
    if inner.get("next_missing_field") or inner.get("missing_fields"):
        if has_recovery(inner):
            return STATE_RECOVER
        return STATE_COLLECT
    if inner.get("preflight") and not (inner.get("preflight") or {}).get("valid", True):
        return STATE_RECOVER if (inner.get("preflight") or {}).get("recoverable", True) else STATE_FAILED
    if inner.get("ready") or has_write_confirmation(actions):
        return STATE_REVIEW
    if has_navigation(actions) or result_mode_is_complete(inner, result):
        return STATE_COMPLETE
    if getattr(intent, "capability", None) in {"create", "update", "delete"}:
        return STATE_DISCOVER
    return STATE_COMPLETE


def has_recovery(inner):
    preflight = (inner or {}).get("preflight") or {}
    next_field = (inner or {}).get("next_missing_field") or {}
    preflight_is_recoverable = preflight.get("recoverable") is True and preflight.get("valid") is False
    return bool(preflight.get("recovery_kind") or next_field.get("wingman_recovery") or preflight_is_recoverable)


def operation_name(intent, inner, result_data):
    return (
        (inner or {}).get("operation")
        or result_data.get("operation")
        or getattr(intent, "capability", None)
        or "conversation"
    )


def doctype_from_context(context):
    obj = (context or {}).get("object") or {}
    return obj.get("doctype") or obj.get("workspace")


def docname_from_context(context):
    obj = (context or {}).get("object") or {}
    return obj.get("docname")


def collected_values(inner):
    for key in ("data", "changes", "collected_fields"):
        value = (inner or {}).get(key)
        if isinstance(value, dict):
            return deepcopy(value)
    plan = (inner or {}).get("operation_plan") or {}
    return deepcopy(plan.get("collected_fields") or {})


def missing_values(inner):
    values = []
    for item in (inner or {}).get("missing_fields") or []:
        values.append(item)
    next_field = (inner or {}).get("next_missing_field") or {}
    if next_field and next_field.get("label") not in values:
        values.append(next_field.get("label") or next_field.get("fieldname"))
    return [item for item in values if item]


def dependencies(inner):
    return deepcopy((inner or {}).get("missing_dependencies") or (inner or {}).get("missing_link_dependencies") or [])


def validation_status(inner):
    preflight = (inner or {}).get("preflight") or {}
    if preflight:
        return "passed" if preflight.get("valid", True) else ("recoverable" if preflight.get("recoverable", True) else "blocked")
    if (inner or {}).get("validation_issues"):
        return "pending"
    if (inner or {}).get("ready"):
        return "passed"
    return "not_started"


def review_data(inner):
    return deepcopy((inner or {}).get("review") or {}) if (inner or {}).get("ready") else {}


def execution_status(inner, result):
    actions = getattr(result, "actions", []) or []
    if getattr(result, "requires_confirmation", False) or has_write_confirmation(actions):
        return "awaiting_user_approval"
    if (inner or {}).get("execution_verification"):
        verification = inner.get("execution_verification") or {}
        return f"verified_{verification.get('status') or 'unknown'}"
    return "not_started"


def retry_information(inner, result):
    diagnostic = (inner or {}).get("exception_diagnostic") or {}
    if not diagnostic and isinstance(getattr(result, "data", None), dict):
        diagnostic = result.data.get("exception_diagnostic") or {}
    return deepcopy(diagnostic.get("retry") or {})


def pipeline_status(current_state):
    status = []
    reached_current = False
    for state in PIPELINE:
        if state == current_state:
            reached_current = True
            item_status = "current"
        elif reached_current:
            item_status = "pending"
        else:
            item_status = "complete"
        status.append({"state": state, "status": item_status})
    if current_state == STATE_FAILED:
        status.append({"state": STATE_FAILED, "status": "current"})
    return status


def has_write_confirmation(actions):
    confirmation_types = {"create", "update", "delete", "submit", "cancel", "apply_workflow"}
    return any((action or {}).get("requires_confirmation") or (action or {}).get("type") in confirmation_types for action in actions or [])


def has_navigation(actions):
    return any((action or {}).get("type") == "navigate" for action in actions or [])


def result_mode_is_complete(inner, result):
    result_data = getattr(result, "data", {}) or {}
    return result_data.get("response_mode") in {"conversation", "fast_context", "document_read", "explicit_document_read"}


def now():
    return datetime.now(timezone.utc).isoformat()
