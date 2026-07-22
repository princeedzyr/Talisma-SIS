import re

from wingman_ai.creation_session.service import CreationSessionManager


TABLE_FIELDTYPES = {"Table", "Table MultiSelect"}
IGNORED_CHILD_FIELDS = {"name", "owner", "creation", "modified", "modified_by", "parent", "parentfield", "parenttype", "idx", "docstatus"}


class PostCreationWorkflowEngine:
    def __init__(self, erp_service=None):
        self.erp_service = erp_service
        self.creation_session = CreationSessionManager(erp_service)

    def build_follow_up(self, doctype, result=None, response=None, messages=None, user=None, completed_fields=None):
        result = result or {}
        docname = result.get("name") or result.get("docname")
        metadata = self.get_metadata(doctype)
        fields = metadata.get("fields") or []
        steps = self.detect_steps(
            doctype=doctype,
            fields=fields,
            document=result,
            messages=messages or extract_response_messages(response),
            user=user,
            completed_fields=set(completed_fields or []),
        )
        if not steps:
            return self.build_optional_user_permissions_follow_up(doctype, docname, result)

        next_step = steps[0]
        return {
            "message": format_follow_up_message(doctype, docname, steps, messages=messages),
            "actions": [self.build_collect_action(doctype, docname, next_step)],
            "workflow": {
                "type": "post_creation",
                "doctype": doctype,
                "docname": docname,
                "remaining_steps": len(steps),
            },
        }

    def build_completion_follow_up(self, doctype, docname):
        return {
            "message": f"{doctype} setup completed successfully.\n\nCurrent Status\n- The record is ready for business use.",
            "actions": [
                {
                    "type": "navigate",
                    "label": f"Open {doctype} {docname}",
                    "target": {
                        "label": f"{doctype} {docname}",
                        "kind": "document",
                        "route": ["Form", doctype, docname],
                        "doctype": doctype,
                        "docname": docname,
                        "resolved": True,
                    },
                    "requires_confirmation": False,
                    "auto_execute": False,
                    "enabled": bool(docname),
                }
            ],
        }

    def build_collect_action(self, doctype, docname, next_step):
        update = next_step.get("update") or {}
        return {
            "type": "collect_field",
            "label": f"Configure {next_step.get('label')}",
            "payload": {
                "field": next_step.get("field") or {},
                "method": "wingman_ai.api.post_creation.apply_step",
                "action_type": "update",
                "args": {
                    "doctype": doctype,
                    "docname": docname,
                    "fieldname": update.get("fieldname"),
                    "fieldtype": update.get("fieldtype"),
                    "child_doctype": update.get("child_doctype"),
                    "child_fieldname": update.get("child_fieldname"),
                },
            },
            "requires_confirmation": False,
            "auto_execute": False,
            "enabled": bool(docname),
        }

    def detect_steps(self, doctype, fields, document, messages=None, user=None, completed_fields=None):
        completed_fields = completed_fields or set()
        message_labels = setup_labels_from_messages(messages or [])
        steps = []
        if doctype == "User":
            roles_field = next((field for field in fields or [] if field.get("fieldname") == "roles"), None)
            if roles_field and "roles" not in completed_fields and is_empty(document.get("roles")):
                step = self.build_step(roles_field, source="user_readiness", user=user)
                if step:
                    steps.append(step)
        for label in message_labels:
            field = find_field_for_label(fields, label)
            fieldname = field.get("fieldname") if field else None
            if fieldname and fieldname not in completed_fields and not has_step(steps, fieldname) and is_empty(document.get(fieldname)):
                steps.append(self.build_step(field, source="erpnext_message", user=user))

        for field in fields or []:
            fieldname = field.get("fieldname")
            if not fieldname or fieldname in completed_fields or has_step(steps, fieldname):
                continue
            if is_required(field) and is_empty(document.get(fieldname)) and is_configurable_field(field):
                steps.append(self.build_step(field, source="metadata_required", user=user))
        return [step for step in steps if step]

    def build_step(self, field, source=None, user=None):
        if field.get("fieldtype") in TABLE_FIELDTYPES:
            return self.build_table_step(field, source=source, user=user)

        serialized = self.creation_session.serialize_field(field, user=user)
        return {
            "field": serialized,
            "fieldname": field.get("fieldname"),
            "label": serialized.get("label"),
            "source": source,
            "update": {
                "fieldname": field.get("fieldname"),
                "fieldtype": field.get("fieldtype"),
            },
        }

    def build_table_step(self, field, source=None, user=None):
        child_field = self.primary_child_value_field(field.get("options"))
        if not child_field:
            serialized = self.creation_session.serialize_field(field, user=user)
            serialized["component"] = {"type": "table"}
            return {
                "field": serialized,
                "fieldname": field.get("fieldname"),
                "label": serialized.get("label"),
                "source": source,
                "update": {"fieldname": field.get("fieldname"), "fieldtype": field.get("fieldtype")},
            }

        serialized = self.creation_session.serialize_field(child_field, user=user)
        serialized["fieldname"] = field.get("fieldname")
        serialized["label"] = field_label(field)
        serialized["fieldtype"] = field.get("fieldtype")
        serialized["options"] = field.get("options")
        if child_field.get("fieldtype") == "Link":
            serialized["component"] = {"type": "multiselect", "target_doctype": child_field.get("options")}
            choices = self.creation_session.choices_for_field(child_field, user=user)
            if choices:
                serialized["choices"] = choices
        else:
            serialized["component"] = {"type": "table"}

        return {
            "field": serialized,
            "fieldname": field.get("fieldname"),
            "label": serialized.get("label"),
            "source": source,
            "update": {
                "fieldname": field.get("fieldname"),
                "fieldtype": field.get("fieldtype"),
                "child_doctype": field.get("options"),
                "child_fieldname": child_field.get("fieldname"),
                "child_fieldtype": child_field.get("fieldtype"),
            },
        }

    def primary_child_value_field(self, child_doctype):
        metadata = self.get_metadata(child_doctype)
        fields = metadata.get("fields") or []
        candidates = [field for field in fields if usable_child_field(field) and is_required(field)]
        candidates = candidates or [field for field in fields if usable_child_field(field)]
        return candidates[0] if candidates else None

    def get_metadata(self, doctype):
        if not doctype or not self.erp_service or not hasattr(self.erp_service, "get_metadata"):
            return {}
        response = self.erp_service.get_metadata(doctype)
        if isinstance(response, dict):
            return response.get("result") or {}
        return response or {}

    def build_update_payload(self, fieldname, fieldtype, value, child_fieldname=None):
        if fieldtype in TABLE_FIELDTYPES and child_fieldname:
            values = parse_multi_value(value)
            return {fieldname: [{child_fieldname: item} for item in values]}
        return {fieldname: value}

    def next_follow_up_after_update(self, doctype, docname, response, completed_field, user=None):
        document = response.get("result") or {}
        follow_up = self.build_follow_up(
            doctype,
            result=document,
            response=response,
            messages=[],
            user=user,
            completed_fields=[completed_field],
        )
        return follow_up or self.build_completion_follow_up(doctype, docname)

    def build_optional_user_permissions_follow_up(self, doctype, docname, document):
        if doctype != "User" or not docname:
            return None
        return {
            "message": "\n".join(
                [
                    f"User {docname} was created.",
                    "",
                    "User Permissions",
                    "Would you like to configure User Permissions for this User?",
                    "",
                    "Current Status",
                    "- The User record exists in Talisma OneCampus.",
                    "- Additional User Permissions are optional and depend on your access model.",
                ]
            ),
            "actions": [
                {
                    "type": "send_message",
                    "label": "Configure User Permissions",
                    "payload": {"message": f"Create User Permission for {docname}"},
                    "requires_confirmation": False,
                    "auto_execute": False,
                    "enabled": True,
                },
                {
                    "type": "send_message",
                    "label": "Skip",
                    "payload": {"message": "skip user permissions"},
                    "requires_confirmation": False,
                    "auto_execute": False,
                    "enabled": True,
                },
            ],
            "workflow": {
                "type": "post_creation",
                "doctype": doctype,
                "docname": docname,
                "remaining_steps": 0,
                "optional_user_permissions": True,
            },
        }


