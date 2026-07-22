from wingman_ai.intent.registry import ENTITY_ALIASES


def extract_parameters(message, entities):
    parameters = {}
    for entity in entities or []:
        entity_type = entity.get("entity_type")
        value = entity.get("value")
        if not value:
            continue

        if entity_type == "BusinessEntity":
            parameters.setdefault("business_entity", value)
        elif entity_type == "Name":
            parameters.setdefault("name", value)
        elif entity_type in ("Email", "Phone", "Date", "Amount"):
            parameters.setdefault(entity_type.lower(), value)
        else:
            parameters.setdefault(entity_type, value)

    parameters.update(extract_named_parameter_values(message))
    return parameters


def extract_named_parameter_values(message):
    text = message or ""
    lowered = text.lower()
    values = {}

    for status in ("open", "closed", "converted", "lost", "won", "draft", "submitted", "cancelled", "enabled", "disabled"):
        if f"status {status}" in lowered or f"status is {status}" in lowered:
            values["status"] = status.title()
            break

    for priority in ("low", "medium", "high", "urgent"):
        if f"{priority} priority" in lowered or f"priority {priority}" in lowered:
            values["priority"] = priority.title()
            break

    for entity, aliases in ENTITY_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                values.setdefault("business_entity", entity)
                break

    return values
