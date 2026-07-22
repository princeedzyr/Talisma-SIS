from copy import deepcopy


TASK_APPROVAL_WORKFLOW = {
    "workflow_name": "Task Approval Workflow",
    "document_type": "Task",
    "is_active": 1,
    "override_status": 0,
    "workflow_state_field": "workflow_state",
    "states": [
        {"state": "Draft", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "Counselor Review", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "Finance Review", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "Final Approval", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "Approved", "doc_status": 1, "allow_edit": "System Manager"},
        {"state": "Rejected", "doc_status": 0, "allow_edit": "System Manager"},
    ],
    "transitions": [
        {"state": "Draft", "action": "Submit for Review", "next_state": "Counselor Review", "allowed": "System Manager"},
        {"state": "Counselor Review", "action": "Approve Counselor Review", "next_state": "Finance Review", "allowed": "System Manager"},
        {"state": "Counselor Review", "action": "Reject Counselor Review", "next_state": "Rejected", "allowed": "System Manager"},
        {"state": "Finance Review", "action": "Approve Finance Review", "next_state": "Final Approval", "allowed": "System Manager"},
        {"state": "Finance Review", "action": "Reject Finance Review", "next_state": "Rejected", "allowed": "System Manager"},
        {"state": "Final Approval", "action": "Approve Final Approval", "next_state": "Approved", "allowed": "System Manager"},
        {"state": "Final Approval", "action": "Reject Final Approval", "next_state": "Rejected", "allowed": "System Manager"},
    ],
}


LEAVE_APPROVAL_WORKFLOW = {
    "workflow_name": "Leave Approval Workflow",
    "document_type": "Leave Application",
    "is_active": 1,
    "override_status": 0,
    "workflow_state_field": "workflow_state",
    "states": [
        {"state": "Draft", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "Manager Review", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "HR Review", "doc_status": 0, "allow_edit": "System Manager"},
        {"state": "Approved", "doc_status": 1, "allow_edit": "System Manager"},
        {"state": "Rejected", "doc_status": 0, "allow_edit": "System Manager"},
    ],
    "transitions": [
        {"state": "Draft", "action": "Submit for Review", "next_state": "Manager Review", "allowed": "System Manager"},
        {"state": "Manager Review", "action": "Approve Manager Review", "next_state": "HR Review", "allowed": "System Manager"},
        {"state": "Manager Review", "action": "Reject Manager Review", "next_state": "Rejected", "allowed": "System Manager"},
        {"state": "HR Review", "action": "Approve Leave", "next_state": "Approved", "allowed": "System Manager"},
        {"state": "HR Review", "action": "Reject Leave", "next_state": "Rejected", "allowed": "System Manager"},
    ],
}


WORKFLOW_TEMPLATES = {
    "task": TASK_APPROVAL_WORKFLOW,
    "leave": LEAVE_APPROVAL_WORKFLOW,
}


WORKFLOW_DOCTYPE_ALIASES = {
    "address": "Address",
    "campaign": "Campaign",
    "contact": "Contact",
    "customer group": "Customer Group",
    "customer": "Customer",
    "delivery note": "Delivery Note",
    "issue": "Issue",
    "item": "Item",
    "lead source": "Lead Source",
    "lead": "Lead",
    "material request": "Material Request",
    "opportunity": "Opportunity",
    "payment entry": "Payment Entry",
    "project": "Project",
    "purchase invoice": "Purchase Invoice",
    "purchase order": "Purchase Order",
    "quotation": "Quotation",
    "sales invoice": "Sales Invoice",
    "sales order": "Sales Order",
    "sales person": "Sales Person",
    "stock entry": "Stock Entry",
    "supplier": "Supplier",
    "task": "Task",
    "territory": "Territory",
    "user": "User",
    "warehouse": "Warehouse",
}


VALID_DOCSTATUS_VALUES = {0, 1, 2}
WORKFLOW_ACTION_MASTER_DOCTYPE = "Workflow Action Master"


