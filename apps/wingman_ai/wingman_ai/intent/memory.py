from wingman_ai.intent.parameters import extract_parameters


class ConversationMemoryResolver:
    def resolve(self, message, context):
        history = (context or {}).get("history") or []
        pending = find_pending_intent(history)
        if not pending:
            return {"pending_intent": None, "resolved_from_memory": False}

        resolved_parameters = dict(pending.get("extracted_parameters") or {})
        current_text = (message or "").strip()
        if current_text and is_short_answer(current_text):
            resolved_parameters.setdefault("name", current_text)

        return {
            "pending_intent": pending,
            "resolved_from_memory": bool(resolved_parameters != (pending.get("extracted_parameters") or {})),
            "resolved_parameters": resolved_parameters,
        }


def find_pending_intent(history):
    for item in reversed(history[-8:]):
        metadata = item.get("metadata") or {}
        intent_result = metadata.get("intent_result") or metadata.get("intent")
        if isinstance(intent_result, dict) and intent_result.get("requires_clarification"):
            return intent_result

        content = (item.get("content") or "").lower()
        role = item.get("role")
        if role == "assistant" and ("company name" in content or "customer" in content and "which" in content):
            return {
                "intent_id": "memory.pending",
                "intent_category": "Create",
                "extracted_parameters": {"business_entity": "Lead"},
                "requires_clarification": True,
                "clarification_questions": [item.get("content")],
            }
    return None


def is_short_answer(text):
    return 1 <= len(text.split()) <= 8 and len(text) <= 80
