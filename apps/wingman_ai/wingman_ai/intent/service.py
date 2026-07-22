from uuid import uuid4

from wingman_ai.config.settings import get_wingman_settings
from wingman_ai.intent.clarification import ClarificationEngine
from wingman_ai.intent.classifier import IntentClassifier
from wingman_ai.intent.entities import EntityExtractor
from wingman_ai.intent.memory import ConversationMemoryResolver
from wingman_ai.intent.parameters import extract_parameters
from wingman_ai.intent.registry import supported_entities, supported_intents
from wingman_ai.intent.schema import IntentResult
from wingman_ai.logging.service import log_error, log_info, log_warning


MEMORY_SAFE_CATEGORIES = {"Greeting", "Goodbye", "Help", "Conversation", "Navigate"}


class IntentRecognitionService:
    def __init__(self, extractor=None, classifier=None, clarification=None, memory=None):
        self.extractor = extractor or EntityExtractor()
        self.classifier = classifier or IntentClassifier()
        self.clarification = clarification or ClarificationEngine()
        self.memory = memory or ConversationMemoryResolver()

    def parse(self, message, context=None):
        settings = get_wingman_settings()
        context = context or {}
        trace_id = uuid4().hex
        try:
            return self._parse(message=message, context=context, settings=settings, trace_id=trace_id)
        except Exception as exc:
            log_error("Intent parsing failed", error_type=type(exc).__name__, trace_id=trace_id)
            return build_unknown_intent(settings=settings, trace_id=trace_id, reason="Intent engine error.")

    def _parse(self, message, context, settings, trace_id):
        text = (message or "").strip()
        language = detect_language(text, settings.intent_supported_languages)
        entities = self.extractor.extract(text)
        classification = self.classifier.classify(text, entities=entities)
        parameters = extract_parameters(text, entities)
        memory_context = (
            {"pending_intent": None, "resolved_from_memory": False}
            if classification["intent_category"] in MEMORY_SAFE_CATEGORIES
            else self.memory.resolve(text, context)
        )

        if memory_context.get("resolved_from_memory"):
            pending = memory_context.get("pending_intent") or {}
            classification["intent_category"] = pending.get("intent_category") or classification["intent_category"]
            parameters.update(memory_context.get("resolved_parameters") or {})
            classification["confidence_score"] = max(classification["confidence_score"], 0.82)
            classification["reasoning_notes"].append("Resolved missing parameter from conversation memory.")

        detected_entity = first_business_entity(entities)
        clarification = self.clarification.evaluate(
            message=text,
            intent_category=classification["intent_category"],
            parameters=parameters,
            confidence=classification["confidence_score"],
            settings=settings,
        )
        fallback = build_fallback(classification["intent_category"], classification["confidence_score"], settings)

        result = IntentResult(
            intent_id=build_intent_id(classification["intent_category"]),
            intent_category=classification["intent_category"],
            detected_entity=detected_entity,
            entities=entities,
            extracted_parameters=parameters,
            conversation_context=build_conversation_context(context, memory_context),
            confidence_score=classification["confidence_score"],
            requires_clarification=clarification["requires_clarification"],
            clarification_questions=clarification["clarification_questions"],
            detected_language=language,
            trace_id=trace_id,
            reasoning_notes=classification["reasoning_notes"],
            fallback=fallback,
            intent_version=settings.intent_version,
        )

        log_intent_result(result)
        return result.to_dict()

    def explain(self, message, context=None):
        parsed = self.parse(message=message, context=context)
        return {
            "intent": parsed,
            "explanation": {
                "summary": f"Detected {parsed['intent_category']} with confidence {parsed['confidence_score']}.",
                "clarification": parsed["clarification_questions"],
                "notes": parsed["reasoning_notes"],
            },
        }

    def supported(self):
        settings = get_wingman_settings()
        return {
            "intent_version": settings.intent_version,
            "intents": supported_intents(),
            "entities": supported_entities(),
            "languages": settings.intent_supported_languages,
            "thresholds": {
                "confidence": settings.intent_confidence_threshold,
                "fallback": settings.intent_fallback_threshold,
            },
        }

    def health(self):
        settings = get_wingman_settings()
        return {
            "status": "ok",
            "engine": "deterministic_intent_engine",
            "intent_version": settings.intent_version,
            "feature_flags": settings.intent_feature_flags,
        }


def build_unknown_intent(settings, trace_id, reason):
    result = IntentResult(
        intent_id="intent.unknown",
        intent_category="Unknown",
        confidence_score=0.0,
        requires_clarification=True,
        clarification_questions=["Could you rephrase the request or choose a clearer business action?"],
        detected_language="en",
        trace_id=trace_id,
        reasoning_notes=[reason],
        fallback={"active": True, "reason": reason},
        intent_version=settings.intent_version,
    )
    return result.to_dict()


def build_intent_id(category):
    return f"intent.{str(category or 'Unknown').lower()}"


def first_business_entity(entities):
    for entity in entities or []:
        if entity.get("entity_type") == "BusinessEntity":
            return entity
    return entities[0] if entities else None


def build_conversation_context(context, memory_context):
    return {
        "conversation_id": (context or {}).get("conversation_id"),
        "current_route": ((context or {}).get("object") or {}).get("route"),
        "current_doctype": ((context or {}).get("object") or {}).get("doctype"),
        "current_docname": ((context or {}).get("object") or {}).get("docname"),
        "pending_intent": memory_context.get("pending_intent"),
        "resolved_from_memory": memory_context.get("resolved_from_memory", False),
    }


def build_fallback(category, confidence, settings):
    active = category == "Unknown" or confidence < settings.intent_fallback_threshold
    return {
        "active": active,
        "reason": "low_confidence_or_unknown" if active else None,
    }


def detect_language(text, supported_languages):
    if not text:
        return "en"
    if any(ord(char) > 127 for char in text):
        return "unknown"
    return "en" if "en" in supported_languages else supported_languages[0]


def log_intent_result(result):
    payload = result.to_dict()
    log_info(
        "Intent detected",
        intent_category=payload["intent_category"],
        confidence=payload["confidence_score"],
        requires_clarification=payload["requires_clarification"],
        fallback=payload["fallback"].get("active"),
        trace_id=payload["trace_id"],
    )
    if payload["fallback"].get("active"):
        log_warning("Intent fallback selected", intent_category=payload["intent_category"], trace_id=payload["trace_id"])
