from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.prompts import get_prompt
from wingman_ai.workflow_builder.service import WorkflowSetupService, build_review_actions, detect_workflow_document_type


class WorkflowBuilderCapability(Capability):
    name = "workflow"

    def __init__(self, service=None):
        self._service = service

    def handle(self, message, context, intent):
        prompt = get_prompt("workflow")
        if is_supported_workflow_request(message):
            review = self.service.prepare_review_for_message(message)
            return CapabilityResult(
                message=review["message"],
                actions=build_review_actions(review["definition"], review["validation"]),
                data={
                    "executed_capability": "workflow",
                    "business_skill": "workflow_builder",
                    "operation": "create_workflow",
                    "write_review_required": True,
                    "prompt_version": prompt["version"],
                    "result": review,
                },
                requires_confirmation=review["ready"],
            )

        return CapabilityResult(
            message="\n".join(
                [
                    "Workflow Request",
                    "I recognized this as a workflow request, but I need the document type and approval path before I can prepare it safely.",
                    "",
                    "Current Status",
                    "- No Talisma OneCampus data has been changed.",
                    "- Try a specific request like \"create task approval workflow\" or \"create leave approval workflow\".",
                ]
            ),
            actions=[
                {
                    "type": "send_message",
                    "label": "Create Task Approval Workflow",
                    "payload": {"message": "create task approval workflow"},
                    "requires_confirmation": False,
                }
            ],
            data={"write_review_required": True, "prompt_version": prompt["version"]},
            requires_confirmation=True,
        )

    @property
    def service(self):
        if self._service is None:
            self._service = WorkflowSetupService()
        return self._service


def is_workflow_builder_request(message, intent=None):
    text = normalize(message)
    if not text:
        return False
    if is_supported_workflow_request(text):
        return True
    category = ((getattr(intent, "structured_intent", None) or {}).get("intent_category") or "").lower()
    return "workflow" in text and category in {"create", "recommend", "explain", "conversation", "unknown"}


def is_task_approval_workflow_request(message):
    text = normalize(message)
    return "workflow" in text and "task" in text


def is_leave_approval_workflow_request(message):
    text = normalize(message)
    return "workflow" in text and "leave" in text


def is_supported_workflow_request(message):
    text = normalize(message)
    return (
        is_task_approval_workflow_request(text)
        or is_leave_approval_workflow_request(text)
        or ("workflow" in text and bool(detect_workflow_document_type(text)))
    )


def normalize(value):
    return " ".join(str(value or "").strip().lower().split())
