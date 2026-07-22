from wingman_ai.intelligence.utils import docname_from, doctype_from, operation_from


DEFAULT_RECOMMENDATIONS = {
    "Lead": ["Create Opportunity", "Assign Sales Person", "Schedule Follow-up"],
    "Opportunity": ["Create Quotation", "Schedule Meeting", "Assign Territory"],
    "Customer": ["Create Contact", "Create Address", "Review Credit Limit"],
    "Contact": ["Open Customer", "Create Address", "Schedule Follow-up"],
    "Address": ["Open Linked Customer", "Create Contact"],
    "Territory": ["Review Customer List", "Create Sales Person"],
    "Lead Source": ["Review Leads", "Create Campaign"],
    "Campaign": ["Review Leads", "Create Lead"],
    "Customer Group": ["Review Customers", "Create Customer"],
    "Sales Person": ["Assign Sales Person", "Review Sales Pipeline"],
}


class RecommendationEngine:
    def __init__(self, recommendations=None):
        self.recommendations = recommendations or DEFAULT_RECOMMENDATIONS

    def recommend(self, payload, context=None):
        doctype = doctype_from(payload, context=context)
        operation = operation_from(payload)
        docname = docname_from(payload, context=context)
        labels = list(self.recommendations.get(doctype) or [])

        if docname and f"View {doctype}" not in labels:
            labels.insert(0, f"View {doctype}")
        if operation == "create" and doctype:
            labels.append(f"Create Another {doctype}")
        if not labels:
            labels.append("Review Current Page")

        return [recommendation_item(label, doctype=doctype, docname=docname) for label in dedupe(labels)[:5]]


def recommendation_item(label, doctype=None, docname=None):
    message = recommendation_message(label, doctype=doctype, docname=docname)
    return {
        "label": label,
        "message": message,
        "action": {
            "type": "send_message",
            "label": label,
            "payload": {"message": message},
            "requires_confirmation": False,
            "auto_execute": False,
            "enabled": True,
        },
    }


def recommendation_message(label, doctype=None, docname=None):
    lowered = str(label or "").lower()
    if lowered.startswith("view ") and doctype and docname:
        return f"open {doctype} {docname}"
    if lowered.startswith("create another ") and doctype:
        return f"create {doctype}"
    if lowered.startswith("create "):
        return label.lower()
    if lowered.startswith("assign "):
        return label.lower()
    if lowered.startswith("schedule "):
        return label.lower()
    if lowered.startswith("review "):
        return f"open {label[7:]}"
    if lowered.startswith("open "):
        return label.lower()
    return label


def dedupe(values):
    seen = set()
    result = []
    for value in values or []:
        key = str(value or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
