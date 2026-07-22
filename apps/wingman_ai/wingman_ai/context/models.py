from dataclasses import dataclass, field


@dataclass
class WingmanContext:
    current_user: str = None
    current_workspace: str = None
    conversation_id: str = None
    current_erp_context: dict = field(default_factory=dict)
    current_module: str = None
    variables: dict = field(default_factory=dict)
    conversation_history: list = field(default_factory=list)

    def to_dict(self):
        return {
            "current_user": self.current_user,
            "current_workspace": self.current_workspace,
            "conversation_id": self.conversation_id,
            "current_erp_context": self.current_erp_context,
            "current_module": self.current_module,
            "variables": self.variables,
            "conversation_history": self.conversation_history,
        }
