from wingman_ai.intelligence.service import get_wingman_intelligence_service


def build_api_response(result, intent, context, user=None):
    payload = result.to_dict()
    executed_capability = ((payload.get("data") or {}).get("executed_capability") or intent.capability)
    payload.update(
        {
            "intent": intent.name,
            "capability": executed_capability,
            "intent_capability": intent.capability,
            "confidence": intent.confidence,
            "context": context.get("object"),
            "context_summary": context.get("summary"),
            "conversation_state": context.get("conversation_state"),
            "conversation_orchestration": ((context.get("conversation_state") or {}).get("unified_state") or context.get("conversation_orchestration")),
            "conversation_id": context.get("conversation_id"),
            "user": user,
            "intent_details": getattr(intent, "structured_intent", None),
        }
    )
    payload["intelligence"] = get_wingman_intelligence_service().build(payload=payload, intent=intent, context=context, user=user)
    return payload


def build_error_response(message, code="validation_error"):
    payload = {
        "status": "error",
        "code": code,
        "message": message,
    }
    payload["intelligence"] = get_wingman_intelligence_service().build(payload=payload)
    return payload
