from wingman_ai.capabilities.base import Capability, CapabilityResult


PROCESS_ACTION_TERMS = {
    "create": "Create",
    "creation": "Create",
    "make": "Create",
    "add": "Create",
    "register": "Create",
    "update": "Update",
    "change": "Update",
    "edit": "Update",
    "modify": "Update",
    "approve": "Approve",
    "approval": "Approve",
    "review": "Review",
    "submit": "Submit",
    "convert": "Convert",
    "conversion": "Convert",
    "search": "Search",
    "find": "Search",
    "report": "Report",
    "dashboard": "Report",
    "close": "Close",
    "follow up": "Follow Up",
    "follow-up": "Follow Up",
}

ERP_PROCESS_OBJECTS = {
    "lead": "Lead",
    "opportunity": "Opportunity",
    "customer": "Customer",
    "contact": "Contact",
    "address": "Address",
    "territory": "Territory",
    "campaign": "Campaign",
    "customer group": "Customer Group",
    "sales person": "Sales Person",
    "quotation": "Quotation",
    "sales order": "Sales Order",
    "sales invoice": "Sales Invoice",
    "delivery note": "Delivery Note",
    "payment entry": "Payment Entry",
    "item": "Item",
    "supplier": "Supplier",
    "purchase order": "Purchase Order",
    "project": "Project",
    "task": "Task",
    "user": "User",
}

PROCESS_HINTS = {
    "improve",
    "redesign",
    "optimize",
    "optimise",
    "automate",
    "automation",
    "faster",
    "less clicks",
    "fewer clicks",
    "process",
    "workflow",
    "best way",
    "experience",
    "product recommendation",
    "recommendation",
    "save time",
    "reduce clicks",
    "pain point",
    "business process",
    "daily work",
}

CRUD_COMMAND_PREFIXES = (
    "create ",
    "new ",
    "add ",
    "make ",
    "register ",
    "open ",
    "go to ",
    "navigate ",
    "search ",
    "find ",
    "list ",
    "update ",
    "change ",
    "delete ",
    "remove ",
)


class ProcessAdvisorCapability(Capability):
    name = "process_advisor"

    def handle(self, message, context, intent):
        profile = build_process_profile(message, context=context)
        return CapabilityResult(
            message=format_process_advisory(profile),
            actions=[],
            data={
                "executed_capability": self.name,
                "response_mode": "erpnext_process_advisory",
                "read_only": True,
                "traceable": True,
                "process_profile": profile,
            },
        )


def is_process_advisory_request(message, intent=None):
    text = normalize(message)
    if not text:
        return False

    if starts_with_crud_command(text) and not has_process_hint(text):
        return False

    advisory_starters = (
        "how can wingman",
        "how should wingman",
        "how can i improve",
        "how do we improve",
        "how can we reduce",
        "how to improve",
        "redesign",
        "optimize",
        "optimise",
        "automate",
        "analyze process",
        "analyse process",
        "review process",
        "product recommendation",
        "make this process",
        "reduce clicks",
        "save time",
    )
    if any(text.startswith(starter) for starter in advisory_starters):
        return True

    if has_process_hint(text) and any(token in text for token in PROCESS_ACTION_TERMS):
        return True

    category = ((getattr(intent, "structured_intent", None) or {}).get("intent_category") or "").lower()
    return category in {"recommend", "compare", "explain"} and has_process_hint(text)


def build_process_profile(message, context=None):
    context = context or {}
    text = normalize(message)
    process_object = detect_process_object(text, context=context)
    operation = detect_process_operation(text)
    module = detect_module(process_object, context=context)
    interactions = estimate_interactions(operation, process_object)
    wingman_interactions = estimate_wingman_interactions(operation)
    return {
        "process": build_process_name(operation, process_object),
        "operation": operation,
        "object": process_object,
        "module": module,
        "context_summary": context.get("summary") or "Talisma OneCampus Desk",
        "current_interactions": interactions,
        "wingman_interactions": wingman_interactions,
        "click_reduction_percent": calculate_click_reduction(interactions, wingman_interactions),
        "time_saved": estimate_time_saved(interactions, wingman_interactions),
        "complexity": estimate_complexity(operation),
    }


def format_process_advisory(profile):
    current = current_process_steps(profile)
    pain_points = process_pain_points(profile)
    wingman = wingman_experience(profile)
    recommendations = product_recommendations(profile)

    return "\n".join(
        [
            profile["process"],
            f"Module: {profile['module']} | Complexity: {profile['complexity']}",
            "",
            "Current Talisma OneCampus Process",
            *[f"- {item}" for item in current],
            f"- Estimated interactions today: {profile['current_interactions']}.",
            "",
            "Pain Points",
            *[f"- {item}" for item in pain_points],
            "",
            "Wingman Experience",
            *[f"- {item}" for item in wingman],
            f"- Estimated Wingman interactions: {profile['wingman_interactions']}.",
            "",
            "Product Recommendations",
            *[f"- {item}" for item in recommendations],
            "",
            "Expected Business Impact",
            f"- Time saved: {profile['time_saved']}.",
            f"- Click reduction: about {profile['click_reduction_percent']}%.",
            "- Business value: faster completion, fewer validation errors, and more consistent Talisma OneCampus data.",
        ]
    )