def format_follow_up_message(doctype, docname, steps, messages=None):
    first = steps[0]
    lines = [
        f"{doctype} {docname or ''} was created.".strip(),
        "",
        "Post-Creation Review",
        "Wingman found setup that should be completed before this record is fully ready.",
        "",
        "Next Required Configuration",
        f"- {first.get('label')}",
    ]
    if len(steps) > 1:
        lines.extend(["", "Remaining Setup", f"- {len(steps) - 1} more item(s) after this."])
    if messages:
        lines.extend(["", "Talisma OneCampus Message", f"- {clean_message(messages[0])}"])
    lines.extend(["", "Current Status", "- No additional Talisma OneCampus setup has been changed yet."])
    return "\n".join(lines)


def extract_response_messages(response):
    if not isinstance(response, dict):
        return []
    messages = []
    messages.extend(str(item) for item in response.get("warnings") or [] if item)
    for item in (response.get("errors") or []) + (response.get("validation_issues") or []):
        if isinstance(item, dict) and item.get("message"):
            messages.append(str(item.get("message")))
    messages.extend(str(item) for item in response.get("server_messages") or [] if item)
    return messages


def setup_labels_from_messages(messages):
    labels = []
    for message in messages or []:
        text = clean_message(message)
        patterns = (
            r"\bno\s+(.+?)\s+specified\b",
            r"\bmissing\s+(.+?)(?:\.|$)",
            r"\b(.+?)\s+missing\b",
            r"\b(.+?)\s+is\s+required\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                label = clean_label(match.group(1))
                if label and label not in labels:
                    labels.append(label)
                break
    return labels


def find_field_for_label(fields, label):
    wanted = normalize(label)
    if not wanted:
        return None
    for field in fields or []:
        field_text = normalize(f"{field.get('label') or ''} {field.get('fieldname') or ''}")
        if wanted == field_text or wanted in field_text or field_text in wanted:
            return field
    singular = wanted[:-1] if wanted.endswith("s") else wanted
    for field in fields or []:
        field_text = normalize(f"{field.get('label') or ''} {field.get('fieldname') or ''}")
        if singular and singular in field_text:
            return field
    return None


def has_step(steps, fieldname):
    return any(step.get("fieldname") == fieldname for step in steps or [])


def is_configurable_field(field):
    return not field.get("hidden") and not field.get("read_only") and field.get("fieldtype") not in {"Section Break", "Column Break", "Tab Break", "HTML"}


def usable_child_field(field):
    fieldname = field.get("fieldname")
    return (
        fieldname
        and fieldname not in IGNORED_CHILD_FIELDS
        and not field.get("hidden")
        and not field.get("read_only")
        and field.get("fieldtype") not in {"Section Break", "Column Break", "Tab Break", "HTML"}
    )


def is_required(field):
    return bool(field.get("reqd") or field.get("mandatory"))


def is_empty(value):
    return value in (None, "", [])


def field_label(field):
    return field.get("label") or str(field.get("fieldname") or "Field").replace("_", " ").title()


def parse_multi_value(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def clean_message(message):
    text = re.sub(r"<[^>]+>", " ", str(message or ""))
    return " ".join(text.replace("\\n", " ").split())


def clean_label(label):
    text = clean_message(label)
    text = re.sub(r"\b(configuration|record|field|value|default)\b", " ", text, flags=re.IGNORECASE)
    return " ".join(text.strip(" .,:;").split()).title()


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()
