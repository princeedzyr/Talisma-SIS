from wingman_ai.business_workflows.service import BusinessWorkflowService
from wingman_ai.capabilities.base import Capability


class BusinessWorkflowCapability(Capability):
    name = "business_workflow"

    def __init__(self, service=None):
        self.service = service or BusinessWorkflowService()

    def handle(self, message, context, intent):
        return self.service.handle_goal(message=message, context=context, intent=intent)
