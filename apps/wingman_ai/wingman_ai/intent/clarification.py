from wingman_ai.intent.registry import WRITE_INTENTS


class ClarificationEngine:
    def evaluate(self, message, intent_category, parameters, confidence, settings):
        questions = []
        lowered = (message or "").lower()
        entity = parameters.get("business_entity")

        if confidence < settings.intent_confidence_threshold:
            questions.append("Could you clarify what you want Wingman to do?")

        if intent_category == "Create" and entity == "Customer" and not parameters.get("name"):
            questions.append("Do you want to create a Lead or a Customer record?")
            questions.append("What customer or company name should be used?")

        if intent_category in ("Read", "Search", "List") and "sales" in lowered and not entity:
            questions.append("Do you want Sales Orders, Quotations, Opportunities, or Sales Invoices?")

        if intent_category == "Create" and entity == "Quotation" and not has_customer_reference(parameters):
            questions.append("For which customer should the quotation be prepared?")

        if intent_category in WRITE_INTENTS and not entity:
            questions.append("Which business record type should this action apply to?")

        return {
            "requires_clarification": bool(questions),
            "clarification_questions": dedupe(questions),
        }


def has_customer_reference(parameters):
    return bool(parameters.get("customer") or parameters.get("party") or parameters.get("name"))


def dedupe(items):
    output = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
