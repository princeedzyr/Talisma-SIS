import json

try:
    import frappe
except ImportError:
    class _FrappeStub:
        @staticmethod
        def whitelist():
            def decorator(fn):
                return fn

            return decorator

        @staticmethod
        def session():
            return None

    frappe = _FrappeStub()

from wingman_ai.api.exception_guard import guarded_api_call
from wingman_ai.business_workflows.service import BusinessWorkflowService


@frappe.whitelist()
def resume_after_dependency(workflow_id=None, dependency_doctype=None, entity=None, opportunity_data=None, business_goal=None, conversation_id=None):
    user = current_user()

    def run():
        return BusinessWorkflowService().resume_after_dependency(
            workflow_id=workflow_id,
            dependency_doctype=dependency_doctype,
            entity=entity,
            opportunity_data=parse_json(opportunity_data, {}),
            business_goal=business_goal,
            conversation_id=conversation_id,
            user=user,
        )

    return guarded_api_call(
        "business_workflow_resume",
        run,
        doctype="Opportunity",
        user=user,
        data=parse_json(opportunity_data, {}) if opportunity_data else {},
        component="BusinessWorkflowAPI",
        erpnext_api="wingman_ai.api.business_workflows.resume_after_dependency",
    )


@frappe.whitelist()
def complete_opportunity_goal(workflow_id=None, business_goal=None, opportunity_data=None, conversation_id=None):
    user = current_user()

    def run():
        return BusinessWorkflowService().complete_opportunity_goal(
            workflow_id=workflow_id,
            business_goal=business_goal,
            opportunity_data=parse_json(opportunity_data, {}),
            conversation_id=conversation_id,
            user=user,
        )

    return guarded_api_call(
        "business_workflow_complete",
        run,
        doctype="Opportunity",
        user=user,
        data=parse_json(opportunity_data, {}) if opportunity_data else {},
        component="BusinessWorkflowAPI",
        erpnext_api="wingman_ai.api.business_workflows.complete_opportunity_goal",
    )


def parse_json(value, default=None):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def current_user():
    session = getattr(frappe, "session", None)
    return getattr(session, "user", None) or "Guest"
