from wingman_ai.operation_engine.blueprint import field_label


class CRMRecommendationService:
    """Builds post-operation suggestions from metadata relationships and fields."""

    def build(self, blueprint, operation="create", result=None):
        blueprint = blueprint or {}
        operation = str(operation or "").lower()
        doctype = blueprint.get("doctype") or "record"
        recommendations = []

        if operation in {"create", "update"}:
            recommendations.extend(self._relationship_recommendations(blueprint, doctype))
            recommendations.extend(self._field_recommendations(blueprint, doctype))
        if operation == "read":
            recommendations.append(f"Ask for related activity or recent changes for this {doctype}.")
        if operation == "search":
            recommendations.append(f"Open a listed {doctype} record to inspect the full details.")
        if operation == "delete":
            recommendations.append(f"Review linked activity before deleting another {doctype}.")

        if not recommendations:
            recommendations.append(f"Open, update, or search related {doctype} records as needed.")
        return unique(recommendations)[:5]

    def _relationship_recommendations(self, blueprint, doctype):
        recommendations = []
        for relation in blueprint.get("related_documents") or []:
            target = relation.get("doctype") or relation.get("target_doctype") if isinstance(relation, dict) else None
            if target:
                recommendations.append(f"Review related {target} records for this {doctype}.")
        for link in blueprint.get("links") or []:
            target = link.get("target_doctype")
            if target and link.get("required"):
                recommendations.append(f"Confirm the linked {target} before finalizing the {doctype}.")
        return recommendations

    def _field_recommendations(self, blueprint, doctype):
        labels = {field_label(field).lower() for field in ((blueprint.get("fields") or {}).get("editable") or [])}
        recommendations = []
        if any("email" in label or "phone" in label or "mobile" in label for label in labels):
            recommendations.append(f"Keep contact details complete on this {doctype}.")
        if any("status" in label or "stage" in label for label in labels):
            recommendations.append(f"Review the status or stage when the {doctype} changes.")
        if any("territory" in label or "region" in label for label in labels):
            recommendations.append(f"Use territory information to keep reporting accurate.")
        return recommendations


def unique(items):
    seen = set()
    result = []
    for item in items or []:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
