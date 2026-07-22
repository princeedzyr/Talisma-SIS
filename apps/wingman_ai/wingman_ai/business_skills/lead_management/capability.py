from wingman_ai.business_skills.lead_management.parser import detect_lead_operation
from wingman_ai.business_skills.lead_management.service import get_lead_management_service
from wingman_ai.capabilities.base import Capability, CapabilityResult
from wingman_ai.review_builder.workflow import build_cancel_action, build_create_action, build_creation_review_actions


class LeadManagementCapability(Capability):
    name = "lead_management"

    def __init__(self, service=None):
        self._service = service

    def handle(self, message, context, intent):
        result = self.service.handle_message(message=message, context=context, intent=intent)
        operation = result.get("operation") or detect_lead_operation(message, getattr(intent, "structured_intent", None))
        actions = build_actions(result, operation)
        return CapabilityResult(
            message=result.get("message") or "Lead Management request prepared.",
            actions=actions,
            data={
                "business_skill": "lead_management",
                "operation": operation,
                "result": result,
            },
            requires_confirmation=any(action.get("requires_confirmation") for action in actions),
        )

    @property
    def service(self):
        if self._service is None:
            self._service = get_lead_management_service()
        return self._service


def is_lead_management_request(message, intent=None, context=None):
    text = (message or "").lower()
    context_object = (context or {}).get("object") or {}
    structured = getattr(intent, "structured_intent", None) or {}
    entity = structured.get("detected_entity") or {}
    parameters = structured.get("extracted_parameters") or {}
    if context_object.get("doctype") == "Lead" and any(word in text for word in ("this", "current", "qualify", "convert", "summary", "summarize", "update", "change")):
        return True
    if context_object.get("route_type") == "Query Report" and "lead" in str(context_object.get("report_name") or "").lower():
        return True
    if entity.get("value") == "Lead" or parameters.get("business_entity") == "Lead":
        return True
    return "lead" in text or "leads" in text


def build_actions(result, operation):
    if operation == "record_type_mismatch":
        return [
            {
                "type": "navigate",
                "label": f"Open {match.get('doctype')} {match.get('name')}",
                "target": {
                    "label": f"{match.get('doctype')} {match.get('name')}",
                    "kind": "document",
                    "route": ["Form", match.get("doctype"), match.get("name")],
                    "doctype": match.get("doctype"),
                    "docname": match.get("name"),
                    "resolved": True,
                },
                "requires_confirmation": False,
                "auto_execute": False,
            }
            for match in (result.get("matches") or [])[:3]
            if match.get("doctype") and match.get("name")
        ]

    if operation == "create":
        parent_action = build_create_action(
            "Lead",
            label="Create Lead",
            method="wingman_ai.api.lead_management.create_lead",
            payload={"data": result.get("data") or {}},
            enabled=bool(result.get("ready")),
        )
        return build_creation_review_actions(result, parent_action)
    if operation == "update":
        return [
            {
                "type": "update",
                "label": "Update Lead",
                "method": "wingman_ai.api.lead_management.update_lead",
                "payload": {"lead_name": result.get("lead_name"), "data": result.get("data") or {}},
                "requires_confirmation": True,
                "auto_execute": False,
                "enabled": bool(result.get("ready")),
            }
        ]
    if operation == "convert":
        return [
            {
                "type": "create",
                "label": "Convert to Opportunity",
                "method": "wingman_ai.api.lead_management.convert_lead",
                "payload": {"lead_name": result.get("lead_name"), "execute": True},
                "requires_confirmation": True,
                "auto_execute": False,
                "enabled": bool(result.get("ready")),
            }
        ]
    return []


def review_control_actions(doctype):
    return [build_cancel_action(doctype)]
