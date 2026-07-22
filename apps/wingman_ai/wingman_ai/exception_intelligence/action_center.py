from copy import deepcopy


UTILITY_ACTION_KINDS = {
    "save_draft",
    "resume_later",
    "notify_administrator",
    "copy_diagnostic",
    "view_technical_details",
    "cancel_operation",
}
PRIMARY_ACTION_KINDS = {
    "create_missing_record",
    "retry",
}
SECONDARY_ACTION_KINDS = {
    "choose_existing_record",
    "edit_value",
    "validation_correction",
}


class ActionCenterService:
    def __init__(self, resolver=None, workflow_manager=None):
        self.resolver = resolver or ActionResolver()
        self.workflow_manager = workflow_manager or RecoveryWorkflowManager()

    def build(self, diagnostic, actions, retry_state=None):
        resolved = self.resolver.resolve(diagnostic or {}, actions or [], retry_state=retry_state or {})
        return self.workflow_manager.prepare(diagnostic or {}, resolved)


class ActionResolver:
    def resolve(self, diagnostic, actions, retry_state=None):
        retry_state = retry_state or {}
        normalized = [self.normalize_action(action, diagnostic, retry_state) for action in actions or []]
        primary = self.choose_primary(normalized, diagnostic, retry_state)
        result = []
        for action in normalized:
            item = deepcopy(action)
            group = self.group_for(item, primary)
            presentation = item.setdefault("presentation", {})
            presentation["section"] = "action_center"
            presentation["group"] = group
            presentation["variant"] = "primary" if group == "primary" else "secondary"
            presentation["rank"] = self.rank_for(item, group)
            item["action_center"] = True
            result.append(item)
        return sorted(result, key=lambda item: ((item.get("presentation") or {}).get("rank", 99), item.get("label") or ""))

    def normalize_action(self, action, diagnostic, retry_state):
        item = deepcopy(action or {})
        kind = item.get("action_kind") or item.get("type")
        item["action_kind"] = kind
        item.setdefault("description", self.description_for(item, diagnostic, retry_state))
        return item

    def choose_primary(self, actions, diagnostic, retry_state):
        dependency_primary = first_action(actions, lambda item: item.get("action_kind") == "create_missing_record")
        if dependency_primary:
            return dependency_primary
        validation = first_action(actions, lambda item: item.get("action_kind") in {"edit_value", "validation_correction"})
        if validation:
            return validation
        retry = first_action(actions, lambda item: item.get("action_kind") == "retry")
        if retry:
            return retry
        return first_action(actions, lambda item: item.get("action_kind") not in UTILITY_ACTION_KINDS) or first_action(actions, lambda item: item.get("action_kind") in UTILITY_ACTION_KINDS)

    def group_for(self, action, primary):
        if primary and action_identity(action) == action_identity(primary):
            return "primary"
        if action.get("action_kind") in UTILITY_ACTION_KINDS:
            return "utility"
        return "secondary"

    def rank_for(self, action, group):
        if group == "primary":
            return 10
        if action.get("action_kind") == "choose_existing_record":
            return 20
        if action.get("action_kind") in {"edit_value", "validation_correction"}:
            return 30
        if group == "secondary":
            return 40
        utility_order = {
            "save_draft": 60,
            "resume_later": 61,
            "notify_administrator": 62,
            "copy_diagnostic": 63,
            "view_technical_details": 64,
            "cancel_operation": 65,
        }
        return utility_order.get(action.get("action_kind"), 70)

    def description_for(self, action, diagnostic, retry_state):
        kind = action.get("action_kind") or action.get("type")
        target = action.get("target_doctype") or ((action.get("payload") or {}).get("doctype")) or diagnostic.get("target_doctype") or "record"
        if kind == "create_missing_record":
            return f"Create the missing {target} and continue the preserved workflow."
        if kind == "choose_existing_record":
            return f"Search existing {target} records and bind the selected value."
        if kind in {"edit_value", "validation_correction"}:
            return "Correct this value inline and re-run validation."
        if kind == "retry":
            return "Retry the paused operation using the preserved session."
        if kind == "save_draft":
            return "Save the current session as a draft."
        if kind == "resume_later":
            return "Persist the session so it can be resumed later."
        if kind == "notify_administrator":
            return "Prepare an administrator notification with the diagnostic context."
        if kind == "view_technical_details":
            return "Show role-aware technical details."
        if kind == "cancel_operation":
            return "Cancel the paused workflow without changing Talisma OneCampus data."
        return action.get("description") or "Continue this workflow."


class RecoveryWorkflowManager:
    def prepare(self, diagnostic, actions):
        grouped = {"primary": [], "secondary": [], "utility": []}
        for action in actions or []:
            group = (action.get("presentation") or {}).get("group") or "secondary"
            grouped.setdefault(group, []).append(action)
        for group, items in grouped.items():
            for index, action in enumerate(items):
                action.setdefault("presentation", {})["position"] = index + 1
                action["workflow_controller"] = True
        diagnostic["action_center"] = {
            "issue": issue_summary(diagnostic),
            "recommendation": recommendation_summary(diagnostic, grouped),
            "groups": {key: [action_identity(item) for item in value] for key, value in grouped.items()},
        }
        return actions


class ActionExecutor:
    def action_contract(self, action):
        return {
            "type": (action or {}).get("type"),
            "method": (action or {}).get("method"),
            "payload": (action or {}).get("payload") or {},
            "requires_confirmation": bool((action or {}).get("requires_confirmation")),
        }


class ConversationResumer:
    def resume_payload(self, action):
        payload = (action or {}).get("payload") or {}
        return payload.get("resume_action") or (action or {}).get("resume_review") or payload.get("resume_review")


class DynamicUIButtonRenderer:
    def presentation(self, action):
        presentation = deepcopy((action or {}).get("presentation") or {})
        presentation.setdefault("section", "action_center")
        presentation.setdefault("group", "secondary")
        presentation.setdefault("variant", "secondary")
        return presentation


def first_action(actions, predicate):
    for action in actions or []:
        if predicate(action):
            return action
    return None


def action_identity(action):
    payload = (action or {}).get("payload") or {}
    return {
        "type": (action or {}).get("type"),
        "label": (action or {}).get("label"),
        "method": (action or {}).get("method"),
        "fieldname": payload.get("fieldname") or ((payload.get("args") or {}).get("fieldname") if isinstance(payload.get("args"), dict) else None),
        "doctype": payload.get("doctype") or ((payload.get("args") or {}).get("doctype") if isinstance(payload.get("args"), dict) else None),
    }


def issue_summary(diagnostic):
    issue = diagnostic.get("root_cause") or diagnostic.get("issue_type") or diagnostic.get("category") or "This operation needs attention."
    return str(issue)


def recommendation_summary(diagnostic, grouped):
    primary = (grouped.get("primary") or [{}])[0]
    if primary.get("label"):
        return primary.get("description") or primary.get("label")
    return diagnostic.get("recommended_resolution") or "Choose an action to continue."
