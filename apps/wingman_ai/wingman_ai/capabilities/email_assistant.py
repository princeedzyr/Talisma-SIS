from wingman_ai.capabilities.base import Capability, CapabilityResult


class EmailAssistantCapability(Capability):
    name = "email"

    def handle(self, message, context, intent):
        return CapabilityResult(
            message="\n".join(
                [
                    "Communication Request",
                    "I recognized this as an email or communication request.",
                    "",
                    "Current Status",
                    "- Wingman will draft first.",
                    "- Sending will require explicit confirmation.",
                ]
            ),
            actions=[
                {
                    "type": "draft_email",
                    "label": "Draft email",
                    "requires_confirmation": True,
                }
            ],
            data={"write_review_required": True},
            requires_confirmation=True,
        )
