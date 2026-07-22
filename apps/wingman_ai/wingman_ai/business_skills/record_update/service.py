import re
from datetime import datetime, timezone

from wingman_ai.application.navigation_resolver import resolve_navigation_target
from wingman_ai.business_skills.record_creation.service import PRIMARY_NAME_FIELDS, SUPPORTED_CREATE_DOCTYPES, RecordCreationService
from wingman_ai.business_skills.record_update.formatter import (
    format_update_blocked_prompt,
    format_interactive_update_review,
    format_record_not_found,
    format_update_cancelled,
    format_update_collection_prompt,
    format_update_dependency_prompt,
    format_update_review,
)
from wingman_ai.creation_session.service import CreationSessionManager
from wingman_ai.dependency_resolution.service import DependencyResolutionService
from wingman_ai.erp_service import get_erp_service
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.operation_engine import UniversalOperationFramework
from wingman_ai.repositories.conversation_repository import clear_pending_update_draft, set_pending_update_draft


UPDATE_WORDS = ("update", "change", "edit", "modify", "set", "assign", "move", "mark", "close", "disable", "enable")
FIELD_VALUE_SPLIT = re.compile(r"\b(?:to|as|=|is|with)\b", re.IGNORECASE)
INTERACTIVE_UPDATE_FIELD_LIMIT = 60