class WorkflowSetupService:
    def __init__(self, frappe_module=None):
        self.frappe = frappe_module or get_frappe()

    def prepare_task_approval_review(self):
        definition = build_task_approval_definition()
        return self.prepare_review(definition)

    def prepare_review_for_message(self, message):
        definition = self.build_definition_from_message(message)
        return self.prepare_review(definition)

    def build_definition_from_message(self, message):
        text = normalize_text(message)
        if "leave" in text:
            return build_leave_approval_definition()
        if "task" in text:
            return build_task_approval_definition()
        document_type = detect_workflow_document_type(message)
        if document_type:
            return build_generic_approval_definition(
                document_type,
                approved_doc_status=1 if self.is_submittable(document_type) else 0,
            )
        return build_task_approval_definition()

    def is_submittable(self, doctype):
        try:
            meta = self.frappe.get_meta(doctype)
        except Exception:
            return False
        return bool(read_attr(meta, "is_submittable") or read_attr(meta, "issubmittable"))

    def prepare_review(self, definition):
        validation = self.validate_definition(definition)
        return {
            "supported": True,
            "ready": validation["valid"],
            "definition": definition,
            "validation": validation,
            "message": format_workflow_review(definition, validation),
        }

    def execute_definition(self, definition=None, user=None):
        definition = normalize_definition(definition or build_task_approval_definition())
        validation = self.validate_definition(definition)
        if not validation["valid"]:
            return {
                "success": False,
                "message": format_validation_failure(validation),
                "validation": validation,
                "result": None,
            }

        self.ensure_workflow_state_field(definition)
        created_states = self.ensure_workflow_states(definition)
        created_actions = self.ensure_workflow_actions(definition)
        workflow = self.create_workflow(definition)
        verification = self.verify_workflow(definition, workflow.name)
        return {
            "success": verification["passed"],
            "message": format_workflow_creation_result(definition, workflow.name, verification),
            "result": {
                "workflow_name": workflow.name,
                "document_type": definition["document_type"],
                "states_created": created_states,
                "actions_created": created_actions,
                "state_count": len(definition["states"]),
                "action_count": len(unique_transition_actions(definition)),
                "transition_count": len(definition["transitions"]),
                "is_active": definition["is_active"],
            },
            "verification": verification,
            "follow_up": {
                "message": format_workflow_creation_result(definition, workflow.name, verification),
                "actions": build_post_create_actions(workflow.name, definition["document_type"]),
            },
        }

    def validate_definition(self, definition):
        definition = normalize_definition(definition)
        issues = []
        warnings = []
        info = {
            "email_notifications_enabled": False,
            "workflow_state_field_exists": False,
            "workflow_state_field_will_be_created": False,
            "existing_active_workflow": None,
            "document_is_submittable": False,
        }

        document_exists = self.exists("DocType", definition["document_type"])
        if not document_exists:
            issues.append(f"DocType {definition['document_type']} was not found.")
        else:
            info["document_is_submittable"] = self.is_submittable(definition["document_type"])

        if self.exists("Workflow", definition["workflow_name"]):
            issues.append(f"Workflow {definition['workflow_name']} already exists.")

        active = self.find_active_workflow(definition["document_type"], definition["workflow_name"])
        if active:
            info["existing_active_workflow"] = active
            issues.append(f"An active workflow already exists for {definition['document_type']}: {active}.")

        roles = sorted({state["allow_edit"] for state in definition["states"]} | {transition["allowed"] for transition in definition["transitions"]})
        for role in roles:
            if not self.exists("Role", role):
                issues.append(f"Role {role} was not found.")

        state_names = {state["state"] for state in definition["states"]}
        for state in definition["states"]:
            if state["doc_status"] not in VALID_DOCSTATUS_VALUES:
                issues.append(f"State {state['state']} has invalid DocStatus {state['doc_status']}.")
        for transition in definition["transitions"]:
            if transition["state"] not in state_names:
                issues.append(f"Transition {transition['action']} references missing source state {transition['state']}.")
            if transition["next_state"] not in state_names:
                issues.append(f"Transition {transition['action']} references missing next state {transition['next_state']}.")

        if self.field_exists(definition["document_type"], definition["workflow_state_field"]):
            info["workflow_state_field_exists"] = True
        else:
            info["workflow_state_field_will_be_created"] = True
            warnings.append(f"Workflow State Field {definition['workflow_state_field']} is not on {definition['document_type']} yet. Wingman will create an upgrade-safe Custom Field before creating the workflow.")

        missing_actions = [action for action in unique_transition_actions(definition) if not self.exists(WORKFLOW_ACTION_MASTER_DOCTYPE, action)]
        if missing_actions:
            info["workflow_actions_will_be_created"] = missing_actions
            warnings.append(f"Wingman will create missing Workflow Action records before saving: {', '.join(missing_actions)}.")

        if self.has_outgoing_email_account():
            info["email_notifications_enabled"] = True
        else:
            warnings.append("No outgoing Email Account is configured, so workflow action email notifications will remain disabled.")

        if definition.get("metadata_driven") and document_exists and not info["document_is_submittable"]:
            warnings.append(f"{definition['document_type']} is not a submittable DocType, so the Approved state will keep DocStatus as Draft (0) and use workflow_state for approval tracking.")

        return {
            "valid": not issues,
            "issues": issues,
            "warnings": warnings,
            "info": info,
            "roles": roles,
        }

    def exists(self, doctype, name):
        try:
            return bool(self.frappe.db.exists(doctype, name))
        except Exception:
            try:
                self.frappe.get_doc(doctype, name)
                return True
            except Exception:
                return False

    def find_active_workflow(self, document_type, workflow_name):
        try:
            rows = self.frappe.get_all(
                "Workflow",
                filters={"document_type": document_type, "is_active": 1},
                fields=["name"],
                limit=5,
            )
        except Exception:
            return None
        for row in rows or []:
            name = row.get("name") if isinstance(row, dict) else getattr(row, "name", None)
            if name and name != workflow_name:
                return name
        return None

    def field_exists(self, doctype, fieldname):
        try:
            meta = self.frappe.get_meta(doctype)
        except Exception:
            return False
        return any(read_attr(field, "fieldname") == fieldname for field in get_fields(meta))

    def has_outgoing_email_account(self):
        try:
            rows = self.frappe.get_all("Email Account", filters={"enable_outgoing": 1}, fields=["name"], limit=1)
        except Exception:
            rows = []
        return bool(rows)

    def ensure_workflow_state_field(self, definition):
        if self.field_exists(definition["document_type"], definition["workflow_state_field"]):
            return None
        custom = self.frappe.new_doc("Custom Field")
        custom.update(
            {
                "dt": definition["document_type"],
                "label": "Workflow State",
                "fieldname": definition["workflow_state_field"],
                "fieldtype": "Link",
                "options": "Workflow State",
                "insert_after": self.default_insert_after(definition["document_type"]),
                "allow_on_submit": 1,
            }
        )
        custom.insert()
        clear_cache(self.frappe, definition["document_type"])
        return custom

    def default_insert_after(self, doctype):
        try:
            meta = self.frappe.get_meta(doctype)
        except Exception:
            return None
        for preferred in ("status", "subject", "title"):
            if any(read_attr(field, "fieldname") == preferred for field in get_fields(meta)):
                return preferred
        fields = get_fields(meta)
        if fields:
            field = fields[0]
            return read_attr(field, "fieldname")
        return None

    def ensure_workflow_states(self, definition):
        created = []
        for state in definition["states"]:
            state_name = state["state"]
            if self.exists("Workflow State", state_name):
                continue
            doc = self.frappe.new_doc("Workflow State")
            doc.update({"workflow_state_name": state_name, "style": workflow_state_style(state_name)})
            doc.insert()
            created.append(state_name)
        return created

    def ensure_workflow_actions(self, definition):
        created = []
        for action_name in unique_transition_actions(definition):
            if self.exists(WORKFLOW_ACTION_MASTER_DOCTYPE, action_name):
                continue
            doc = self.frappe.new_doc(WORKFLOW_ACTION_MASTER_DOCTYPE)
            doc.update({"workflow_action_name": action_name})
            doc.insert()
            created.append(action_name)
        return created

    def create_workflow(self, definition):
        workflow = self.frappe.new_doc("Workflow")
        workflow.update(
            {
                "workflow_name": definition["workflow_name"],
                "document_type": definition["document_type"],
                "is_active": definition["is_active"],
                "override_status": definition["override_status"],
                "workflow_state_field": definition["workflow_state_field"],
                "send_email_alert": 1 if self.has_outgoing_email_account() else 0,
            }
        )
        for state in definition["states"]:
            workflow.append(
                "states",
                {
                    "state": state["state"],
                    "doc_status": str(state["doc_status"]),
                    "allow_edit": state["allow_edit"],
                },
            )
        for transition in definition["transitions"]:
            workflow.append(
                "transitions",
                {
                    "state": transition["state"],
                    "action": transition["action"],
                    "next_state": transition["next_state"],
                    "allowed": transition["allowed"],
                },
            )
        workflow.insert()
        return workflow

    def verify_workflow(self, definition, workflow_name):
        failures = []
        try:
            workflow = self.frappe.get_doc("Workflow", workflow_name)
        except Exception as exc:
            return {"passed": False, "failures": [f"Could not reload Workflow {workflow_name}: {exc}"]}

        state_names = {read_attr(row, "state") for row in getattr(workflow, "states", []) or []}
        expected_states = {state["state"] for state in definition["states"]}
        missing_states = sorted(expected_states - state_names)
        if missing_states:
            failures.append(f"Missing states: {', '.join(missing_states)}.")

        transition_keys = {
            (read_attr(row, "state"), read_attr(row, "action"), read_attr(row, "next_state"), read_attr(row, "allowed"))
            for row in getattr(workflow, "transitions", []) or []
        }
        expected_transitions = {
            (transition["state"], transition["action"], transition["next_state"], transition["allowed"])
            for transition in definition["transitions"]
        }
        missing_transitions = sorted(expected_transitions - transition_keys)
        if missing_transitions:
            failures.append(f"Missing transitions: {len(missing_transitions)}.")

        missing_actions = [action for action in unique_transition_actions(definition) if not self.exists(WORKFLOW_ACTION_MASTER_DOCTYPE, action)]
        if missing_actions:
            failures.append(f"Missing workflow actions: {', '.join(missing_actions)}.")

        if not read_bool(workflow, "is_active"):
            failures.append("Workflow is not active.")
        if read_attr(workflow, "workflow_state_field") != definition["workflow_state_field"]:
            failures.append("Workflow State Field does not match the requested field.")

        return {"passed": not failures, "failures": failures}


