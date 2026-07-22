import re

from wingman_ai.erp_service import get_erp_service


class CRMMetadataService:
    """Loads Talisma OneCampus CRM metadata without hardcoding individual CRM DocTypes."""

    def __init__(self, erp_service=None, module="CRM"):
        self.erp_service = erp_service or get_erp_service()
        self.module = module
        self.metadata_service = getattr(self.erp_service, "metadata_service", None)

    def list_doctypes(self, include_child_tables=False):
        rows = self._list_from_metadata_service(include_child_tables=include_child_tables)
        if not rows:
            rows = self._list_from_erp_metadata()
        return [self.normalize_doctype_row(row) for row in rows if doctype_name(row)]

    def list_crm_doctypes(self, include_child_tables=False):
        rows = []
        for row in self.list_doctypes(include_child_tables=include_child_tables):
            if not include_child_tables and row.get("is_child_table"):
                continue
            metadata = None if row.get("module") else self.get_metadata(row.get("name"))
            if self.is_crm_doctype(row, metadata=metadata):
                rows.append(row)
        return sorted(rows, key=lambda item: item.get("name") or "")

    def get_metadata(self, doctype):
        if not doctype:
            return {}
        if hasattr(self.erp_service, "get_metadata"):
            response = self.erp_service.get_metadata(doctype)
            metadata = normalize_service_result(response)
            if metadata:
                return metadata
        if self.metadata_service and hasattr(self.metadata_service, "get_doctype_metadata"):
            try:
                return self.metadata_service.get_doctype_metadata(doctype) or {}
            except Exception:
                return {}
        return {}

    def is_crm_doctype(self, row, metadata=None):
        module = normalize_module(read_attr(row, "module") or read_attr(metadata or {}, "module"))
        return module == normalize_module(self.module)

    def normalize_doctype_row(self, row):
        return {
            "name": doctype_name(row),
            "module": read_attr(row, "module"),
            "custom": truthy(read_attr(row, "custom")),
            "is_child_table": truthy(read_attr(row, "is_child_table")) or truthy(read_attr(row, "istable")),
            "is_single": truthy(read_attr(row, "is_single")) or truthy(read_attr(row, "issingle")),
            "is_submittable": truthy(read_attr(row, "is_submittable")),
            "modified": read_attr(row, "modified"),
        }

    def _list_from_metadata_service(self, include_child_tables=False):
        if not self.metadata_service or not hasattr(self.metadata_service, "list_doctypes"):
            return []
        for kwargs in (
            {"module": self.module, "include_child_tables": include_child_tables},
            {"include_child_tables": include_child_tables},
            {},
        ):
            try:
                rows = self.metadata_service.list_doctypes(**kwargs) or []
                if rows:
                    return rows
            except TypeError:
                continue
            except Exception:
                return []
        return []

    def _list_from_erp_metadata(self):
        metadata = getattr(self.erp_service, "metadata", None)
        if not isinstance(metadata, dict):
            return []
        rows = []
        for doctype, meta in metadata.items():
            rows.append(
                {
                    "name": doctype,
                    "module": read_attr(meta, "module"),
                    "is_child_table": truthy(read_attr(meta, "is_child_table")) or truthy(read_attr(meta, "istable")),
                    "is_single": truthy(read_attr(meta, "is_single")) or truthy(read_attr(meta, "issingle")),
                }
            )
        return rows


def normalize_service_result(response):
    if isinstance(response, dict):
        if isinstance(response.get("result"), dict):
            return response.get("result") or {}
        if response.get("doctype") or response.get("fields"):
            return response
    return response if isinstance(response, dict) else {}


def doctype_name(row):
    return read_attr(row, "name") or read_attr(row, "doctype")


def read_attr(value, key, default=None):
    if not value:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    if hasattr(value, "get"):
        try:
            return value.get(key, default)
        except TypeError:
            pass
    return getattr(value, key, default)


def truthy(value):
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "none", "null")
    return bool(value)


def normalize_module(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())