def current_process_steps(profile):
    obj = profile["object"]
    operation = profile["operation"]
    if operation == "Create":
        return [
            f"Open the correct workspace or list for {obj}.",
            f"Click New or Add {obj}.",
            "Search or manually enter linked records and required setup values.",
            "Fill mandatory fields, apply defaults, and correct validation messages.",
            "Save, verify the created record, then decide the next business action.",
        ]
    if operation == "Update":
        return [
            f"Find the existing {obj} record from search, list, report, or workspace navigation.",
            "Open the form, locate the field or tab, and edit the value.",
            "Resolve validation or workflow rules if Talisma OneCampus rejects the update.",
            "Save and confirm that the intended business change is reflected.",
        ]
    if operation in {"Approve", "Review", "Submit"}:
        return [
            f"Open the relevant {obj} record or approval list.",
            "Review status, ownership, linked records, and outstanding validation requirements.",
            "Choose the correct workflow action and handle permission or state errors.",
            "Reopen the record or report to confirm the workflow result.",
        ]
    if operation == "Report":
        return [
            "Navigate to the correct report or dashboard.",
            "Set filters such as company, date range, status, territory, or owner.",
            "Run the report, scan rows, and manually identify exceptions or next actions.",
            "Open related records one by one for follow-up.",
        ]
    return [
        f"Navigate to the right Talisma OneCampus area for {obj}.",
        "Search records, inspect fields, and decide the next action manually.",
        "Move between forms, reports, and linked records until the business task is complete.",
    ]


def process_pain_points(profile):
    obj = profile["object"]
    return [
        f"Users must know where {obj} lives in Talisma OneCampus and which linked records are required.",
        "The same values are often searched, copied, or re-entered across screens.",
        "Missing setup records and permissions usually appear late, after manual effort.",
        "Talisma OneCampus validation messages can force the user to restart or backtrack.",
        "Next actions are not always obvious after the record is created or updated.",
    ]


def wingman_experience(profile):
    obj = profile["object"]
    operation = profile["operation"].lower()
    return [
        f"User states the business goal in one prompt, such as '{operation} {obj.lower()} for <name>'.",
        "Wingman reads Talisma OneCampus metadata and current context before asking anything.",
        "Existing linked records are searched automatically and exact matches are reused.",
        "Safe defaults are applied from Talisma OneCampus; only missing business decisions are asked one at a time.",
        "Recoverable dependencies are resolved with buttons, then the original workflow resumes automatically.",
        "Wingman verifies the result in Talisma OneCampus and presents recommended next actions.",
    ]


def product_recommendations(profile):
    obj = profile["object"]
    return [
        "Use a goal-oriented session instead of exposing the Talisma OneCampus form as the primary experience.",
        f"Provide quick actions such as Create {obj}, Use Existing Record, Edit Value, Retry, and Cancel only when executable.",
        "Cache metadata blueprints and field rules so repeated prompts are faster.",
        "Show compact business reviews: captured details, inferred defaults, missing decisions, and final action.",
        "Recommend next steps after completion, such as create follow-up, open related record, or review activity.",
        "Keep all writes behind Talisma OneCampus permissions, validation, workflow rules, and final confirmation.",
    ]


def normalize(value):
    return " ".join(str(value or "").strip().lower().split())


def starts_with_crud_command(text):
    return any(text.startswith(prefix) for prefix in CRUD_COMMAND_PREFIXES)


def has_process_hint(text):
    return any(hint in text for hint in PROCESS_HINTS)


def detect_process_object(text, context=None):
    for phrase, doctype in sorted(ERP_PROCESS_OBJECTS.items(), key=lambda item: len(item[0]), reverse=True):
        if phrase in text:
            return doctype
    obj = ((context or {}).get("object") or {}) if isinstance(context, dict) else {}
    return obj.get("doctype") or obj.get("workspace") or obj.get("route_type") or "Talisma OneCampus record"


def detect_process_operation(text):
    for phrase, operation in sorted(PROCESS_ACTION_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
        if phrase in text:
            return operation
    return "Complete"


def detect_module(process_object, context=None):
    obj = ((context or {}).get("object") or {}) if isinstance(context, dict) else {}
    if obj.get("workspace"):
        return obj.get("workspace")
    if process_object in {"Lead", "Opportunity", "Customer", "Contact", "Address", "Territory", "Campaign", "Customer Group", "Sales Person"}:
        return "CRM"
    if process_object in {"Quotation", "Sales Order", "Sales Invoice", "Delivery Note", "Payment Entry"}:
        return "Selling"
    return "Talisma OneCampus"


def build_process_name(operation, process_object):
    return f"{operation} {process_object} Process Redesign"


def estimate_interactions(operation, process_object):
    if operation == "Create":
        return 18 if process_object in {"Opportunity", "Quotation", "Sales Order"} else 12
    if operation == "Update":
        return 9
    if operation in {"Approve", "Review", "Submit"}:
        return 10
    if operation == "Report":
        return 14
    return 8


def estimate_wingman_interactions(operation):
    if operation == "Create":
        return 3
    if operation == "Update":
        return 2
    if operation in {"Approve", "Review", "Submit"}:
        return 2
    if operation == "Report":
        return 2
    return 2


def calculate_click_reduction(current, wingman):
    if not current:
        return 0
    return max(0, min(95, round(((current - wingman) / current) * 100)))


def estimate_time_saved(current, wingman):
    minutes = max(1, round((current - wingman) * 0.35))
    if minutes <= 1:
        return "about 1 minute per task"
    return f"about {minutes} minutes per task"


def estimate_complexity(operation):
    if operation == "Create":
        return "Medium"
    if operation in {"Approve", "Submit"}:
        return "Medium"
    if operation == "Report":
        return "Medium"
    return "Low"
