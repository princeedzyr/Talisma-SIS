from wingman_ai.application.response_builder import build_api_response, build_error_response
from wingman_ai.context.service import ContextService
from wingman_ai.conversation.service import ConversationService
from wingman_ai.conversation.state_manager import ConversationStateManager
from wingman_ai.execution.service import ExecutionService
from wingman_ai.exception_intelligence import get_exception_interceptor
from wingman_ai.logging.correlation import new_correlation_id
from wingman_ai.planner.service import PlannerService
from wingman_ai.security.input_guard import InputValidationError, validate_user_message
from wingman_ai.security.prompt_guard import assert_prompt_is_safe
from wingman_ai.security.rate_limiter import check_rate_limit


class WingmanOrchestrator:
    def __init__(self):
        self.context_service = ContextService()
        self.conversation_service = ConversationService()
        self.state_manager = ConversationStateManager()
        self.planner_service = PlannerService()
        self.execution_service = ExecutionService()

    def handle_message(self, message, raw_context=None, user=None, conversation_id=None, request_id=None):
        correlation_id = new_correlation_id()

        try:
            text = validate_user_message(message)
        except InputValidationError as exc:
            return build_error_response(str(exc), code="validation_error")

        rate_limit = check_rate_limit(user, conversation_id=conversation_id, request_id=request_id)
        if not rate_limit.get("allowed"):
            response = build_error_response(rate_limit.get("message"), code="rate_limited")
            response["retry_after_seconds"] = rate_limit.get("retry_after_seconds")
            return response

        prompt_guard = assert_prompt_is_safe(text)
        if not prompt_guard.get("safe"):
            return build_error_response(prompt_guard.get("message"), code="prompt_guard_blocked")

        context = {}
        turn = None
        try:
            context = self.context_service.build(raw_context=raw_context, user=user, conversation_id=conversation_id)
            context.setdefault("raw", {})["message"] = text
            turn = self.conversation_service.start_turn(message=text, user=user, context=context)
            context["conversation_id"] = turn.conversation_id
            plan = self.planner_service.create_plan(message=text, context=context)
            result = self.execution_service.execute_plan(plan)
            context["conversation_state"] = self.state_manager.complete_turn(context, plan.intent, result)
            response = build_api_response(result=result, intent=plan.intent, context=context, user=user)
            response["correlation_id"] = correlation_id
            self.conversation_service.complete_turn(turn, response)
            return response
        except Exception as exc:
            diagnostic = get_exception_interceptor().failure_response(
                exc,
                context={
                    **(context or {}),
                    "operation": "conversation",
                    "user": user,
                    "conversation_id": (context or {}).get("conversation_id") or conversation_id,
                    "message": text,
                    "failure_stage": "Conversation orchestration",
                    "component": "WingmanOrchestrator",
                    "erpnext_api": "wingman_ai.api.chat.send",
                },
            )
            response = build_error_response(diagnostic["message"], code="wingman_exception_diagnostic")
            response["exception_diagnostic"] = diagnostic["exception_diagnostic"]
            response["actions"] = diagnostic["exception_diagnostic"].get("actions") or []
            response["correlation_id"] = correlation_id
            if context.get("conversation_id"):
                response["conversation_id"] = context.get("conversation_id")
            if turn:
                self.conversation_service.complete_turn(turn, response)
            return response


_ORCHESTRATOR = WingmanOrchestrator()


def get_orchestrator():
    return _ORCHESTRATOR
