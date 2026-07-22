from dataclasses import dataclass, field


@dataclass
class CapabilityResult:
    message: str
    status: str = "success"
    actions: list = field(default_factory=list)
    data: dict = field(default_factory=dict)
    requires_confirmation: bool = False

    def to_dict(self):
        return {
            "status": self.status,
            "message": self.message,
            "actions": self.actions,
            "data": self.data,
            "requires_confirmation": self.requires_confirmation,
        }


class Capability:
    name = "base"

    def handle(self, message, context, intent):
        raise NotImplementedError

