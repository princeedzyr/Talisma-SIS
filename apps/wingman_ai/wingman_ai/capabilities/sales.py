from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.services.document_summary import get_current_record_response, get_explicit_record_response


class SalesCapability(Capability):
    name = "sales"

    def handle(self, message, context, intent):
        record_response = get_explicit_record_response(message, context, intent=intent)
        if record_response:
            return CapabilityResult(
                message=record_response["message"],
                actions=[],
                data={
                    "pipeline": "orchestrator",
                    **record_response["data"],
                },
            )

        current_record_response = get_current_record_response(message, context, intent=intent)
        if current_record_response:
            return CapabilityResult(
                message=current_record_response["message"],
                actions=[],
                data={
                    "pipeline": "orchestrator",
                    **current_record_response["data"],
                },
            )

        return CapabilityResult(
            message="\n".join(
                [
                    "Sales Request",
                    "I recognized this as a sales document request.",
                    "",
                    "What You Can Do Next",
                    "- Open a specific Sales Order, Quotation, Opportunity, Delivery Note, or Invoice.",
                    "- Ask for its details to fetch the filled fields through Talisma OneCampus permissions.",
                ]
            ),
            actions=[],
            data={"supported_doctypes": ["Opportunity", "Quotation", "Sales Order", "Delivery Note"]},
        )
