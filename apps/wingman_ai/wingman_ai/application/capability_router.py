from wingman_ai.capabilities.crm import CRMCapability
from wingman_ai.capabilities.email_assistant import EmailAssistantCapability
from wingman_ai.capabilities.general import GeneralCapability
from wingman_ai.capabilities.navigation import NavigationCapability
from wingman_ai.capabilities.process_advisor import ProcessAdvisorCapability, is_process_advisory_request
from wingman_ai.capabilities.reasoning import ReasoningCapability
from wingman_ai.capabilities.reports import ReportsCapability
from wingman_ai.capabilities.sales import SalesCapability
from wingman_ai.capabilities.student_group_hold import StudentGroupHoldCapability, is_student_group_hold_request
from wingman_ai.capabilities.workflow_builder import WorkflowBuilderCapability, is_workflow_builder_request
from wingman_ai.business_workflows.capability import BusinessWorkflowCapability
from wingman_ai.business_skills.record_creation.capability import RecordCreationCapability
from wingman_ai.business_skills.record_delete.capability import RecordDeleteCapability
from wingman_ai.business_skills.record_update.capability import RecordUpdateCapability
from wingman_ai.workflow_engine.registry import get_runtime_workflow_registry


CAPABILITIES = {
    "business_workflow": BusinessWorkflowCapability(),
    "crm": CRMCapability(),
    "create": RecordCreationCapability(),
    "delete": RecordDeleteCapability(),
    "email": EmailAssistantCapability(),
    "general": GeneralCapability(),
    "navigation": NavigationCapability(),
    "process_advisor": ProcessAdvisorCapability(),
    "reasoning": ReasoningCapability(),
    "reports": ReportsCapability(),
    "sales": SalesCapability(),
    "student_group_hold": StudentGroupHoldCapability(),
    "update": RecordUpdateCapability(),
    "workflow": WorkflowBuilderCapability(),
}


def route_capability(intent, message, context):
    if is_student_group_hold_request(message):
        capability_name = "student_group_hold"
    elif is_pending_business_workflow_control(message, context=context):
        capability_name = "business_workflow"
    elif is_workflow_builder_request(message, intent=intent):
        capability_name = "workflow"
    elif is_process_advisory_request(message, intent=intent):
        capability_name = "process_advisor"
    else:
        capability_name = "business_workflow" if is_business_workflow_operation(intent, message, context=context) else ("create" if is_create_operation(intent, message) else intent.capability)
    capability = CAPABILITIES.get(capability_name) or CAPABILITIES["general"]
    return capability.handle(message=message, context=context, intent=intent)


def is_create_operation(intent, message):
    structured = getattr(intent, "structured_intent", None) or {}
    if structured.get("intent_category") == "Create":
        return True

    text = str(message or "").strip().lower()
    return any(
        text == keyword or text.startswith(f"{keyword} ")
        for keyword in ("create", "new", "add", "make", "register", "draft")
    )


def is_business_workflow_operation(intent, message, context=None):
    if not is_create_operation(intent, message):
        return False
    if (context or {}).get("pending_create_draft"):
        return False

    return get_runtime_workflow_registry().supports_message(message=message, intent=intent, operation="create")


def is_pending_business_workflow_control(message, context=None):
    if not (context or {}).get("pending_workflow_session"):
        return False
    text = " ".join(str(message or "").strip().lower().split())
    return (
        text == "start"
        or text.startswith("start workflow")
        or text.startswith("begin workflow")
        or text.startswith("create opportunity party ")
        or text.startswith("resume opportunity workflow")
    ) or text in {
        "cancel",
        "cancel workflow",
        "stop workflow",
        "abort workflow",
        "never mind",
        "nevermind",
    }