class RecordUpdateService:
    def __init__(self, erp_service=None, dependency_service=None, creation_session=None, record_creation_service=None):
        self.erp_service = erp_service or get_erp_service()
        self.operation_framework = UniversalOperationFramework(erp_service=self.erp_service)
        self.dependency_service = dependency_service or DependencyResolutionService(
            erp_service=self.erp_service,
            supported_doctypes=SUPPORTED_CREATE_DOCTYPES,
            primary_name_fields=PRIMARY_NAME_FIELDS,
        )
        self.creation_session = creation_session or CreationSessionManager(self.erp_service)
        self.record_creation_service = record_creation_service or RecordCreationService(
            erp_service=self.erp_service,
            dependency_service=self.dependency_service,
        )
        self.preflight = self.operation_framework.preflight

    def handle_message(self, message, context=None, intent=None):
        context = context or {}
        pending = context.get("pending_update_draft")
        if pending and should_restart_pending_update(message, intent=intent):
            clear_pending_update_draft(context.get("conversation_id"), user=context.get("user"))
            result = self.prepare_update_from_message(message, context=context, intent=intent)
        elif pending:
            result = self.continue_pending_update(message, context=context, intent=intent)
        else:
            result = self.prepare_update_from_message(message, context=context, intent=intent)
        if isinstance(result, dict) and context.get("conversation_id"):
            result.setdefault("conversation_id", context.get("conversation_id"))
        return result

    def prepare_update_from_message(self, message, context=None, intent=None):
        context = context or {}
        target = self.resolve_target(message, context=context)
        if target.get("ambiguous"):
            prepared = self.build_record_selection(message, target)
            self.sync_pending_update(prepared, context=context)
            return prepared
        if not target.get("doctype") or not target.get("docname"):
            return self.not_found(message, target.get("query"))

        read_response = self.erp_service.read_document(target["doctype"], target["docname"], user=context.get("user"))
        if not read_response.get("success"):
            return self.not_found(message, target.get("query") or target.get("docname"))

        blueprint = self.build_blueprint(target["doctype"])
        fields = blueprint["fields"]["all"]
        current = read_response.get("result") or {}
        changes = self.extract_changes(message, target, fields)
        if not changes:
            prepared = self.build_interactive_review(target, current, fields, original_message=message, user=context.get("user"))
            self.sync_pending_update(prepared, context=context)
            return prepared

        prepared = self.build_prepared_update(
            target["doctype"],
            target["docname"],
            current,
            fields,
            changes,
            original_message=message,
            user=context.get("user"),
            blueprint=blueprint,
        )
        self.sync_pending_update(prepared, context=context)
        return prepared

    def continue_pending_update(self, message, context=None, intent=None):
        context = context or {}
        pending = context.get("pending_update_draft") or {}
        if is_cancel_message(message):
            clear_pending_update_draft(context.get("conversation_id"), user=context.get("user"))
            return {
                "operation": "update",
                "supported": True,
                "cancelled": True,
                "message": format_update_cancelled(pending.get("doctype"), pending.get("docname")),
            }

        stage = pending.get("stage")
        if stage == "record_selection":
            return self.continue_record_selection(message, pending, context=context)
        if stage == "interactive_review":
            return self.continue_interactive_review(message, pending, context=context)
        if stage == "field_selection":
            return self.continue_field_selection(message, pending, context=context)
        if stage == "value_collection":
            return self.continue_value_collection(message, pending, context=context)

        clear_pending_update_draft(context.get("conversation_id"), user=context.get("user"))
        return self.prepare_update_from_message(message, context=context, intent=intent)

    def continue_record_selection(self, message, pending, context=None):
        selected = self.resolve_selected_record(message, pending.get("options") or [])
        if not selected:
            prepared = dict(pending)
            prepared["message"] = format_update_collection_prompt(prepared, reason="Please choose one of the listed records.")
            self.sync_pending_update(prepared, context=context)
            return prepared

        read_response = self.erp_service.read_document(selected["doctype"], selected["docname"], user=(context or {}).get("user"))
        if not read_response.get("success"):
            return self.not_found(pending.get("original_message"), selected.get("docname"))
        blueprint = self.build_blueprint(selected["doctype"])
        prepared = self.build_interactive_review(
            selected,
            read_response.get("result") or {},
            blueprint["fields"]["all"],
            original_message=pending.get("original_message"),
            user=(context or {}).get("user"),
        )
        self.sync_pending_update(prepared, context=context)
        return prepared

    def continue_interactive_review(self, message, pending, context=None):
        fields = pending.get("fields") or []
        field = self.match_update_field(message, fields)
        if not field:
            prepared = dict(pending)
            prepared["editable_review_fields"] = self.build_editable_review_fields(
                fields,
                pending.get("current") or {},
                changes=pending.get("changes") or {},
                user=(context or {}).get("user"),
            )
            prepared["message"] = format_interactive_update_review(prepared)
            self.sync_pending_update(prepared, context=context)
            return prepared

        prepared = self.build_value_collection(pending, field, user=(context or {}).get("user"))
        self.sync_pending_update(prepared, context=context)
        return prepared

    def continue_field_selection(self, message, pending, context=None):
        fields = pending.get("fields") or []
        field = self.match_update_field(message, fields)
        if not field:
            prepared = dict(pending)
            prepared["message"] = format_update_collection_prompt(prepared, reason="Please choose an editable field from the list.")
            self.sync_pending_update(prepared, context=context)
            return prepared

        prepared = self.build_value_collection(pending, field, user=(context or {}).get("user"))
        self.sync_pending_update(prepared, context=context)
        return prepared

    def continue_value_collection(self, message, pending, context=None):
        fields = pending.get("fields") or []
        field = find_field(fields, pending.get("fieldname"))
        if not field:
            clear_pending_update_draft((context or {}).get("conversation_id"), user=(context or {}).get("user"))
            return self.not_found(pending.get("original_message"), pending.get("docname"))

        prepared = self.continue_inline_field(
            doctype=pending.get("doctype"),
            docname=pending.get("docname"),
            fieldname=field.get("fieldname"),
            value=message,
            current=pending.get("current") or {},
            changes=pending.get("changes") or {},
            original_message=pending.get("original_message"),
            conversation_id=(context or {}).get("conversation_id") or pending.get("conversation_id"),
            user=(context or {}).get("user"),
        )
        self.sync_pending_update(prepared, context=context)
        return prepared

    def build_record_selection(self, message, target):
        options = target.get("options") or []
        field = {
            "fieldname": "record",
            "label": "Record",
            "fieldtype": "Select",
            "component": {"type": "select"},
            "choices": [
                {
                    "label": option.get("label") or f"{option.get('doctype')} {option.get('docname')}",
                    "value": encode_record_choice(option.get("doctype"), option.get("docname")),
                }
                for option in options
                if option.get("doctype") and option.get("docname")
            ],
            "required": True,
        }
        prepared = {
            "operation": "update",
            "supported": True,
            "stage": "record_selection",
            "original_message": message,
            "options": options,
            "next_missing_field": field,
            "ready": False,
        }
        prepared["message"] = format_update_collection_prompt(prepared)
        return prepared

    def build_field_selection(self, target, current, fields, original_message=None, user=None):
        editable = editable_fields(fields)
        field = {
            "fieldname": "field",
            "label": "Field",
            "fieldtype": "Select",
            "component": {"type": "select"},
            "choices": [{"label": field_label(item), "value": item.get("fieldname")} for item in editable[:80]],
            "required": True,
        }
        prepared = {
            "operation": "update",
            "supported": True,
            "stage": "field_selection",
            "doctype": target.get("doctype"),
            "docname": target.get("docname"),
            "current": current,
            "fields": editable,
            "changes": {},
            "original_message": original_message,
            "next_missing_field": field,
            "ready": False,
        }
        prepared["message"] = format_update_collection_prompt(prepared)
        return prepared

    def build_interactive_review(self, target, current, fields, original_message=None, user=None, changes=None):
        editable = editable_fields(fields)
        prepared = {
            "operation": "update",
            "supported": True,
            "stage": "interactive_review",
            "doctype": target.get("doctype"),
            "docname": target.get("docname"),
            "current": current,
            "fields": editable,
            "changes": changes or {},
            "editable_review_fields": self.build_editable_review_fields(editable, current, changes=changes, user=user),
            "original_message": original_message,
            "ready": False,
        }
        prepared["message"] = format_interactive_update_review(prepared)
        return prepared

    def build_editable_review_fields(self, fields, current, changes=None, user=None):
        rows = []
        changes = changes or {}
        for field in editable_fields(fields)[:INTERACTIVE_UPDATE_FIELD_LIMIT]:
            item = self.creation_session.serialize_field({**field, "required": False}, user=user)
            fieldname = item.get("fieldname")
            current_value = (current or {}).get(fieldname)
            has_change = fieldname in changes
            item.update(
                {
                    "current_value": current_value,
                    "new_value": changes.get(fieldname) if has_change else current_value,
                    "modified": has_change,
                }
            )
            rows.append(item)
        return rows

    def build_value_collection(self, pending, field, user=None):
        prepared = {
            **dict(pending),
            "operation": "update",
            "supported": True,
            "stage": "value_collection",
            "fieldname": field.get("fieldname"),
            "next_missing_field": self.creation_session.serialize_field(field, user=user),
            "ready": False,
        }
        prepared["message"] = format_update_collection_prompt(prepared)
        return prepared

    def continue_inline_field(
        self,
        doctype,
        docname,
        fieldname,
        value,
        current=None,
        changes=None,
        original_message=None,
        conversation_id=None,
        user=None,
    ):
        require_update_target(doctype, docname, fieldname)
        blueprint = self.build_blueprint(doctype)
        fields = editable_fields(blueprint["fields"]["all"])
        current = current or {}
        if not current:
            read_response = self.erp_service.read_document(doctype, docname, user=user)
            if not read_response.get("success"):
                return self.not_found(original_message, docname)
            current = read_response.get("result") or {}

        field = find_field(fields, fieldname)
        if not field:
            prepared = self.build_interactive_review(
                {"doctype": doctype, "docname": docname},
                current,
                fields,
                original_message=original_message,
                user=user,
                changes=changes,
            )
            prepared["message"] = format_interactive_update_review(prepared)
            return prepared

        parsed = self.record_creation_service.parse_answer_for_field(value, field, user=user)
        if not parsed.get("accepted"):
            pending = {
                "operation": "update",
                "supported": True,
                "stage": "interactive_review",
                "doctype": doctype,
                "docname": docname,
                "current": current,
                "fields": fields,
                "changes": changes or {},
                "original_message": original_message,
                "conversation_id": conversation_id,
            }
            prepared = self.build_value_collection(pending, field, user=user)
            prepared["message"] = format_update_collection_prompt(prepared, reason=parsed.get("message"))
            return prepared

        merged_changes = dict(changes or {})
        new_value = parsed.get("value")
        if values_match(current.get(fieldname), new_value):
            merged_changes.pop(fieldname, None)
        else:
            merged_changes[fieldname] = new_value

        if not merged_changes:
            return self.build_interactive_review(
                {"doctype": doctype, "docname": docname},
                current,
                fields,
                original_message=original_message,
                user=user,
                changes={},
            )

        prepared = self.build_prepared_update(
            doctype,
            docname,
            current,
            fields,
            merged_changes,
            original_message=original_message,
            user=user,
            blueprint=blueprint,
        )
        if conversation_id:
            prepared["conversation_id"] = conversation_id
        return prepared

    def build_prepared_update(self, doctype, docname, current, fields, changes, original_message=None, user=None, blueprint=None):
        blueprint = blueprint or self.build_blueprint(doctype)
        editable = self.operation_framework.editable_fields(blueprint) or editable_fields(fields)
        cleaned_changes, invalid = self.normalize_changes(changes, editable, user=user)
        missing_dependencies = self.dependency_service.detect_for_operation(doctype, cleaned_changes, operation="update", docname=docname, user=user)
        missing_dependencies = self.record_creation_service.add_dependency_reviews(missing_dependencies, context={"user": user, "raw": {"message": original_message}}, user=user)
        preflight = self.run_preflight_update(doctype, docname, cleaned_changes, editable, invalid=invalid, missing_dependencies=missing_dependencies, user=user)
        preflight_field = preflight.get("field") if not preflight.get("valid") and preflight.get("recoverable", True) else None
        validation_issues = invalid + (preflight.get("issues") or [])
        plan = self.operation_framework.build_update_plan(
            blueprint,
            changes=cleaned_changes,
            current=current,
            missing_fields=[preflight_field] if preflight_field else [],
            dependencies=missing_dependencies,
            preflight={**preflight, "field": preflight_field},
            docname=docname,
        )
        review = self.operation_framework.build_update_review(
            doctype,
            docname=docname,
            current=current,
            changes=cleaned_changes,
            fields=editable,
            context={"raw": {"message": original_message}},
            user=user,
        )
        prepared = {
            "operation": "update",
            "supported": True,
            "stage": "value_collection" if preflight_field else "review",
            "doctype": doctype,
            "docname": docname,
            "blueprint": blueprint,
            "operation_plan": plan,
            "current": current,
            "fields": editable,
            "fieldname": preflight_field.get("fieldname") if preflight_field else None,
            "changes": cleaned_changes,
            "change_rows": change_rows(current, cleaned_changes, editable),
            "missing_dependencies": missing_dependencies,
            "validation_issues": validation_issues,
            "preflight": preflight,
            "review": review,
            "next_missing_field": self.creation_session.serialize_field(preflight_field, user=user) if preflight_field else None,
            "impact": analyze_impact(doctype, cleaned_changes, editable),
            "audit": {"user": user, "timestamp": datetime.now(timezone.utc).isoformat()},
            "original_message": original_message,
            "ready": bool(cleaned_changes) and not missing_dependencies and not validation_issues and preflight.get("valid"),
        }
        if not cleaned_changes:
            return self.build_interactive_review({"doctype": doctype, "docname": docname}, current, editable, original_message=original_message, user=user)
        if preflight_field:
            prepared["message"] = format_update_collection_prompt(prepared, reason=preflight.get("guidance"))
            return prepared
        if not preflight.get("valid") and not preflight.get("recoverable", True):
            prepared["message"] = format_update_blocked_prompt(prepared)
            return prepared
        prepared["message"] = format_update_dependency_prompt(prepared) if missing_dependencies else format_update_review(prepared)
        return prepared

    def normalize_changes(self, changes, fields, user=None):
        cleaned = {}
        invalid = []
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
        for fieldname, value in (changes or {}).items():
            field = field_map.get(fieldname)
            if not field:
                invalid.append({"fieldname": fieldname, "message": f"{fieldname} is not editable on this record."})
                continue
            parsed = self.record_creation_service.parse_answer_for_field(value, field, user=user)
            if parsed.get("accepted"):
                cleaned[fieldname] = parsed.get("value")
            else:
                invalid.append({"fieldname": fieldname, "message": parsed.get("message") or f"{field_label(field)} is invalid."})
        return cleaned, invalid

    def validate_update(self, doctype, docname, changes, user=None):
        if not hasattr(self.erp_service, "validate_document"):
            return {"validation_issues": []}
        response = self.erp_service.validate_document(doctype, data=changes or {}, docname=docname, operation="write", user=user)
        return response if isinstance(response, dict) else {"validation_issues": []}

    def run_preflight_update(self, doctype, docname, changes, fields, invalid=None, missing_dependencies=None, user=None):
        if invalid or missing_dependencies or not changes:
            return {"valid": True, "field": None, "fieldname": None, "issues": [], "guidance": None}
        return self.operation_framework.validate_update(doctype, docname, changes=changes, fields=fields, user=user)

    def update_record(self, doctype, docname, data, user=None):
        return self.erp_service.update_document(doctype, docname, data=data or {}, user=user)

    def resolve_target(self, message, context=None):
        context = context or {}
        context_object = context.get("object") or {}
        if should_use_current_record(message, context_object):
            return {
                "doctype": context_object.get("doctype"),
                "docname": context_object.get("docname"),
                "query": "current record",
            }

        target_query = extract_target_query(message, context=context, erp_service=self.erp_service)
        if not target_query and context_object.get("doctype") and context_object.get("docname"):
            return {
                "doctype": context_object.get("doctype"),
                "docname": context_object.get("docname"),
                "query": "current record",
            }
        if not target_query:
            return {"query": message}

        bare_doctype = self.get_bare_doctype_request(target_query)
        if bare_doctype:
            if current_record_matches_doctype(context_object, bare_doctype):
                return {
                    "doctype": context_object.get("doctype"),
                    "docname": context_object.get("docname"),
                    "query": "current record",
                }
            selection = self.build_record_selection_target(bare_doctype, target_query, user=context.get("user"))
            if selection:
                return selection
            return {"query": target_query}

        target = resolve_navigation_target(f"open {target_query}", context=context)
        if target.kind == "document":
            read_response = self.erp_service.read_document(target.doctype, target.docname, user=context.get("user"))
            if read_response.get("success"):
                return {"doctype": target.doctype, "docname": target.docname, "query": target_query}
            fallback = self.resolve_target_with_search(target_query, user=context.get("user"))
            if fallback:
                return fallback
            return {"doctype": target.doctype, "docname": target.docname, "query": target_query}
        if target.kind == "ambiguous_document":
            return {"ambiguous": True, "query": target_query, "options": normalize_target_options(target.options)}
        if target.kind == "document_type_mismatch" and target.options:
            return {"ambiguous": True, "query": target_query, "options": normalize_target_options(target.options)}

        fallback = self.resolve_target_with_search(target_query, user=context.get("user"))
        return fallback or {"query": target_query}

    def get_bare_doctype_request(self, target_query):
        request = split_doctype_query(target_query, self.discover_doctypes())
        if not request:
            return None
        doctype, query = request
        return doctype if not query else None

    def build_record_selection_target(self, doctype, target_query, user=None):
        if not hasattr(self.erp_service, "search_documents"):
            return None
        response = self.erp_service.search_documents(doctype, text="", fields=["name"], page=1, page_size=6, user=user)
        rows = ((response.get("result") or {}).get("rows") or []) if isinstance(response, dict) and response.get("success") else []
        options = [
            {"doctype": doctype, "docname": row.get("name"), "label": row.get("name")}
            for row in rows
            if row.get("name")
        ]
        if not options:
            return None
        return {"ambiguous": True, "query": target_query, "options": options}

    def resolve_target_with_search(self, target_query, user=None):
        request = split_doctype_query(target_query, self.discover_doctypes())
        if not request:
            return None
        doctype, query = request
        if not query:
            return None
        exact = self.erp_service.read_document(doctype, query, user=user)
        if exact.get("success"):
            return {"doctype": doctype, "docname": query, "query": target_query}
        response = self.erp_service.search_documents(doctype, text=query, fields=["name"], page=1, page_size=6, user=user)
        rows = ((response.get("result") or {}).get("rows") or []) if response.get("success") else []
        if len(rows) == 1:
            return {"doctype": doctype, "docname": rows[0].get("name"), "query": target_query}
        if len(rows) > 1:
            return {
                "ambiguous": True,
                "query": target_query,
                "options": [{"doctype": doctype, "docname": row.get("name"), "label": row.get("name")} for row in rows if row.get("name")],
            }
        return None

    def discover_doctypes(self):
        metadata_service = getattr(self.erp_service, "metadata_service", None)
        if metadata_service and hasattr(metadata_service, "list_doctypes"):
            try:
                rows = metadata_service.list_doctypes(include_child_tables=False) or []
                return [item.get("name") for item in rows if item.get("name")]
            except Exception:
                pass
        if hasattr(self.erp_service, "metadata") and isinstance(getattr(self.erp_service, "metadata"), dict):
            return list(self.erp_service.metadata.keys())
        return sorted(SUPPORTED_CREATE_DOCTYPES)

    def extract_changes(self, message, target, fields):
        editable = editable_fields(fields)
        text = remove_target_phrase(message, target)
        special = extract_special_change(message, editable)
        if special:
            return special

        field_phrase, value = split_field_value(text)
        if not field_phrase or value in (None, ""):
            return {}
        field = self.match_update_field(field_phrase, editable)
        if not field:
            return {}
        return {field["fieldname"]: value}

    def match_update_field(self, value, fields):
        return match_update_field(value, fields)

    def get_metadata(self, doctype):
        response = self.erp_service.get_metadata(doctype)
        if isinstance(response, dict):
            return response.get("result") or {}
        return response or {}

    def build_blueprint(self, doctype):
        return self.operation_framework.build_blueprint(doctype, operation="update")

    def resolve_selected_record(self, message, options):
        value = str(message or "").strip()
        for option in options or []:
            if value == encode_record_choice(option.get("doctype"), option.get("docname")):
                return option
            if normalize(value) in {normalize(option.get("label")), normalize(option.get("docname"))}:
                return option
        return None

    def sync_pending_update(self, prepared, context=None):
        context = context or {}
        conversation_id = context.get("conversation_id")
        if not conversation_id or not prepared.get("supported"):
            return
        if prepared.get("ready") or prepared.get("cancelled"):
            clear_pending_update_draft(conversation_id, user=context.get("user"))
            return
        set_pending_update_draft(
            conversation_id,
            {
                "operation": "update",
                "stage": prepared.get("stage"),
                "doctype": prepared.get("doctype"),
                "docname": prepared.get("docname"),
                "current": prepared.get("current") or {},
                "fields": prepared.get("fields") or [],
                "changes": prepared.get("changes") or {},
                "fieldname": prepared.get("fieldname"),
                "editable_review_fields": prepared.get("editable_review_fields") or [],
                "options": prepared.get("options") or [],
                "original_message": prepared.get("original_message"),
                "next_field": prepared.get("next_missing_field"),
            },
            user=context.get("user"),
        )

    def not_found(self, message, query=None):
        return {
            "operation": "update",
            "supported": True,
            "ready": False,
            "message": format_record_not_found(query or message),
        }


