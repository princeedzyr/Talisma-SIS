from wingman_ai.business_skills.record_update.service import get_record_update_service
from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.review_builder.workflow import build_cancel_action, build_collect_field_action, build_dependency_review_actions


UPDATE_METHOD = "wingman_ai.api.record_update.update_record"
UPDATE_FIELD_METHOD = "wingman_ai.api.record_update.continue_update_field"


class RecordUpdateCapability(Capability):
    name = "update"

    def __init__(self, service=None):
        self._service = service

    def handle(self, message, context, intent):
        result = self.service.handle_message(message=message, context=context, intent=intent)
        actions = build_actions(result)
        return CapabilityResult(
            message=result.get("message") or "Update request prepared.",
            actions=actions,
            data={
                "business_skill": "record_update",
                "operation": "update",
                "result": result,
            },
            requires_confirmation=any(action.get("requires_confirmation") for action in actions),
        )

    @property
    def service(self):
        if self._service is None:
            self._service = get_record_update_service()
        return self._service


def build_actions(result):
    if not result.get("supported") or result.get("cancelled"):
        return []

    doctype = result.get("doctype") or "Record"
    stage = result.get("stage")
    next_field = result.get("next_missing_field")
    if stage == "interactive_review":
        return build_interactive_update_actions(result) + [build_cancel_action(doctype)]
    if stage == "value_collection" and next_field:
        return [build_update_value_collection_action(result, next_field), build_cancel_action(doctype)]
    if stage in ("record_selection", "field_selection", "value_collection") and next_field:
        return [build_collect_field_action(next_field), build_cancel_action(doctype)]

    dependencies = result.get("missing_dependencies") or result.get("missing_link_dependencies") or []
    if dependencies:
        resume_message = result.get("original_message") or ""
        return build_dependency_review_actions(dependencies, resume_review={"message": resume_message} if resume_message else None) + [
            build_cancel_action(doctype)
        ]

    if result.get("ready"):
        return [build_update_action(result), build_continue_editing_action(result), build_cancel_action(doctype)]
    return [build_cancel_action(doctype)]


def build_update_value_collection_action(result, field):
    return build_collect_field_action(
        field,
        method=UPDATE_FIELD_METHOD,
        action_type="update",
        args={
            "doctype": result.get("doctype"),
            "docname": result.get("docname"),
            "fieldname": field.get("fieldname"),
            "current": result.get("current") or {},
            "changes": result.get("changes") or {},
            "original_message": result.get("original_message"),
            "conversation_id": result.get("conversation_id"),
        },
    )


def build_interactive_update_actions(result):
    actions = []
    for field in result.get("editable_review_fields") or []:
        actions.append(
            {
                "type": "edit_update_field",
                "label": f"Edit {field.get('label') or 'Field'}",
                "payload": {
                    "field": field,
                    "method": UPDATE_FIELD_METHOD,
                    "action_type": "update",
                    "args": {
                        "doctype": result.get("doctype"),
                        "docname": result.get("docname"),
                        "fieldname": field.get("fieldname"),
                        "current": result.get("current") or {},
                        "changes": result.get("changes") or {},
                        "original_message": result.get("original_message"),
                        "conversation_id": result.get("conversation_id"),
                    },
                },
                "requires_confirmation": False,
                "auto_execute": False,
                "enabled": bool(field.get("fieldname")),
            }
        )
    return actions


def build_continue_editing_action(result):
    from wingman_ai.business_skills.record_update.formatter import format_interactive_update_review

    interactive = {
        **dict(result or {}),
        "stage": "interactive_review",
        "ready": False,
    }
    if not interactive.get("editable_review_fields"):
        interactive["editable_review_fields"] = [
            serialize_basic_update_field(field, interactive.get("current") or {}, interactive.get("changes") or {})
            for field in (interactive.get("fields") or [])[:60]
            if field.get("fieldname")
        ]
    interactive["message"] = format_interactive_update_review(interactive)
    return {
        "type": "review_update_fields",
        "label": "Continue Editing",
        "payload": {
            "message": interactive.get("message"),
            "actions": build_interactive_update_actions(interactive) + [build_cancel_action(result.get("doctype") or "Record")],
        },
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def serialize_basic_update_field(field, current, changes):
    fieldname = field.get("fieldname")
    has_change = fieldname in (changes or {})
    return {
        "fieldname": fieldname,
        "label": field.get("label") or str(fieldname or "Field").replace("_", " ").title(),
        "fieldtype": field.get("fieldtype"),
        "options": field.get("options"),
        "component": field.get("component") or {},
        "required": False,
        "choices": field.get("choices") or [],
        "current_value": (current or {}).get(fieldname),
        "new_value": (changes or {}).get(fieldname) if has_change else (current or {}).get(fieldname),
        "modified": has_change,
    }


def build_update_action(result):
    doctype = result.get("doctype")
    docname = result.get("docname")
    payload = {
        "doctype": doctype,
        "docname": docname,
        "data": result.get("changes") or {},
        "old_values": {row.get("fieldname"): row.get("old_value") for row in result.get("change_rows") or []},
    }
    if result.get("conversation_id"):
        payload["conversation_id"] = result.get("conversation_id")
    return {
        "type": "update",
        "label": f"Update {doctype}",
        "method": UPDATE_METHOD,
        "payload": payload,
        "requires_confirmation": True,
        "auto_execute": False,
        "enabled": bool(result.get("ready")),
    }
