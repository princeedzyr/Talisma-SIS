from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class IntentEntity:
    entity_type: str
    value: str
    label: str = None
    confidence: float = 0.0
    source: str = "rule"

    def to_dict(self):
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "label": self.label or self.value,
            "confidence": round(float(self.confidence), 3),
            "source": self.source,
        }


@dataclass
class IntentResult:
    intent_id: str
    intent_category: str
    detected_entity: dict = None
    entities: list = field(default_factory=list)
    extracted_parameters: dict = field(default_factory=dict)
    conversation_context: dict = field(default_factory=dict)
    confidence_score: float = 0.0
    requires_clarification: bool = False
    clarification_questions: list = field(default_factory=list)
    detected_language: str = "en"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    reasoning_notes: list = field(default_factory=list)
    fallback: dict = field(default_factory=dict)
    intent_version: str = "1.0.0"

    def to_dict(self):
        return {
            "intent_id": self.intent_id,
            "intent_category": self.intent_category,
            "detected_entity": self.detected_entity,
            "entities": self.entities,
            "extracted_parameters": self.extracted_parameters,
            "conversation_context": self.conversation_context,
            "confidence_score": round(float(self.confidence_score), 3),
            "requires_clarification": self.requires_clarification,
            "clarification_questions": self.clarification_questions,
            "detected_language": self.detected_language,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "reasoning_notes": self.reasoning_notes,
            "fallback": self.fallback,
            "intent_version": self.intent_version,
        }