def extract_target_query(message, context=None, erp_service=None):
    text = clean_text(message)
    lowered = normalize(text)
    stripped = strip_update_prefix(text)

    possessive = re.search(r"^(?:change|update|edit|set)\s+(.+?)'s\s+(.+?)\s+(?:to|as|=|is)\s+.+$", text, re.IGNORECASE)
    if possessive:
        return clean_query(possessive.group(1))

    for prefix in ("assign", "move"):
        match = re.search(rf"^{prefix}\s+(.+?)\s+to\s+.+$", text, re.IGNORECASE)
        if match:
            return clean_query(match.group(1))

    for prefix in ("disable", "enable", "close"):
        if lowered.startswith(prefix):
            return clean_query(text[len(prefix) :])

    if lowered.startswith("mark "):
        match = re.search(r"^mark\s+(.+?)\s+(?:as\s+)?(?:completed|complete|closed|done|open|won|lost|qualified)$", text, re.IGNORECASE)
        if match:
            return clean_query(match.group(1))

    doctypes = discover_doctypes_from_erp(erp_service)
    doctype_request = split_doctype_query(stripped, doctypes)
    if not doctype_request:
        return ""

    doctype, query = doctype_request
    fields = get_fields_for_doctype(erp_service, doctype)
    split_at = find_change_field_start(query, fields)
    if split_at is not None:
        query = query[:split_at]
    return clean_query(f"{doctype} {query}") if query else clean_query(doctype)


