from wingman_ai.business_skills.record_creation.formatter import (
    format_collection_prompt,
    format_dependency_collection_prompt,
    format_preflight_validation_prompt,
)
from wingman_ai.link_resolution import LINK_SEARCH_METHOD
from wingman_ai.review_builder.service import format_creation_review_card


GENERIC_CREATE_METHOD = "wingman_ai.api.record_creation.create_record"
DEPENDENCY_CONTINUE_METHOD = "wingman_ai.api.record_creation.continue_dependency_create"


def build_create_action(doctype, data=None, label=None, method=None, payload=None, enabled=True):
    return {
        "type": "create",
        "label": label or f"Create {friendly_doctype(doctype)}",
        "method": method or GENERIC_CREATE_METHOD,
        "payload": payload if payload is not None else {"doctype": doctype, "data": data or {}},
        "requires_confirmation": True,
        "auto_execute": False,
        "enabled": bool(enabled),
    }


def build_cancel_action(doctype):
    return {
        "type": "cancel_review",
        "label": "Cancel",
        "payload": {"doctype": doctype},
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def friendly_doctype(doctype):
    return str(doctype or "Record").removeprefix("Talisma ")


def build_collect_field_action(field, method=None, args=None, action_type=None):
    label = (field or {}).get("label") or "Required Detail"
    payload = {"field": field or {}}
    if method:
        payload.update(
            {
                "method": method,
                "action_type": action_type or "update",
                "args": args or {},
            }
        )
    return {
        "type": "collect_field",
        "label": f"Provide {label}",
        "payload": payload,
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def build_creation_review_actions(result, parent_action):
    doctype = result.get("doctype") or "Record"
    next_field = result.get("next_missing_field")
    if next_field and not result.get("ready"):
        return [build_collect_field_action(next_field), build_cancel_action(doctype)]
    dependencies = result.get("missing_dependencies") or result.get("missing_link_dependencies") or []
    if dependencies:
        return build_dependency_review_actions(dependencies, resume_review=resume_review_from_result(result)) + [build_cancel_action(doctype)]
    if not result.get("ready"):
        return [build_cancel_action(doctype)]
    return [parent_action, build_cancel_action(doctype)]


def build_dependency_review_actions(dependencies, resume_review=None):
    actions = []
    for dependency in dependencies or []:
        action = build_dependency_review_action(dependency, resume_review=resume_review)
        if action:
            actions.append(action)
        search_action = build_dependency_search_again_action(dependency, resume_review=resume_review)
        if search_action:
            actions.append(search_action)
    return actions


def build_dependency_review_action(dependency, resume_review=None):
    target_doctype = dependency.get("target_doctype")
    value = dependency.get("value")
    if not target_doctype or value in (None, "", []):
        return None

    child_prepared = dependency_prepared_payload(dependency)
    child_resume = resume_review_from_dependency(dependency)
    child_payload = build_dependency_session_payload(child_prepared, resume_review=child_resume)

    action = {
        "type": "review_dependency",
        "label": f"Create {target_doctype}",
        "payload": child_payload,
        "requires_confirmation": True,
        "auto_execute": False,
        "enabled": True,
    }
    if resume_review:
        action["resume_review"] = resume_review
    return action


def build_dependency_session_payload(prepared, resume_review=None):
    return {
        "message": format_dependency_session_message(prepared),
        "actions": build_dependency_session_actions(prepared, resume_review=resume_review),
    }


def format_dependency_session_message(prepared):
    if prepared.get("next_missing_field") and not prepared.get("ready"):
        preflight = prepared.get("preflight") or {}
        return format_collection_prompt(prepared, reason=preflight.get("guidance") if not preflight.get("valid", True) else None)
    if prepared.get("missing_dependencies") or prepared.get("missing_link_dependencies"):
        return format_dependency_collection_prompt(prepared)
    if not (prepared.get("preflight") or {}).get("valid", True):
        return format_preflight_validation_prompt(prepared)
    return format_creation_review_card(prepared)


def build_dependency_session_actions(prepared, resume_review=None):
    doctype = prepared.get("doctype") or "Record"
    next_field = prepared.get("next_missing_field")
    if next_field and not prepared.get("ready"):
        return [build_dependency_collect_field_action(prepared, resume_review=resume_review), build_cancel_action(doctype)]

    dependencies = prepared.get("missing_dependencies") or prepared.get("missing_link_dependencies") or []
    if dependencies:
        return build_dependency_review_actions(dependencies, resume_review=resume_review_from_result(prepared) or resume_review) + [
            build_cancel_action(doctype)
        ]

    if not prepared.get("ready"):
        return [build_cancel_action(doctype)]

    return [build_create_action(doctype, data=prepared.get("data") or {}, enabled=bool(prepared.get("ready"))), build_cancel_action(doctype)]


def build_dependency_search_again_action(dependency, resume_review=None):
    source_doctype = dependency.get("source_doctype")
    fieldname = dependency.get("fieldname")
    target_doctype = dependency.get("target_doctype")
    if not source_doctype or not fieldname or not target_doctype:
        return None

    field = {
        "fieldname": fieldname,
        "label": dependency.get("label") or target_doctype,
        "fieldtype": "Link",
        "options": target_doctype,
        "component": {
            "type": "link",
            "target_doctype": target_doctype,
            "search_method": LINK_SEARCH_METHOD,
            "allow_create": True,
        },
        "choices": dependency.get("matches") or [],
        "placeholder": f"Search or enter {dependency.get('label') or target_doctype}",
        "required": True,
    }
    args = {
        "doctype": source_doctype,
        "data": dependency.get("source_data") or {},
        "fieldname": fieldname,
    }
    if resume_review:
        args["resume_review"] = resume_review
    action = build_collect_field_action(
        field,
        method=DEPENDENCY_CONTINUE_METHOD,
        args=args,
        action_type="link_resolution",
    )
    action["label"] = "Search Again"
    return action


def build_dependency_collect_field_action(prepared, resume_review=None):
    doctype = prepared.get("doctype") or "Record"
    field = prepared.get("next_missing_field") or {}
    args = {
        "doctype": doctype,
        "data": prepared.get("data") or {},
        "fieldname": field.get("fieldname"),
    }
    if resume_review:
        args["resume_review"] = resume_review
    return build_collect_field_action(field, method=DEPENDENCY_CONTINUE_METHOD, args=args)


def dependency_prepared_payload(dependency):
    missing_dependencies = dependency.get("missing_dependencies") or dependency.get("missing_link_dependencies") or []
    missing_fields = dependency.get("missing_fields") or []
    return {
        "operation": "create",
        "supported": True,
        "doctype": dependency.get("target_doctype"),
        "data": dependency.get("create_data") or {},
        "review": dependency.get("review") or {},
        "missing_fields": missing_fields,
        "missing_dependencies": missing_dependencies,
        "missing_link_dependencies": missing_dependencies,
        "next_missing_field": dependency.get("next_missing_field"),
        "validation_issues": dependency.get("validation_issues") or [],
        "preflight": dependency.get("preflight") or {"valid": True},
        "ready": not missing_fields and not missing_dependencies,
    }


def resume_review_from_result(result):
    message = ((result.get("dependency_context") or {}).get("original_message") or "").strip()
    return {"message": message} if message else None


def resume_review_from_dependency(dependency):
    message = (dependency.get("source_message") or "").strip()
    return {"message": message} if message else None
