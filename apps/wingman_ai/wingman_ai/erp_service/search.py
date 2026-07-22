from wingman_ai.erp_service.config import clamp_page_size, normalize_page


class ERPSearchService:
    def __init__(self, repository, metadata_service=None, config=None):
        self.repository = repository
        self.metadata_service = metadata_service
        self.config = config

    def list_documents(self, doctype, fields=None, filters=None, order_by=None, page=1, page_size=None):
        page = normalize_page(page)
        page_size = clamp_page_size(page_size, self.config)
        return {
            "doctype": doctype,
            "page": page,
            "page_size": page_size,
            "rows": self.repository.list_documents(
                doctype,
                fields=fields or ["name"],
                filters=filters or {},
                order_by=order_by,
                page=page,
                page_size=page_size,
            ),
        }

    def search_documents(self, doctype, text=None, fields=None, filters=None, order_by=None, page=1, page_size=None):
        page = normalize_page(page)
        page_size = clamp_page_size(page_size, self.config)
        search_fields = self.get_search_fields(doctype)
        return {
            "doctype": doctype,
            "query": text,
            "page": page,
            "page_size": page_size,
            "search_fields": search_fields,
            "rows": self.repository.search_documents(
                doctype,
                text=text,
                fields=fields or ["name"],
                filters=filters or {},
                search_fields=search_fields,
                order_by=order_by,
                page=page,
                page_size=page_size,
            ),
        }

    def autocomplete(self, doctype, text=None, page_size=None):
        return self.search_documents(doctype=doctype, text=text, fields=["name"], page_size=page_size)

    def global_search(self, text=None, doctypes=None, fields=None, page_size=None):
        page_size = clamp_page_size(page_size, self.config)
        selected_doctypes = list(doctypes or self.get_global_search_doctypes())
        results = []
        for doctype in selected_doctypes[:page_size]:
            rows = self.search_documents(
                doctype=doctype,
                text=text,
                fields=fields or ["name"],
                page=1,
                page_size=min(5, page_size),
            ).get("rows", [])
            if rows:
                results.append({"doctype": doctype, "rows": rows})
        return {"query": text, "doctypes": selected_doctypes, "results": results}

    def get_search_fields(self, doctype):
        if self.metadata_service:
            try:
                metadata = self.metadata_service.get_search_metadata(doctype)
                fields = metadata.get("autocomplete_fields") or metadata.get("search_fields") or []
                return fields or ["name"]
            except Exception:
                pass
        return ["name"]

    def get_global_search_doctypes(self):
        if not self.metadata_service:
            return []
        try:
            rows = self.metadata_service.list_doctypes(include_child_tables=False)
        except Exception:
            return []
        doctypes = []
        for row in rows or []:
            if isinstance(row, dict):
                value = row.get("name") or row.get("doctype")
            else:
                value = getattr(row, "name", None) or str(row)
            if value:
                doctypes.append(value)
        return doctypes