def strip_update_prefix(text):
    value = clean_text(text)
    for word in UPDATE_WORDS:
        match = re.match(rf"^\s*{re.escape(word)}\s+", value, flags=re.IGNORECASE)
        if match:
            return clean_text(value[match.end() :])
    return value


def discover_doctypes_from_erp(erp_service):
    if erp_service is not None and hasattr(erp_service, "metadata") and isinstance(getattr(erp_service, "metadata"), dict):
        return list(erp_service.metadata.keys())
    return sorted(SUPPORTED_CREATE_DOCTYPES)


def get_fields_for_doctype(erp_service, doctype):
    if not erp_service:
        return []
    try:
        response = erp_service.get_metadata(doctype)
    except Exception:
        return []
    meta = response.get("result") if isinstance(response, dict) else response
    return (meta or {}).get("fields") or []


def split_doctype_query(text, doctypes):
    normalized = normalize(text)
    for doctype in sorted([item for item in doctypes or [] if item], key=len, reverse=True):
        doctype_norm = normalize(doctype)
        if normalized == doctype_norm:
            return doctype, ""
        if normalized.startswith(f"{doctype_norm} "):
            words = text.split()
            query = " ".join(words[len(doctype_norm.split()) :])
            return doctype, clean_query(query)
    return None


def find_change_field_start(query, fields):
    lowered = normalize(query)
    if not lowered:
        return None
    aliases = []
    for field in editable_fields(fields):
        aliases.extend(field_aliases(field))
    for alias in sorted(set(aliases), key=len, reverse=True):
        match = re.search(rf"\b{re.escape(alias)}\b\s+(?:to|as|=|is|with)\b", lowered)
        if match:
            prefix = lowered[: match.start()]
            return len(prefix)
    return None


