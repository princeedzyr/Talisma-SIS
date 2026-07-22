from wingman_ai.exception_intelligence.knowledge_base import (
    CATEGORY_API,
    CATEGORY_AUTHENTICATION,
    CATEGORY_CONFIGURATION,
    CATEGORY_DEPENDENCY,
    CATEGORY_ENVIRONMENT,
    CATEGORY_PERMISSION,
    CATEGORY_INFRASTRUCTURE,
    CATEGORY_INTEGRATION,
    CATEGORY_UNEXPECTED,
    CATEGORY_VALIDATION,
    CATEGORY_WORKFLOW,
)


class RecoveryPlanner:
    def plan(self, classification, analysis, preserved_session=None):
        category = classification.get("category")
        retryable = category in {CATEGORY_API, CATEGORY_INFRASTRUCTURE, CATEGORY_INTEGRATION, CATEGORY_UNEXPECTED}
        can_continue = category in {CATEGORY_VALIDATION, CATEGORY_DEPENDENCY, CATEGORY_WORKFLOW}
        action_labels = []

        if retryable:
            action_labels.append("Retry")
        if preserved_session:
            action_labels.append("Save Draft")
        if category == CATEGORY_DEPENDENCY:
            action_labels.append("Resolve Dependency")
        if category == CATEGORY_VALIDATION:
            action_labels.append("Correct Details")
        if category in {CATEGORY_PERMISSION, CATEGORY_ENVIRONMENT, CATEGORY_CONFIGURATION, CATEGORY_UNEXPECTED}:
            action_labels.append("Notify Administrator")
        action_labels.append("Copy Diagnostic")
        action_labels.append("Cancel")

        return {
            "strategy": classification.get("recovery") or default_strategy(category),
            "retryable": retryable,
            "can_continue_conversation": can_continue,
            "session_preserved": bool(preserved_session),
            "recommended_resolution": role_aware_resolution(classification, analysis),
            "actions": build_actions(action_labels, preserved_session=preserved_session),
        }


def default_strategy(category):
    return {
        CATEGORY_VALIDATION: "Continue conversation and collect corrected information.",
        CATEGORY_DEPENDENCY: "Resolve the missing linked record and resume.",
        CATEGORY_CONFIGURATION: "Pause until setup is completed.",
        CATEGORY_PERMISSION: "Pause until the user role or workflow state is corrected.",
        CATEGORY_ENVIRONMENT: "Pause and ask an ERP Administrator to repair the site.",
        CATEGORY_AUTHENTICATION: "Pause until authentication is restored.",
        CATEGORY_API: "Retry using the configured retry policy.",
        CATEGORY_INFRASTRUCTURE: "Retry with backoff after Talisma OneCampus infrastructure is healthy.",
        CATEGORY_INTEGRATION: "Pause operation and retry after the connected service is corrected.",
        CATEGORY_WORKFLOW: "Guide the user to an available workflow action.",
        CATEGORY_UNEXPECTED: "Log diagnostic and preserve session.",
    }.get(category, "Log diagnostic and preserve session.")


def role_aware_resolution(classification, analysis=None):
    role_profile = (analysis or {}).get("role_profile")
    if role_profile in {"administrator", "developer"}:
        return classification.get("admin_resolution") or classification.get("resolution")
    return classification.get("business_resolution") or classification.get("resolution")


def build_actions(labels, preserved_session=None):
    actions = []
    for label in labels:
        action_type = label.lower().replace(" ", "_")
        action = {
            "type": action_type,
            "label": label,
            "requires_confirmation": label in {"Retry", "Cancel"},
            "auto_execute": False,
            "enabled": True,
        }
        if label in {"Retry", "Save Draft"} and preserved_session:
            action["payload"] = {"preserved_session": preserved_session}
        actions.append(action)
    return actions
