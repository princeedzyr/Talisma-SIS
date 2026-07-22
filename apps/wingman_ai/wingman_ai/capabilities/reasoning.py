from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.application.ai_assistant import generate_ai_response
from wingman_ai.knowledge import build_fast_context_answer
from wingman_ai.services.document_summary import get_current_record_response, get_explicit_record_response


class ReasoningCapability(Capability):
    name = "reasoning"

    def handle(self, message, context, intent):
        record_response = get_explicit_record_response(message, context, intent=intent)
        if record_response:
            return CapabilityResult(
                message=record_response["message"],
                actions=[],
                data={
                    "read_only": True,
                    "traceable": True,
                    **record_response["data"],
                },
            )

        current_record_response = get_current_record_response(message, context, intent=intent)
        if current_record_response:
            return CapabilityResult(
                message=current_record_response["message"],
                actions=[],
                data={
                    "read_only": True,
                    "traceable": True,
                    **current_record_response["data"],
                },
            )

        fast_answer = build_fast_context_answer(message, context)
        if fast_answer:
            return CapabilityResult(
                message=fast_answer["message"],
                actions=[],
                data={
                    "read_only": True,
                    "traceable": True,
                    "response_mode": fast_answer["source"],
                },
            )

        ai_response = generate_ai_response(message=message, context=context, purpose="business reasoning")
        if ai_response and ai_response.get("success"):
            return CapabilityResult(
                message=ai_response["response_text"],
                actions=[],
                data={
                    "read_only": True,
                    "traceable": True,
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
                    "Reasoning Request",
                    "I treated this as a reasoning request.",
                    "",
                    "Current Status",
                    "- The local AI model did not respond within the fast-response window.",
                    "- No Talisma OneCampus data was changed.",
                    "",
                    "What You Can Do Next",
                    "- Ask a shorter, more specific question for a faster model response.",
                    "- Try a direct OneCampus command such as \"open students\" or \"open Liam Patel\".",
                ]
            ),
            actions=[],
            data={
                "read_only": True,
                "traceable": True,
                "ai": ai_response if ai_response else {"success": False, "error": "AI provider not configured."},
            },
        )