def remove_target_phrase(message, target):
    text = strip_update_prefix(message)
    for item in (target.get("doctype"), target.get("document_query"), target.get("docname"), target.get("query")):
        if item:
            text = re.sub(rf"\b{re.escape(str(item))}\b", " ", text, flags=re.IGNORECASE)
    return clean_text(text)


def split_field_value(text):
    value = clean_text(text)
    match = FIELD_VALUE_SPLIT.search(value)
    if not match:
        return "", ""
    field_phrase = clean_query(value[: match.start()])
    new_value = clean_query(value[match.end() :])
    field_phrase = re.sub(r"^(?:field|value|number)\s+", "", field_phrase, flags=re.IGNORECASE).strip()
    return field_phrase, new_value


def extract_special_change(message, fields):
    text = normalize(message)
    if text.startswith("disable "):
        field = first_existing_field(fields, ("enabled", "disabled"))
        if field:
            return {field["fieldname"]: 0 if field["fieldname"] == "enabled" else 1}
    if text.startswith("enable "):
        field = first_existing_field(fields, ("enabled", "disabled"))
        if field:
            return {field["fieldname"]: 1 if field["fieldname"] == "enabled" else 0}

    status_field = first_status_field(fields)
    if status_field:
        status_value = None
        if text.startswith("close "):
            status_value = best_select_value(status_field, ("Closed", "Close", "Completed", "Complete"))
        elif " completed" in f" {text}" or " complete" in f" {text}":
            status_value = best_select_value(status_field, ("Completed", "Complete", "Closed"))
        elif " won" in f" {text}":
            status_value = best_select_value(status_field, ("Won", "Closed Won", "Completed"))
        elif " lost" in f" {text}":
            status_value = best_select_value(status_field, ("Lost", "Closed Lost", "Closed"))
        elif " qualified" in f" {text}":
            status_value = best_select_value(status_field, ("Qualified", "Opportunity"))
        if status_value:
            return {status_field["fieldname"]: status_value}

    if text.startswith("assign ") or text.startswith("move "):
        field = first_assignment_field(fields)
        match = re.search(r"\bto\s+(.+)$", message or "", flags=re.IGNORECASE)
        if field and match:
            return {field["fieldname"]: clean_query(match.group(1))}
    return {}


