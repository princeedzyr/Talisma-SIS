from wingman_ai.application.intent_router import detect_intent
from wingman_ai.domain.plan import ActionPlan


class PlannerService:
    def create_plan(self, message, context):
        intent = detect_intent(message, context=context)
        return ActionPlan(
            intent=intent,
            capability=intent.capability,
            message=message,
            context=context,
        )
