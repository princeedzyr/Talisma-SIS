from wingman_ai.business_skills.record_delete.service import get_record_delete_service
from wingman_ai.capabilities.base import Capability, CapabilityResult


DELETE_METHOD = "wingman_ai.api.record_delete.delete_record"


class RecordDeleteCapability(Capability):
    name = "delete"

    def __init__(self, service=None):
        self._service = service

    def handle(self, message, context, intent):
        result = self.service.handle_message(message=message, context=context, intent=intent)
        actions = build_actions(result)
        return CapabilityResult(
            message=result.get("message") or "Delete request prepared.",
            actions=actions,
            data={
                "business_skill": "record_delete",
                "operation": "delete",
                "result": result,
            },
            requires_confirmation=any(action.get("requires_confirmation") for action in actions),
        )

    @property
    def service(self):
        if self._service is None:
            self._service = get_record_delete_service()
        return self._service


def build_actions(result):
    if not result.get("supported"):
        return []
    if result.get("stage") == "record_selection":
        return build_selection_actions(result)
    if result.get("ready"):
        return [build_delete_action(result), build_cancel_action(result.get("doctype"))]
    return [build_cancel_action(result.get("doctype"))]


def build_selection_actions(result):
    actions = []
    for option in result.get("options") or []:
        doctype = option.get("doctype")
        docname = option.get("docname")
        if not doctype or not docname:
            continue
        actions.append(
            {
                "type": "send_message",
                "label": f"Delete {format_choice_label(option)}",
                "payload": {"message": f"delete {doctype} {docname}"},
                "requires_confirmation": False,
                "auto_execute": False,
                "enabled": True,
            }
        )
    actions.append(build_cancel_action("Record"))
    return actions


def build_delete_action(result):
    doctype = result.get("doctype")
    docname = result.get("docname")
    return {
        "type": "delete",
        "label": f"Delete {doctype}",
        "method": DELETE_METHOD,
        "payload": {
            "doctype": doctype,
            "docname": docname,
        },
        "requires_confirmation": True,
        "auto_execute": False,
        "enabled": bool(result.get("ready")),
    }


def build_cancel_action(doctype):
    return {
        "type": "cancel_review",
        "label": "Cancel",
        "payload": {"doctype": doctype or "Record"},
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def format_choice_label(option):
    doctype = option.get("doctype") or "Record"
    docname = option.get("docname") or ""
    label = option.get("label") or docname
    if label.startswith(f"{doctype} "):
        label = label[len(doctype) + 1 :]
    return f"{doctype}: {label or docname}"