def build_task_approval_definition():
    return deepcopy(TASK_APPROVAL_WORKFLOW)


def build_leave_approval_definition():
    return deepcopy(LEAVE_APPROVAL_WORKFLOW)


def build_definition_from_message(message):
    text = normalize_text(message)
    if "leave" in text:
        return build_leave_approval_definition()
    if "task" in text:
        return build_task_approval_definition()
    document_type = detect_workflow_document_type(message)
    if document_type:
        return build_generic_approval_definition(document_type)
    return build_task_approval_definition()


def build_generic_approval_definition(document_type, approved_doc_status=0):
    return {
        "workflow_name": f"{document_type} Approval Workflow",
        "document_type": document_type,
        "is_active": 1,
        "override_status": 0,
        "workflow_state_field": "workflow_state",
        "metadata_driven": True,
        "states": [
            {"state": "Draft", "doc_status": 0, "allow_edit": "System Manager"},
            {"state": "Review", "doc_status": 0, "allow_edit": "System Manager"},
            {"state": "Approved", "doc_status": int(approved_doc_status), "allow_edit": "System Manager"},
            {"state": "Rejected", "doc_status": 0, "allow_edit": "System Manager"},
        ],
        "transitions": [
            {"state": "Draft", "action": "Submit for Review", "next_state": "Review", "allowed": "System Manager"},
            {"state": "Review", "action": "Approve Review", "next_state": "Approved", "allowed": "System Manager"},
            {"state": "Review", "action": "Reject Review", "next_state": "Rejected", "allowed": "System Manager"},
        ],
    }


