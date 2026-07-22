from wingman_ai.application.intent_router import detect_intent as detect_application_intent
from wingman_ai.application.orchestrator import get_orchestrator


def detect_intent(message):
    return detect_application_intent(message).name


def build_response(message, context, user=None):
    return get_orchestrator().handle_message(message, raw_context=context, user=user)
