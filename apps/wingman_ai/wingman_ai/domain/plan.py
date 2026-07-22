from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionPlan:
    intent: object
    capability: str
    message: str
    context: dict
    actions: list = field(default_factory=list)

    @property
    def requires_confirmation(self):
        return bool(getattr(self.intent, "requires_write_review", False))

