from copy import deepcopy
import re

from wingman_ai.logging.service import log_info


class FrappeDocumentRepository:
    """ERP data access boundary for the Universal ERP Service Layer."""

    def __init__(self, frappe_module=None):
        if frappe_module is None:
            import frappe as frappe_module

        self.frappe = frappe_module

    def read(self, doctype, docname):
        log_info("ERP repository read", doctype=doctype)
        return self.frappe.get_doc(doctype, docname)

    def exists(self, doctype, docname):
        if not docname:
            return False
        try:
            return bool(self.frappe.db.exists(doctype, docname))
        except Exception:
            return False

    def create(self, doctype, data):
        log_info("ERP repository create", doctype=doctype)
        doc = self.frappe.new_doc(doctype)
        doc.update(data or {})
        doc.insert()
        return doc

    def update(self, doctype, docname, data):
        log_info("ERP repository update", doctype=doctype)
        doc = self.read(doctype, docname)
        doc.update(data or {})
        doc.save()
        return doc

    def delete(self, doctype, docname):
        log_info("ERP repository delete", doctype=doctype)
        self.frappe.delete_doc(doctype, docname)
        return {"doctype": doctype, "docname": docname, "deleted": True}

    def list_documents(self, doctype, fields=None, filters=None, order_by=None, page=1, page_size=20):
        log_info("ERP repository list", doctype=doctype, page_size=page_size)
        return self.frappe.get_list(
            doctype,
            fields=fields or ["name"],
            filters=filters or {},
            order_by=order_by,
            limit_start=(page - 1) * page_size,
            limit_page_length=page_size,
        )

    def search_documents(self, doctype, text=None, fields=None, filters=None, search_fields=None, order_by=None, page=1, page_size=20):
        log_info("ERP repository search", doctype=doctype, page_size=page_size)
        kwargs = {
            "fields": fields or ["name"],
            "filters": filters or {},
            "order_by": order_by,
            "limit_start": (page - 1) * page_size,
            "limit_page_length": page_size,
        }
        if text and search_fields:
            kwargs["or_filters"] = build_or_filters(search_fields, text)
        return self.frappe.get_list(
            doctype,
            **kwargs,
        )

    def get_meta(self, doctype):
        return self.frappe.get_meta(doctype)

    def has_permission(self, doctype, permission_type="read", docname=None, user=None):
        try:
            if docname:
                return bool(self.frappe.has_permission(doc=self.read(doctype, docname), ptype=permission_type, user=user))
            return bool(self.frappe.has_permission(doctype=doctype, ptype=permission_type, user=user))
        except Exception:
            return False

    def apply_workflow(self, doctype, docname, action):
        from frappe.model.workflow import apply_workflow

        log_info("ERP repository workflow action", doctype=doctype)
        return apply_workflow(self.read(doctype, docname), action)

    def validate_document(self, doctype, data, docname=None, operation="create"):
        log_info("ERP repository validation hook", doctype=doctype)
        self.validate_storage_ready(doctype)
        doc = self.read(doctype, docname) if docname else self.frappe.new_doc(doctype)
        if docname and hasattr(doc, "get_doc_before_save"):
            # Frappe initializes this snapshot inside Document.save() before
            # running before_save hooks. Preflight invokes those hooks without
            # writing, so it must reproduce the same lifecycle state.
            doc._doc_before_save = doc.get_doc_before_save()
        doc.update(data or {})
        if operation == "create":
            run_document_method(doc, "before_insert")
        run_document_method(doc, "before_validate")
        doc.run_method("validate")
        run_document_method(doc, "before_save")
        prepare_child_rows_for_validation(doc, doctype)
        run_internal_document_validation(doc)
        return doc

    def validate_storage_ready(self, doctype):
        meta = self.get_meta(doctype)
        if get_meta_flag(meta, "issingle") or get_meta_flag(meta, "is_virtual"):
            return
        db = getattr(self.frappe, "db", None)
        if not db or not hasattr(db, "table_exists"):
            return
        table_name = f"tab{doctype}"
        try:
            exists = bool(db.table_exists(doctype))
        except Exception as exc:
            raise RuntimeError(format_missing_table_prerequisite(str(exc), fallback_doctype=doctype))
        if not exists:
            raise RuntimeError(
                f"Talisma OneCampus database table {table_name} is missing. Run bench migrate for the site, then clear cache and reload Desk."
            )

    def serialize_doc(self, doc):
        if hasattr(doc, "as_dict"):
            return doc.as_dict()
        return doc


def build_or_filters(search_fields, text):
    escaped = str(text or "").strip()
    return [[fieldname, "like", f"%{escaped}%"] for fieldname in search_fields if fieldname]


def run_document_method(doc, method):
    if hasattr(doc, "run_method"):
        doc.run_method(method)


