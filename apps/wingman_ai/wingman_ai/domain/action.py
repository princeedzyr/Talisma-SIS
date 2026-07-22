from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlannedAction:
    action_type: str
    label: str
    payload: dict = field(default_factory=dict)
    requires_confirmation: bool = False
    auto_execute: bool = False

    def to_dict(self):
        data = {
            "type": self.action_type,
            "label": self.label,
            "requires_confirmation": self.requires_confirmation,
            "auto_execute": self.auto_execute,
        }
        data.update(self.payload)
        return data