def editable_fields(fields):
    result = []
    for field in fields or []:
        if not is_editable_business_field(field):
            continue
        result.append(dict(field))
    return result


def match_update_field(value, fields):
    requested = normalize(value)
    if not requested:
        return None
    for field in fields or []:
        if requested in {normalize(field.get("fieldname")), normalize(field_label(field))}:
            return field
    for field in fields or []:
        if requested in field_aliases(field):
            return field
    best = None
    for field in fields or []:
        for alias in field_aliases(field):
            if requested in alias or alias in requested:
                score = len(alias)
                if not best or score > best[0]:
                    best = (score, field)
    return best[1] if best else None


def field_aliases(field):
    label = normalize(field_label(field))
    fieldname = normalize(str(field.get("fieldname") or "").replace("_", " "))
    aliases = {label, fieldname}
    text = f"{fieldname} {label}"
    generic = {
        "phone": ("phone", "phone number", "mobile", "mobile number", "contact number"),
        "email": ("email", "email id", "mail"),
        "website": ("website", "web site", "url"),
        "territory": ("territory", "region", "area"),
        "department": ("department", "team"),
        "company": ("company", "organization"),
        "status": ("status", "state"),
        "owner": ("owner", "assignee", "assigned to", "sales person"),
        "credit_limit": ("credit limit", "limit"),
        "gstin": ("gst", "gst number", "tax id", "tax number"),
    }
    for key, values in generic.items():
        key_text = key.replace("_", " ")
        if key_text in text:
            aliases.update(values)
    return {item for item in aliases if item}


