from dataclasses import dataclass
import re

from wingman_ai.intent.service import IntentRecognitionService


@dataclass(frozen=True)
class Intent:
    name: str
    capability: str
    confidence: float
    requires_write_review: bool = False
    structured_intent: dict = None


CRM_ENTITIES = {
    "Address",
    "Campaign",
    "Contact",
    "Customer",
    "Customer Group",
    "Lead",
    "Lead Source",
    "Opportunity",
    "Sales Person",
    "Territory",
}
SALES_ENTITIES = {"Quotation", "Sales Order", "Invoice", "Payment", "Sales Invoice", "Delivery Note", "Payment Entry"}
CREATE_CAPABILITY_ENTITIES = {
    "Address",
    "Asset",
    "Brand",
    "Campaign",
    "Company",
    "Contact",
    "Course",
    "Customer",
    "Customer Group",
    "Delivery Note",
    "Department",
    "Employee",
    "Invoice",
    "Issue",
    "Item",
    "Item Group",
    "Journal Entry",
    "Lead",
    "Lead Source",
    "Opportunity",
    "Payment",
    "Payment Entry",
    "Patient",
    "Program",
    "Project",
    "Purchase Invoice",
    "Purchase Order",
    "Purchase Receipt",
    "Quotation",
    "Sales Invoice",
    "Sales Order",
    "Sales Person",
    "Student",
    "Supplier",
    "Task",
    "Territory",
    "UOM",
    "User",
    "Warehouse",
}
WRITE_CATEGORIES = {"Create", "Update", "Delete"}
REASONING_CATEGORIES = {"Explain", "Summarize", "Compare", "Recommend"}


def detect_intent(message, context=None):
    structured = IntentRecognitionService().parse(message=message, context=context or {})
    category = structured.get("intent_category") or "Unknown"
    entity = structured.get("detected_entity") or {}
    entity_value = entity.get("value")

    return Intent(
        name=category.lower(),
        capability=map_capability(category, entity_value, context=context, message=message),
        confidence=structured.get("confidence_score", 0.0),
        requires_write_review=category in WRITE_CATEGORIES,
        structured_intent=structured,
    )


def map_capability(category, entity_value=None, context=None, message=None):
    if should_continue_pending_create(category, context=context):
        return "create"
    if should_continue_pending_update(category, context=context):
        return "update"
    if category == "Create":
        return "create"
    if category == "Navigate":
        return "navigation"
    if category in ("Greeting", "Goodbye", "Help", "Conversation", "Unknown"):
        return "general"
    context_object = ((context or {}).get("object") or {}) if isinstance(context, dict) else {}
    if context_object.get("doctype") == "Lead" and is_lead_business_action(message):
        return "crm"
    if category == "Update":
        return "update"
    if category == "Delete":
        return "delete"
    if context_object.get("doctype") == "Lead":
        return "crm"
    if context_object.get("route_type") == "Query Report" and "lead" in str(context_object.get("report_name") or "").lower():
        return "crm"
    if entity_value in CRM_ENTITIES:
        return "crm"
    if entity_value in SALES_ENTITIES:
        return "sales"
    if category in REASONING_CATEGORIES:
        return "reasoning"
    if category == "Search" or category == "List":
        return "navigation"
    return "general"


def is_lead_business_action(message):
    text = str(message or "").lower()
    return any(word in text for word in ("qualify", "qualification", "convert"))


def should_continue_pending_create(category, context=None):
    context = context or {}
    draft = context.get("pending_create_draft")
    if not draft:
        return False

    raw_message = str(context.get("raw", {}).get("message") or "")
    text = raw_message.strip().lower()
    if not text:
        return False
    if text in {"cancel", "cancel draft", "stop", "never mind", "nevermind"}:
        return True
    if pending_field_accepts_text(text, draft):
        return True
    if category in ("Navigate", "Greeting", "Goodbye", "Help"):
        return False
    if starts_with_new_command(text):
        return False

    next_field = draft.get("next_field") or {}
    label = str(next_field.get("label") or next_field.get("fieldname") or "").lower()
    if label and label in text:
        return True
    if "@" in text or re.search(r"\d", text):
        return True
    return 1 <= len(text.split()) <= 12


def should_continue_pending_update(category, context=None):
    context = context or {}
    draft = context.get("pending_update_draft")
    if not draft:
        return False

    raw_message = str(context.get("raw", {}).get("message") or "")
    text = raw_message.strip().lower()
    if not text:
        return False
    if text in {"cancel", "cancel update", "stop", "never mind", "nevermind"}:
        return True
    if pending_field_accepts_text(text, draft):
        return True
    if category in ("Navigate", "Greeting", "Goodbye", "Help"):
        return False
    if starts_with_new_command(text):
        return False
    return 1 <= len(text.split()) <= 16 or "@" in text or re.search(r"\d", text)


def starts_with_new_command(text):
    return any(
        text.startswith(prefix)
        for prefix in (
            "open ",
            "go to ",
            "navigate ",
            "navigae ",
            "show ",
            "list ",
            "search ",
            "find ",
            "tell me ",
            "summarize ",
            "explain ",
            "update ",
            "change ",
            "delete ",
            "remove ",
            "create ",
            "new ",
            "add ",
        )
    )


def pending_field_accepts_text(text, draft):
    field = (draft or {}).get("next_field") or (draft or {}).get("next_missing_field") or {}
    if not field:
        return False
    normalized = normalize_text(text)
    if not normalized:
        return False

    for choice in field.get("choices") or []:
        if normalized in {normalize_text(choice.get("value")), normalize_text(choice.get("label"))}:
            return True

    options = field.get("options")
    if isinstance(options, (list, tuple)):
        option_values = options
    else:
        option_values = str(options or "").replace(",", "\n").splitlines()
    return any(normalized == normalize_text(option) for option in option_values)


def normalize_text(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()
