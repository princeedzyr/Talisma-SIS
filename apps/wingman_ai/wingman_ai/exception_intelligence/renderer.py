class DiagnosticRenderer:
    def render(self, analysis, recovery, retry_state):
        lines = [
            "Wingman Operations Center",
            "",
            "Status: Operation Paused",
            f"Issue Type: {analysis.get('category')}",
            f"Severity: {analysis.get('severity')}",
            f"Operation: {analysis.get('operation') or 'Talisma OneCampus Operation'}",
            f"Affected DocType: {analysis.get('target_doctype') or 'Not available'}",
            f"Current Step: {analysis.get('current_step') or analysis.get('failure_stage') or 'Talisma OneCampus Transaction'}",
            "",
            "Root Cause",
            business_safe_text(analysis.get("root_cause"), analysis.get("role_profile")),
            "",
            "Business Impact",
            business_safe_text(analysis.get("business_impact"), analysis.get("role_profile")) or "No Talisma OneCampus data was changed.",
            "",
            "Recommended Resolution",
            business_safe_text(recovery.get("recommended_resolution"), analysis.get("role_profile")) or "Review the diagnostic and retry after correcting the issue.",
            "",
            "Responsible Team",
            analysis.get("responsible_team") or "Wingman Engineering",
        ]
        if recovery.get("session_preserved"):
            lines.extend(["", "Conversation Preserved", "Your entered information has been preserved for retry."])
        if recovery.get("actions"):
            primary = primary_action(recovery.get("actions") or [])
            lines.extend(
                [
                    "",
                    "Action Center",
                    "",
                    "Issue",
                    business_safe_text(analysis.get("root_cause"), analysis.get("role_profile")) or "The operation paused before Talisma OneCampus data was changed.",
                    "",
                    "Wingman Recommendation",
                    action_recommendation(primary, recovery),
                    "",
                    "Use the action buttons below to continue this workflow.",
                ]
            )
        return "\n".join(lines)

    def diagnostic(self, analysis, recovery, retry_state):
        return {
            "title": "Operations Center",
            "issue_type": analysis.get("category"),
            "operation": analysis.get("operation"),
            "crud_action": analysis.get("crud_action"),
            "target_doctype": analysis.get("target_doctype"),
            "docname": analysis.get("docname"),
            "conversation_id": analysis.get("conversation_id"),
            "status": "Operation Paused",
            "category": analysis.get("category"),
            "severity": analysis.get("severity"),
            "root_cause": analysis.get("root_cause"),
            "business_impact": analysis.get("business_impact"),
            "recommended_resolution": recovery.get("recommended_resolution"),
            "responsible_team": analysis.get("responsible_team"),
            "current_step": analysis.get("current_step"),
            "framework_component": analysis.get("framework_component"),
            "failure_stage": analysis.get("failure_stage"),
            "erpnext_api": analysis.get("erpnext_api"),
            "current_user": analysis.get("current_user"),
            "current_company": analysis.get("current_company"),
            "role_profile": analysis.get("role_profile"),
            "technical_reference": analysis.get("technical_reference"),
            "recovery_strategy": recovery.get("strategy"),
            "recovery_options": [action.get("label") for action in recovery.get("actions") or [] if action.get("label")],
            "retry": retry_state,
            "actions": recovery.get("actions") or [],
            "session_preserved": recovery.get("session_preserved"),
        }


def business_safe_text(text, role_profile=None):
    value = str(text or "")
    if role_profile in {"administrator", "developer"}:
        return value
    blocked = ("bench ", "traceback", "programmingerror", "operationalerror", "attributeerror", "file ")
    if not any(token in value.lower() for token in blocked):
        return value
    value = value.replace("Run bench migrate for the site, clear cache, and reload Desk.", "Ask an ERP Administrator to repair the Talisma OneCampus site setup.")
    value = value.replace("Run bench migrate, clear cache, clear website cache, and restart the affected Talisma OneCampus services.", "Ask an ERP Administrator to repair the Talisma OneCampus site setup.")
    return value


def primary_action(actions):
    for action in actions or []:
        presentation = action.get("presentation") or {}
        if presentation.get("group") == "primary":
            return action
    return (actions or [None])[0]


def action_recommendation(action, recovery):
    if action and action.get("description"):
        return action.get("description")
    if action and action.get("label"):
        return action.get("label")
    return business_safe_text(recovery.get("recommended_resolution")) or "Choose the recommended action to continue."
