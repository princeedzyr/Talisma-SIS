from wingman_ai.business_skills.record_creation.service import get_record_creation_service
from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.review_builder.workflow import build_cancel_action, build_create_action, build_creation_review_actions


class RecordCreationCapability(Capability):
    name = "create"

    def __init__(self, service=None):
        self._service = service

    def handle(self, message, context, intent):
        result = self.service.handle_message(message=message, context=context, intent=intent)
        actions = build_actions(result)
        direct_curriculum_create = any(action.get("wingman_direct_create") is True for action in actions)
        response_message = result.get("message") or "Record creation request prepared."
        if direct_curriculum_create:
            program = (result.get("data") or {}).get("program")
            response_message = "\n".join(
                [
                    "Creating Curriculum Version",
                    (
                        f"Wingman is creating this Curriculum Version and linking it to {program}."
                        if program
                        else "Wingman is creating this Curriculum Version."
                    ),
                ]
            )
        return CapabilityResult(
            message=response_message,
            actions=actions,
            data={
                "business_skill": "record_creation",
                "operation": "create",
                "result": result,
            },
            requires_confirmation=any(action.get("requires_confirmation") for action in actions),
        )

    @property
    def service(self):
        if self._service is None:
            self._service = get_record_creation_service()
        return self._service


def build_actions(result):
    if not result.get("supported"):
        return []

    doctype = result.get("doctype")
    parent_action = build_create_action(doctype, data=result.get("data") or {}, enabled=bool(result.get("ready")))
    actions = build_creation_review_actions(result, parent_action)
    if (
        doctype == "Talisma Curriculum Version"
        and result.get("ready")
        and (result.get("setup_state") or {}).get("curriculum_requirements_reviewed")
        and bool((result.get("data") or {}).get("requirements"))
    ):
        for action in actions:
            if action.get("type") == "create":
                action["label"] = "Creating Curriculum Version"
                action["requires_confirmation"] = False
                action["auto_execute"] = True
                action["wingman_direct_create"] = True
    if result.get("resume_action"):
        actions = attach_resume_action(actions, result.get("resume_action"))
    setup_actions = result.get("setup_actions") or []
    if setup_actions and result.get("next_missing_field") and not result.get("ready"):
        cancel_actions = [action for action in actions if action.get("type") == "cancel_review"]
        primary_actions = [action for action in actions if action.get("type") != "cancel_review"]
        return primary_actions + setup_actions + cancel_actions
    return actions


def review_control_actions(doctype):
    return [build_cancel_action(doctype)]


def attach_resume_action(actions, resume_action):
    updated = []
    for action in actions or []:
        item = dict(action)
        if item.get("type") == "create":
            payload = dict(item.get("payload") or {})
            payload["resume_action"] = resume_action
            item["payload"] = payload
        updated.append(item)
    return updated
