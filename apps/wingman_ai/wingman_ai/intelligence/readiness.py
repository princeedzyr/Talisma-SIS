from wingman_ai.intelligence.utils import dependencies, is_ready, validation_issues


class ExecutionReadinessEngine:
    def assess(self, payload):
        if (payload or {}).get("status") == "error":
            return state("Not Ready", "red", "Wingman could not complete this response.")

        data = (payload or {}).get("data") or {}
        result = data.get("result") or {}
        if dependencies(payload):
            return state("Waiting for Dependency", "amber", "A linked record or setup dependency must be resolved.")
        if result.get("next_missing_field") or result.get("missing_fields"):
            return state("Waiting for User Input", "amber", "Wingman needs one or more details from the user.")
        if validation_issues(payload):
            return state("Validation Failed", "red", "Talisma OneCampus validation or permission checks need attention.")
        if is_ready(payload):
            return state("Ready to Execute", "green", "The operation is ready for user confirmation.")
        if (payload or {}).get("actions"):
            return state("Action Available", "green", "Wingman prepared a safe next action.")
        return state("Response Ready", "green", "Wingman generated an informational response.")


def state(label, indicator, reason):
    return {
        "state": label,
        "indicator": indicator,
        "ready": indicator == "green",
        "reason": reason,
    }
