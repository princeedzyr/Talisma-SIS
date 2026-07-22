import re

from wingman_ai.application.navigation_resolver import resolve_navigation_target
from wingman_ai.business_skills.record_creation.service import SUPPORTED_CREATE_DOCTYPES
from wingman_ai.business_skills.record_delete.formatter import (
    format_delete_not_found,
    format_delete_review,
    format_delete_selection,
)
from wingman_ai.erp_service import get_erp_service


DELETE_WORDS = ("delete", "remove", "discard")


class RecordDeleteService:
    def __init__(self, erp_service=None):
        self.erp_service = erp_service or get_erp_service()

    def handle_message(self, message, context=None, intent=None):
        context = context or {}
        target = self.resolve_target(message, context=context)
        if target.get("ambiguous"):
            prepared = self.build_record_selection(message, target)
            prepared["message"] = format_delete_selection(prepared)
            return prepared

        if not target.get("doctype") or not target.get("docname"):
            return self.not_found(target.get("query") or message)

        read_response = self.erp_service.read_document(target["doctype"], target["docname"], user=context.get("user"))
        if not read_response.get("success"):
            return self.not_found(target.get("query") or target.get("docname"))

        current = read_response.get("result") or {}
        validation = self.validate_delete(target["doctype"], target["docname"], user=context.get("user"))
        issues = extract_validation_issues(validation)
        prepared = {
            "operation": "delete",
            "supported": True,
            "doctype": target["doctype"],
            "docname": target["docname"],
            "title": current.get("title") or current.get("customer_name") or current.get("lead_name") or current.get("name"),
            "current": current,
            "validation": validation,
            "validation_issues": issues,
            "ready": not issues,
        }
        prepared["message"] = format_delete_review(prepared)
        return prepared

    def resolve_target(self, message, context=None):
        context = context or {}
        context_object = context.get("object") or {}
        if should_use_current_record(message, context_object):
            return {
                "doctype": context_object.get("doctype"),
                "docname": context_object.get("docname"),
                "query": "current record",
            }

        query = extract_delete_target_query(message)
        if not query and context_object.get("doctype") and context_object.get("docname"):
            return {
                "doctype": context_object.get("doctype"),
                "docname": context_object.get("docname"),
                "query": "current record",
            }
        if not query:
            return {"query": message}

        target = resolve_navigation_target(f"open {query}", context=context)
        if target.kind == "document":
            return {"doctype": target.doctype, "docname": target.docname, "query": query}
        if target.kind in ("ambiguous_document", "document_type_mismatch") and target.options:
            return {"ambiguous": True, "query": query, "options": normalize_options(target.options)}
        fallback = self.resolve_target_with_search(query, user=context.get("user"))
        if fallback:
            return fallback
        return {"query": query, "doctype": getattr(target, "doctype", ""), "docname": getattr(target, "docname", "")}

    def resolve_target_with_search(self, query, user=None):
        request = split_doctype_query(query, discover_doctypes(self.erp_service))
        if not request:
            return None
        doctype, doc_query = request
        if not doc_query:
            return None
        exact = self.erp_service.read_document(doctype, doc_query, user=user)
        if exact.get("success"):
            return {"doctype": doctype, "docname": doc_query, "query": query}
        response = self.erp_service.search_documents(doctype, text=doc_query, fields=["name"], page=1, page_size=6, user=user)
        rows = ((response.get("result") or {}).get("rows") or []) if response.get("success") else []
        if len(rows) == 1:
            return {"doctype": doctype, "docname": rows[0].get("name"), "query": query}
        if len(rows) > 1:
            return {
                "ambiguous": True,
                "query": query,
                "options": [{"doctype": doctype, "docname": row.get("name"), "label": row.get("name")} for row in rows if row.get("name")],
            }
        return None

    def build_record_selection(self, message, target):
        return {
            "operation": "delete",
            "supported": True,
            "stage": "record_selection",
            "query": target.get("query") or message,
            "options": target.get("options") or [],
            "ready": False,
        }

    def validate_delete(self, doctype, docname, user=None):
        if not hasattr(self.erp_service, "validate_document"):
            return {"success": True, "validation_issues": []}
        return self.erp_service.validate_document(doctype, docname=docname, operation="delete", user=user)

    def delete_record(self, doctype, docname, user=None):
        return self.erp_service.delete_document(doctype, docname, user=user)

    def not_found(self, query=None):
        return {
            "operation": "delete",
            "supported": True,
            "ready": False,
            "message": format_delete_not_found(query),
        }


def extract_delete_target_query(message):
    text = clean_query(message)
    lowered = normalize(text)
    for word in DELETE_WORDS:
        if lowered == word:
            return ""
        match = re.match(rf"^\s*{re.escape(word)}\s+", text, flags=re.IGNORECASE)
        if match:
            return clean_query(text[match.end() :])
    return text


def should_use_current_record(message, context_object):
    if not context_object.get("doctype") or not context_object.get("docname"):
        return False
    text = normalize(message)
    return any(token in text for token in ("this", "current", "this record", "current record"))


def normalize_options(options):
    result = []
    for option in options or []:
        if not option.get("doctype") or not option.get("docname"):
            continue
        result.append(
            {
                "doctype": option.get("doctype"),
                "docname": option.get("docname"),
                "label": option.get("label") or option.get("docname"),
            }
        )
    return result


def discover_doctypes(erp_service):
    metadata_service = getattr(erp_service, "metadata_service", None)
    if metadata_service and hasattr(metadata_service, "list_doctypes"):
        try:
            return [item.get("name") for item in metadata_service.list_doctypes(include_child_tables=False) or [] if item.get("name")]
        except Exception:
            pass
    if hasattr(erp_service, "metadata") and isinstance(getattr(erp_service, "metadata"), dict):
        return list(erp_service.metadata.keys())
    return sorted(SUPPORTED_CREATE_DOCTYPES)


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


def extract_validation_issues(response):
    if not isinstance(response, dict):
        return []
    issues = response.get("validation_issues") or []
    if issues:
        return [dict(issue) for issue in issues]
    result = response.get("result") or {}
    return [dict(issue) for issue in result.get("issues") or []]


def clean_query(value):
    return " ".join(str(value or "").strip().strip(".,;:()[]{}\"'").split())


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", str(value or "").lower())).strip()


_SERVICE = None


def get_record_delete_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RecordDeleteService()
    return _SERVICE