def detect_workflow_document_type(message):
    text = f" {normalize_text(message)} "
    for alias, doctype in sorted(WORKFLOW_DOCTYPE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if f" {alias} " in text:
            return doctype
    return None


def normalize_definition(definition):
    normalized = deepcopy(definition or {})
    normalized.setdefault("workflow_name", TASK_APPROVAL_WORKFLOW["workflow_name"])
    normalized.setdefault("document_type", TASK_APPROVAL_WORKFLOW["document_type"])
    normalized.setdefault("is_active", 1)
    normalized.setdefault("override_status", 0)
    normalized.setdefault("workflow_state_field", "workflow_state")
    normalized.setdefault("states", deepcopy(TASK_APPROVAL_WORKFLOW["states"]))
    normalized.setdefault("transitions", deepcopy(TASK_APPROVAL_WORKFLOW["transitions"]))
    for state in normalized["states"]:
        state["doc_status"] = int(state.get("doc_status", 0))
    return normalized


def format_workflow_review(definition, validation):
    lines = [
        "Workflow Creation Review",
        f"Workflow Name: {definition['workflow_name']}",
        f"Document Type: {definition['document_type']}",
        f"Workflow State Field: {definition['workflow_state_field']}",
        "Do Not Override Status: Yes",
        f"Email Notifications: {'Enabled' if validation['info'].get('email_notifications_enabled') else 'Disabled'}",
        "",
        "Workflow States",
    ]
    lines.extend([f"- {state['state']} | DocStatus {docstatus_label(state['doc_status'])} | Editable By {state['allow_edit']}" for state in definition["states"]])
    lines.extend(["", "Workflow Transitions"])
    lines.extend([f"- {transition['state']} -> {transition['action']} -> {transition['next_state']} | Role {transition['allowed']}" for transition in definition["transitions"]])
    lines.extend(["", "Roles", *[f"- {role}" for role in validation.get("roles") or []]])
    if validation["warnings"]:
        lines.extend(["", "Validation Notes", *[f"- {warning}" for warning in validation["warnings"]]])
    if validation["issues"]:
        lines.extend(["", "Issues To Fix Before Creation", *[f"- {issue}" for issue in validation["issues"]]])
    else:
        lines.extend(["", "Current Status", "- Ready to create after your confirmation.", "- No Talisma OneCampus data has been changed yet."])
    return "\n".join(lines)


def format_validation_failure(validation):
    return "\n".join(["Workflow cannot be created yet.", "", "Issues", *[f"- {issue}" for issue in validation.get("issues") or []]])


def format_workflow_creation_result(definition, workflow_name, verification):
    passed = bool(verification.get("passed"))
    lines = [
        "Workflow Created Successfully" if passed else "Workflow Created With Verification Issues",
        f"Workflow Name: {workflow_name}",
        f"Document Type: {definition['document_type']}",
        f"Total States Created: {len(definition['states'])}",
        f"Total Workflow Actions Verified: {len(unique_transition_actions(definition))}",
        f"Total Transitions Created: {len(definition['transitions'])}",
        f"Status: {'Active' if definition.get('is_active') else 'Inactive'}",
        f"Verification Passed: {'Yes' if passed else 'No'}",
    ]
    if verification.get("failures"):
        lines.extend(["", "Verification Issues", *[f"- {failure}" for failure in verification["failures"]]])
    lines.extend(["", "Next Actions", "- Open Workflow", "- Test Workflow", "- Edit Workflow"])
    return "\n".join(lines)


def build_review_actions(definition, validation):
    actions = []
    active_workflow = (validation.get("info") or {}).get("existing_active_workflow")
    if active_workflow:
        actions.append(
            {
                "type": "navigate",
                "label": "Open Existing Workflow",
                "description": "Open the active workflow that currently controls this DocType.",
                "target": {
                    "kind": "document",
                    "label": active_workflow,
                    "route": ["Form", "Workflow", active_workflow],
                },
                "presentation": {"variant": "primary"},
            }
        )

    actions.extend(
        [
            {
                "type": "workflow_create",
                "label": "Create Workflow",
                "method": "wingman_ai.api.workflow_builder.create_workflow",
                "payload": {"definition": definition},
                "requires_confirmation": True,
                "enabled": validation["valid"],
                "auto_execute": False,
            },
            {
                "type": "edit_review",
                "label": "Edit",
                "enabled": True,
                "payload": {"message": f"Change {definition['workflow_name']}: "},
            },
            {"type": "cancel_review", "label": "Cancel", "enabled": True, "payload": {"message": "cancel workflow review"}},
        ]
    )
    return actions


def build_post_create_actions(workflow_name, document_type="Task"):
    return [
        {"type": "navigate", "label": "Open Workflow", "target": {"kind": "document", "route": ["Form", "Workflow", workflow_name]}},
        {"type": "navigate", "label": "Test Workflow", "target": {"kind": "list", "route": ["List", document_type]}},
        {"type": "navigate", "label": "Edit Workflow", "target": {"kind": "document", "route": ["Form", "Workflow", workflow_name]}},
    ]


def docstatus_label(value):
    labels = {0: "Draft (0)", 1: "Submitted (1)", 2: "Cancelled (2)"}
    return labels.get(int(value), str(value))


def get_fields(meta):
    if isinstance(meta, dict):
        return meta.get("fields") or []
    return getattr(meta, "fields", []) or []


def read_attr(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def read_bool(value, key):
    return bool(read_attr(value, key))


def unique_transition_actions(definition):
    actions = []
    seen = set()
    for transition in (definition or {}).get("transitions") or []:
        action = str(transition.get("action") or "").strip()
        if action and action not in seen:
            actions.append(action)
            seen.add(action)
    return actions


def workflow_state_style(state_name):
    text = normalize_text(state_name)
    if "approve" in text:
        return "Success"
    if "reject" in text:
        return "Danger"
    if "review" in text:
        return "Warning"
    return "Primary"


def clear_cache(frappe, doctype):
    clear = getattr(frappe, "clear_cache", None)
    if callable(clear):
        clear(doctype=doctype)


def get_frappe():
    import frappe

    return frappe


def normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())