def prepare_child_rows_for_validation(doc, doctype):
    """Give unsaved child rows a temporary parent during non-writing preflight."""
    if not hasattr(doc, "get_all_children"):
        return
    parent_name = getattr(doc, "name", None) or f"new-{str(doctype or 'document').lower().replace(' ', '-')}"
    for child in doc.get_all_children() or []:
        if not getattr(child, "parent", None):
            child.parent = parent_name
        if not getattr(child, "parenttype", None):
            child.parenttype = doctype


def run_internal_document_validation(doc):
    if hasattr(doc, "_validate"):
        doc._validate()


def get_meta_flag(meta, fieldname):
    if isinstance(meta, dict):
        return bool(meta.get(fieldname))
    if hasattr(meta, "get"):
        try:
            return bool(meta.get(fieldname))
        except TypeError:
            pass
    return bool(getattr(meta, fieldname, None))


def format_missing_table_prerequisite(message, fallback_doctype=None):
    match = re.search(r"Table ['\"](?P<table>[^'\"]+)['\"] doesn't exist", message or "", re.IGNORECASE)
    if match:
        table = str(match.group("table") or "").split(".")[-1]
        doctype = table[3:] if table.lower().startswith("tab") else table
    else:
        doctype = fallback_doctype or "the requested DocType"
    return (
        f"Talisma OneCampus setup is incomplete: the database table for {doctype} is missing. "
        "Run bench migrate for the site, clear cache, and reload Desk."
    )


class MemoryDocumentRepository:
    def __init__(self, metas=None, documents=None, permissions=None):
        self.metas = metas or {}
        self.documents = deepcopy(documents or {})
        self.permissions = permissions or {}

    def read(self, doctype, docname):
        key = (doctype, docname)
        if key not in self.documents:
            raise KeyError(docname)
        return MemoryDocument(doctype=doctype, data=deepcopy(self.documents[key]))

    def exists(self, doctype, docname):
        return (doctype, docname) in self.documents

    def create(self, doctype, data):
        name = (data or {}).get("name") or f"{doctype}-NEW"
        stored = dict(data or {}, name=name)
        self.documents[(doctype, name)] = stored
        return MemoryDocument(doctype=doctype, data=deepcopy(stored))

    def update(self, doctype, docname, data):
        doc = self.read(doctype, docname).as_dict()
        doc.update(data or {})
        self.documents[(doctype, docname)] = doc
        return MemoryDocument(doctype=doctype, data=deepcopy(doc))

    def delete(self, doctype, docname):
        if not self.exists(doctype, docname):
            raise KeyError(docname)
        del self.documents[(doctype, docname)]
        return {"doctype": doctype, "docname": docname, "deleted": True}

    def list_documents(self, doctype, fields=None, filters=None, order_by=None, page=1, page_size=20):
        rows = []
        for (row_doctype, _name), data in self.documents.items():
            if row_doctype == doctype and matches_filters(data, filters):
                rows.append(project_fields(data, fields))
        return rows[(page - 1) * page_size : page * page_size]

    def search_documents(self, doctype, text=None, fields=None, filters=None, search_fields=None, order_by=None, page=1, page_size=20):
        lowered = str(text or "").lower()
        rows = []
        for (row_doctype, _name), data in self.documents.items():
            if row_doctype != doctype or not matches_filters(data, filters):
                continue
            if lowered and not any(lowered in str(data.get(fieldname, "")).lower() for fieldname in search_fields or ["name"]):
                continue
            rows.append(project_fields(data, fields))
        return rows[(page - 1) * page_size : page * page_size]

    def get_meta(self, doctype):
        if doctype not in self.metas:
            raise KeyError(doctype)
        return self.metas[doctype]

    def has_permission(self, doctype, permission_type="read", docname=None, user=None):
        return self.permissions.get((doctype, permission_type), self.permissions.get(doctype, True))

    def apply_workflow(self, doctype, docname, action):
        doc = self.read(doctype, docname).as_dict()
        doc["workflow_action"] = action
        self.documents[(doctype, docname)] = doc
        return MemoryDocument(doctype=doctype, data=deepcopy(doc))

    def validate_document(self, doctype, data, docname=None, operation="create"):
        return MemoryDocument(doctype=doctype, data=dict(data or {}, name=docname or (data or {}).get("name")))

    def serialize_doc(self, doc):
        return doc.as_dict() if hasattr(doc, "as_dict") else doc


class MemoryDocument:
    def __init__(self, doctype, data):
        self.doctype = doctype
        self.data = data
        self.name = data.get("name")

    def as_dict(self):
        return dict(self.data)


def matches_filters(data, filters):
    if not filters:
        return True
    if isinstance(filters, list):
        return all(matches_filters(data, item) for item in filters if isinstance(item, dict))
    for key, expected in (filters or {}).items():
        if data.get(key) != expected:
            return False
    return True


def project_fields(data, fields):
    selected = fields or ["name"]
    return {fieldname: data.get(fieldname) for fieldname in selected}
