from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.application.ai_assistant import generate_ai_response


class ReportsCapability(Capability):
    name = "reports"

    def handle(self, message, context, intent):
        ai_response = generate_ai_response(message=message, context=context, purpose="report planning")
        if ai_response and ai_response.get("success"):
            return CapabilityResult(
                message=ai_response["response_text"],
                actions=[
                    {
                        "type": "prepare_report",
                        "label": "Prepare report",
                        "requires_confirmation": False,
                    }
                ],
                data={
                    "read_only": True,
                    "ai": {
                        "provider": ai_response.get("provider"),
                        "model": ai_response.get("model"),
                        "latency": ai_response.get("latency"),
                    },
                },
            )

        return CapabilityResult(
            message="\n".join(
                [
                    "Report Request",
                    "I recognized this as a reporting request.",
                    "",
                    "Current Status",
                    "- I can prepare a report plan.",
                    "- Talisma OneCampus reads will still go through permission-aware services.",
                ]
            ),
            actions=[
                {
                    "type": "prepare_report",
                    "label": "Prepare report",
                    "requires_confirmation": False,
                }
            ],
            data={
                "read_only": True,
                "ai": ai_response if ai_response else {"success": False, "error": "AI provider not configured."},
            },
        )
