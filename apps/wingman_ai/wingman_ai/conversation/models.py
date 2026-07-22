from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class ConversationTurn:
    message: str
    user: str = None
    conversation_id: str = None
    turn_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: dict = field(default_factory=dict)
    intent: str = None
    response: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "started_at": self.started_at,
            "user": self.user,
            "message": self.message,
            "context": self.context,
            "intent": self.intent,
            "response": self.response,
        }


@dataclass
class Conversation:
    conversation_id: str
    user: str = None
    metadata: dict = field(default_factory=dict)
    status: str = "active"
    messages: list = field(default_factory=list)
