from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.business_skills.lead_management.capability import LeadManagementCapability, is_lead_management_request
from wingman_ai.knowledge import build_fast_context_answer
from wingman_ai.prompts import get_prompt
from wingman_ai.services.document_summary import get_current_record_response, get_explicit_record_response


WRITE_KEYWORDS = ("create", "new", "add", "make", "register", "update", "change", "edit", "delete", "remove")


class CRMCapability(Capability):
    name = "crm"

    def __init__(self, lead_capability=None):
        self.lead_capability = lead_capability or LeadManagementCapability()

    def handle(self, message, context, intent):
        prompt = get_prompt("crm")
        requires_confirmation = getattr(intent, "requires_write_review", False) or is_write_request(message)

        record_response = get_explicit_record_response(message, context, intent=intent)
        if record_response and should_use_explicit_record_before_lead_skill(record_response):
            return self.make_record_result(record_response, prompt)

        if is_lead_management_request(message, intent=intent, context=context):
            return self.lead_capability.handle(message=message, context=context, intent=intent)

        if record_response:
            return self.make_record_result(record_response, prompt)

        current_record_response = get_current_record_response(message, context, intent=intent)
        if current_record_response:
            return CapabilityResult(
                message=current_record_response["message"],
                actions=[],
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    **current_record_response["data"],
                },
            )

        fast_answer = None if requires_confirmation else build_fast_context_answer(message, context)
        if fast_answer:
            return CapabilityResult(
                message=fast_answer["message"],
                actions=[],
                data={
                    "pipeline": "orchestrator",
                    "prompt_version": prompt["version"],
                    "response_mode": fast_answer["source"],
                },
            )

        return CapabilityResult(
            message=(
                f"{context['summary']}\n\n"
                "I recognized this as a CRM request. I will preserve the existing Wingman CRM behavior "
                "behind review cards before creating or updating Talisma OneCampus records."
            ),
            actions=[
                {
                    "type": "prepare_crm_action",
                    "label": "Prepare CRM review",
                    "requires_confirmation": requires_confirmation,
                }
            ],
            data={
                "supported_doctypes": ["Lead", "Customer", "Contact", "Opportunity"],
                "write_review_required": requires_confirmation,
                "prompt_version": prompt["version"],
            },
            requires_confirmation=requires_confirmation,
        )

    def make_record_result(self, record_response, prompt):
        return CapabilityResult(
            message=record_response["message"],
            actions=[],
            data={
                "pipeline": "orchestrator",
                "prompt_version": prompt["version"],
                **record_response["data"],
            },
        )


def is_write_request(message):
    text = (message or "").lower()
    return any(keyword in text for keyword in WRITE_KEYWORDS)


def should_use_explicit_record_before_lead_skill(record_response):
    data = (record_response or {}).get("data") or {}
    explicit = data.get("explicit_record") or {}
    doctype = explicit.get("doctype")
    kind = explicit.get("kind")
    if doctype and doctype != "Lead":
        return True
    return kind in ("document_not_found", "navigation_not_found") and doctype != "Lead"
