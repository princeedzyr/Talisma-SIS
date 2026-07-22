from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter
from wingman_ai.erp_intelligence.models import read_attr, read_bool


class WorkflowDiscoveryService:
    def __init__(self, adapter=None, config=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()

    def get_workflow(self, doctype, docname=None, user=None):
        self.adapter.log("info", "ERP intelligence workflow discovery started", doctype=doctype)
        workflows = []
        for workflow_ref in self.adapter.list_workflows(doctype=doctype):
            workflow = self.adapter.get_workflow(read_attr(workflow_ref, "name"))
            current_state = self.get_current_state(doctype, docname, workflow, user=user) if docname else None
            transitions = self.serialize_transitions(workflow)
            workflows.append(
                {
                    "name": read_attr(workflow, "name"),
                    "document_type": read_attr(workflow, "document_type"),
                    "is_active": read_bool(workflow, "is_active", True),
                    "workflow_state_field": read_attr(workflow, "workflow_state_field"),
                    "states": self.serialize_states(workflow),
                    "transitions": transitions,
                    "current_state": current_state,
                    "allowed_actions": self.filter_allowed_actions(transitions, current_state, user=user),
                    "approval_rules": self.build_approval_rules(transitions),
                }
            )
        return {"doctype": doctype, "docname_provided": bool(docname), "workflows": workflows}

    def get_current_state(self, doctype, docname, workflow, user=None):
        if not self.adapter.has_permission(doctype, "read", docname=docname, user=user):
            return {"available": False, "reason": "read_permission_required"}

        state_field = read_attr(workflow, "workflow_state_field")
        if not state_field:
            return {"available": False, "reason": "workflow_state_field_missing"}

        try:
            doc = self.adapter.get_doc(doctype, docname)
        except Exception:
            return {"available": False, "reason": "document_not_found_or_unreadable"}

        return {"available": True, "fieldname": state_field, "value": read_attr(doc, state_field)}

    def serialize_states(self, workflow):
        states = []
        for state in read_attr(workflow, "states", []) or []:
            states.append(
                {
                    "state": read_attr(state, "state"),
                    "doc_status": read_attr(state, "doc_status"),
                    "allow_edit": read_attr(state, "allow_edit"),
                    "style": read_attr(state, "style"),
                }
            )
        return states

    def serialize_transitions(self, workflow):
        transitions = []
        for transition in read_attr(workflow, "transitions", []) or []:
            transitions.append(
                {
                    "state": read_attr(transition, "state"),
                    "action": read_attr(transition, "action"),
                    "next_state": read_attr(transition, "next_state"),
                    "allowed": read_attr(transition, "allowed"),
                    "condition": read_attr(transition, "condition"),
                    "allow_self_approval": read_bool(transition, "allow_self_approval"),
                }
            )
        return transitions

    def filter_allowed_actions(self, transitions, current_state, user=None):
        roles = set(self.adapter.get_user_roles(user))
        current_value = current_state.get("value") if isinstance(current_state, dict) and current_state.get("available") else None
        allowed = []
        for transition in transitions:
            if current_value and transition.get("state") != current_value:
                continue
            role = transition.get("allowed")
            if role and roles and role not in roles:
                continue
            allowed.append(transition)
        return allowed

    def build_approval_rules(self, transitions):
        return [
            {
                "from_state": transition.get("state"),
                "action": transition.get("action"),
                "to_state": transition.get("next_state"),
                "role": transition.get("allowed"),
                "condition": transition.get("condition"),
                "allow_self_approval": transition.get("allow_self_approval"),
            }
            for transition in transitions
        ]
