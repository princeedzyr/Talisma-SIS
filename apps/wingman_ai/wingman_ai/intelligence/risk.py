from wingman_ai.intelligence.utils import dependencies, operation_from, validation_issues


class RiskAssessmentEngine:
    def assess(self, payload, readiness=None):
        issues = validation_issues(payload)
        deps = dependencies(payload)
        operation = operation_from(payload)
        reasons = []

        if operation == "delete":
            reasons.append("Delete operations can affect linked records and reports.")
        if deps:
            reasons.append("Missing dependencies must be resolved before execution.")
        if issues:
            reasons.append("Talisma OneCampus validation or permission checks reported issues.")
        if readiness and readiness.get("indicator") == "red":
            reasons.append(readiness.get("reason"))

        level = "Low"
        if operation == "delete" or issues:
            level = "High"
        elif deps or operation == "update":
            level = "Medium"

        return {
            "level": level,
            "indicator": {"Low": "green", "Medium": "amber", "High": "red"}.get(level, "amber"),
            "reasons": reasons or ["No elevated risk signals were detected from the available response data."],
        }
