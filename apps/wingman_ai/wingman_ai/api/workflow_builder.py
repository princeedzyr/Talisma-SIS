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

    frappe = _FrappeStub()

from wingman_ai.api.exception_guard import guarded_api_call
from wingman_ai.workflow_builder.service import WorkflowSetupService, build_task_approval_definition


@frappe.whitelist()
def create_workflow(definition=None):
    user = current_user()

    def run():
        service = WorkflowSetupService()
        parsed_definition = parse_json(definition, build_task_approval_definition())
        return service.execute_definition(parsed_definition, user=user)

    return guarded_api_call(
        "create_workflow",
        run,
        doctype="Workflow",
        user=user,
        data=parse_json(definition, {}),
        component="WorkflowBuilderAPI",
        erpnext_api="wingman_ai.api.workflow_builder.create_workflow",
    )


def current_user():
    return getattr(getattr(frappe, "session", None), "user", None)


def parse_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
