class ERPWorkflowService:
    def __init__(self, repository, metadata_service=None, permission_service=None):
        self.repository = repository
        self.metadata_service = metadata_service
        self.permission_service = permission_service

    def get_workflow(self, doctype, docname=None, user=None):
        if not self.metadata_service:
            return {"doctype": doctype, "docname": docname, "workflows": []}
        return self.metadata_service.get_workflow(doctype=doctype, docname=docname, user=user)

    def get_current_state(self, doctype, docname, user=None):
        workflow = self.get_workflow(doctype=doctype, docname=docname, user=user)
        states = []
        for item in workflow.get("workflows") or []:
            current = item.get("current_state")
            if current:
                states.append({"workflow": item.get("name"), "current_state": current})
        return {"doctype": doctype, "docname": docname, "states": states}

    def get_available_transitions(self, doctype, docname, user=None):
        workflow = self.get_workflow(doctype=doctype, docname=docname, user=user)
        transitions = []
        for item in workflow.get("workflows") or []:
            for action in item.get("allowed_actions") or []:
                transitions.append({"workflow": item.get("name"), **action})
        return {"doctype": doctype, "docname": docname, "transitions": transitions}

    def validate_action(self, doctype, docname, action, user=None):
        transitions = self.get_available_transitions(doctype=doctype, docname=docname, user=user).get("transitions") or []
        allowed = any(item.get("action") == action for item in transitions)
        return {
            "doctype": doctype,
            "docname": docname,
            "action": action,
            "valid": allowed,
            "message": "Workflow action is available." if allowed else "Workflow action is not available for the current state or role.",
        }

    def apply_action(self, doctype, docname, action, user=None):
        validation = self.validate_action(doctype, docname, action, user=user)
        if not validation.get("valid"):
            return validation
        doc = self.repository.apply_workflow(doctype, docname, action)
        return {"applied": True, "document": self.repository.serialize_doc(doc)}