def change_rows(current, changes, fields):
    field_map = {field.get("fieldname"): field for field in fields or []}
    rows = []
    for fieldname, new_value in (changes or {}).items():
        field = field_map.get(fieldname, {"fieldname": fieldname})
        rows.append(
            {
                "fieldname": fieldname,
                "label": field_label(field),
                "old_value": (current or {}).get(fieldname),
                "new_value": new_value,
            }
        )
    return rows


def analyze_impact(doctype, changes, fields):
    field_map = {field.get("fieldname"): field for field in fields or []}
    impacts = []
    for fieldname in (changes or {}).keys():
        field = field_map.get(fieldname, {"fieldname": fieldname})
        label = field_label(field)
        normalized = normalize(f"{fieldname} {label}")
        if any(token in normalized for token in ("company", "currency", "warehouse", "territory", "customer group", "supplier group", "item group")):
            impacts.append(f"Future transactions and reports that use {label} may reflect the new value.")
        elif any(token in normalized for token in ("status", "workflow", "stage")):
            impacts.append(f"Workflow, dashboard, and follow-up views may change based on the new {label}.")
        elif any(token in normalized for token in ("owner", "assigned", "sales person", "user", "role", "permission")):
            impacts.append(f"Responsibility or access-related views may change based on the new {label}.")
        elif any(token in normalized for token in ("price", "rate", "credit", "amount", "limit")):
            impacts.append(f"Financial review may be needed because {label} affects commercial values.")
    return dedupe(impacts)


