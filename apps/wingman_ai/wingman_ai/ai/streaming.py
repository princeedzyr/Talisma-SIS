from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class StreamEvent:
    event_type: str
    data: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "data": self.data,
            "created_at": self.created_at,
        }


class StreamController:
    def __init__(self):
        self.cancelled = False
        self.events = []

    def cancel(self):
        self.cancelled = True
        self.emit("cancelled")

    def emit(self, event_type, **data):
        event = StreamEvent(event_type=event_type, data=data)
        self.events.append(event)
        return event.to_dict()

    def progress(self, message=None, **data):
        return self.emit("progress", message=message, **data)
