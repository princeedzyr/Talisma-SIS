from wingman_ai.erp_intelligence.models import read_attr


class FrappeERPAdapter:
    """Small boundary around Frappe APIs used by the ERP intelligence layer."""

    REGISTRY_DOCTYPE = "DocType"
    REGISTRY_MODULE = "Module Def"
    REGISTRY_WORKFLOW = "Workflow"

    def __init__(self, frappe_module=None):
        if frappe_module is None:
            import frappe as frappe_module

        self.frappe = frappe_module

    def list_modules(self):
        return self.get_list(
            self.REGISTRY_MODULE,
            fields=["name", "app_name", "custom"],
            order_by="name asc",
        )

    def list_doctypes(self, module=None, limit=None):
        filters = {}
        if module:
            filters["module"] = module

        return self.get_list(
            self.REGISTRY_DOCTYPE,
            fields=[
                "name",
                "module",
                "custom",
                "istable",
                "issingle",
                "is_submittable",
                "modified",
            ],
            filters=filters,
            order_by="module asc, name asc",
            limit_page_length=limit,
        )

    def get_meta(self, doctype):
        return self.frappe.get_meta(doctype)

    def get_doc(self, doctype, name):
        return self.frappe.get_doc(doctype, name)

    def get_list(self, doctype, fields=None, filters=None, order_by=None, limit_page_length=None):
        kwargs = {
            "fields": fields or ["name"],
            "filters": filters or {},
        }
        if order_by:
            kwargs["order_by"] = order_by
        if limit_page_length:
            kwargs["limit_page_length"] = limit_page_length

        try:
            return self.frappe.get_list(doctype, **kwargs)
        except Exception:
            return []

    def list_workflows(self, doctype=None):
        filters = {"is_active": 1}
        if doctype:
            filters["document_type"] = doctype

        return self.get_list(
            self.REGISTRY_WORKFLOW,
            fields=["name", "document_type", "workflow_state_field", "is_active"],
            filters=filters,
            order_by="document_type asc, name asc",
        )

    def get_workflow(self, name):
        return self.get_doc(self.REGISTRY_WORKFLOW, name)

    def has_permission(self, doctype, permission_type="read", docname=None, user=None):
        try:
            if docname:
                doc = self.get_doc(doctype, docname)
                return bool(self.frappe.has_permission(doc=doc, ptype=permission_type, user=user))
            return bool(self.frappe.has_permission(doctype=doctype, ptype=permission_type, user=user))
        except TypeError:
            try:
                return bool(self.frappe.has_permission(doctype=doctype, ptype=permission_type))
            except Exception:
                return False
        except Exception:
            return False

    def get_user_roles(self, user=None):
        try:
            return list(self.frappe.get_roles(user))
        except Exception:
            return []

    def get_cache(self):
        try:
            return self.frappe.cache()
        except Exception:
            return None

    def log(self, level, message, **kwargs):
        from wingman_ai.logging.service import write_log

        write_log(level, message, **kwargs)


class MemoryERPAdapter:
    """Test adapter with the same surface area as FrappeERPAdapter."""

    def __init__(self, modules=None, doctypes=None, metas=None, workflows=None, permissions=None, roles=None, docs=None):
        self.modules = modules or []
        self.doctypes = doctypes or []
        self.metas = metas or {}
        self.workflows = workflows or {}
        self.permissions = permissions or {}
        self.roles = roles or []
        self.docs = docs or {}
        self.cache_store = {}

    def list_modules(self):
        return list(self.modules)

    def list_doctypes(self, module=None, limit=None):
        rows = [row for row in self.doctypes if not module or read_attr(row, "module") == module]
        return rows[:limit] if limit else rows

    def get_meta(self, doctype):
        if doctype not in self.metas:
            raise KeyError(doctype)
        return self.metas[doctype]

    def get_doc(self, doctype, name):
        if doctype == FrappeERPAdapter.REGISTRY_WORKFLOW:
            return self.workflows[name]
        return self.docs[(doctype, name)]

    def list_workflows(self, doctype=None):
        rows = []
        for name, workflow in self.workflows.items():
            document_type = read_attr(workflow, "document_type")
            if doctype and document_type != doctype:
                continue
            rows.append(
                {
                    "name": name,
                    "document_type": document_type,
                    "workflow_state_field": read_attr(workflow, "workflow_state_field"),
                    "is_active": read_attr(workflow, "is_active", 1),
                }
            )
        return rows

    def get_workflow(self, name):
        return self.workflows[name]

    def has_permission(self, doctype, permission_type="read", docname=None, user=None):
        return self.permissions.get((doctype, permission_type), self.permissions.get(doctype, True))

    def get_user_roles(self, user=None):
        return list(self.roles)

    def get_cache(self):
        return None

    def log(self, level, message, **kwargs):
        return None