def first_existing_field(fields, fieldnames):
    for fieldname in fieldnames:
        for field in fields or []:
            if field.get("fieldname") == fieldname:
                return field
    return None


def first_status_field(fields):
    for field in fields or []:
        if normalize(field.get("fieldname")) in {"status", "workflow_state", "state"}:
            return field
    for field in fields or []:
        if "status" in normalize(field_label(field)):
            return field
    return None


def first_assignment_field(fields):
    for preferred in ("owner", "assigned_to", "opportunity_owner", "sales_person", "project_manager"):
        field = first_existing_field(fields, (preferred,))
        if field:
            return field
    for field in fields or []:
        text = normalize(f"{field.get('fieldname')} {field_label(field)}")
        if any(token in text for token in ("owner", "assigned", "sales person", "manager")):
            return field
    return None


def best_select_value(field, candidates):
    options = split_options(field.get("options"))
    if not options:
        return candidates[0] if candidates else None
    normalized = {normalize(option): option for option in options}
    for candidate in candidates or []:
        if normalize(candidate) in normalized:
            return normalized[normalize(candidate)]
    for candidate in candidates or []:
        for option in options:
            if normalize(candidate) in normalize(option) or normalize(option) in normalize(candidate):
                return option
    return None


def split_options(options):
    if not options:
        return []
    if isinstance(options, (list, tuple)):
        return [str(item).strip() for item in options if str(item).strip()]
    return [line.strip() for line in str(options).replace(",", "\n").splitlines() if line.strip()]


def normalize_target_options(options):
    normalized = []
    for option in options or []:
        normalized.append(
            {
                "doctype": option.get("doctype"),
                "docname": option.get("docname"),
                "label": option.get("label") or " ".join(item for item in (option.get("doctype"), option.get("docname")) if item),
            }
        )
    return normalized


def encode_record_choice(doctype, docname):
    return f"{doctype}::{docname}"


def find_field(fields, fieldname):
    for field in fields or []:
        if field.get("fieldname") == fieldname:
            return field
    return None


def require_update_target(doctype, docname, fieldname):
    missing = [label for label, value in (("doctype", doctype), ("docname", docname), ("fieldname", fieldname)) if not value]
    if missing:
        raise ValueError(f"Missing update target: {', '.join(missing)}")


def values_match(left, right):
    if left in (None, "") and right in (None, ""):
        return True
    return str(left) == str(right)


def should_use_current_record(message, context_object):
    if not context_object.get("doctype") or not context_object.get("docname"):
        return False
    text = normalize(message)
    return any(phrase in text for phrase in ("this", "current", "this record", "current record", "this customer", "this user"))


def current_record_matches_doctype(context_object, doctype):
    if not context_object.get("doctype") or not context_object.get("docname"):
        return False
    return normalize(context_object.get("doctype")) == normalize(doctype)


def should_restart_pending_update(message, intent=None):
    text = clean_text(message)
    if not text or is_cancel_message(text):
        return False
    structured = getattr(intent, "structured_intent", None) or {}
    if structured.get("intent_category") != "Update":
        return False
    stripped = strip_update_prefix(text)
    return bool(stripped and normalize(stripped) != normalize(text))


def is_cancel_message(message):
    return normalize(message) in {"cancel", "cancel update", "stop", "never mind", "nevermind"}


def field_label(field):
    return (field or {}).get("label") or str((field or {}).get("fieldname") or "Field").replace("_", " ").title()


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).strip()


def clean_query(value):
    return clean_text(value).strip(".,;:()[]{}\"'")


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


def dedupe(values):
    result = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


_SERVICE = None


def get_record_update_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RecordUpdateService()
    return _SERVICE
