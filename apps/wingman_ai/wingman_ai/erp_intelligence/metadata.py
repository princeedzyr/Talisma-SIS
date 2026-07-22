from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter
from wingman_ai.erp_intelligence.models import read_attr, read_bool, split_csv, unique


LINK_FIELD_TYPES = {"Link", "Dynamic Link"}
CHILD_TABLE_FIELD_TYPES = {"Table", "Table MultiSelect"}
DISPLAY_FIELD_TYPES = {
    "Data",
    "Select",
    "Link",
    "Dynamic Link",
    "Int",
    "Float",
    "Currency",
    "Date",
    "Datetime",
    "Check",
    "Small Text",
    "Text",
    "Long Text",
}


class MetadataDiscoveryService:
    def __init__(self, adapter=None, config=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()

    def list_modules(self):
        self.adapter.log("info", "ERP intelligence module discovery started")
        modules = []
        for row in self.adapter.list_modules():
            modules.append(
                {
                    "name": read_attr(row, "name"),
                    "app_name": read_attr(row, "app_name"),
                    "custom": read_bool(row, "custom"),
                }
            )
        return modules

    def list_doctypes(self, module=None, include_child_tables=True):
        self.adapter.log("info", "ERP intelligence doctype discovery started", module=module)
        rows = self.adapter.list_doctypes(module=module, limit=self.config.max_doctypes)
        doctypes = []
        for row in rows:
            if not include_child_tables and read_bool(row, "istable"):
                continue
            doctypes.append(
                {
                    "name": read_attr(row, "name"),
                    "module": read_attr(row, "module"),
                    "custom": read_bool(row, "custom"),
                    "is_child_table": read_bool(row, "istable"),
                    "is_single": read_bool(row, "issingle"),
                    "is_submittable": read_bool(row, "is_submittable"),
                    "modified": read_attr(row, "modified"),
                }
            )
        return doctypes

    def get_doctype_metadata(self, doctype):
        self.adapter.log("info", "ERP intelligence doctype metadata discovery started", doctype=doctype)
        meta = self.adapter.get_meta(doctype)
        fields = [self.serialize_field(field) for field in list(read_attr(meta, "fields", []))[: self.config.max_fields_per_doctype]]
        workflows = self.get_workflow_metadata(doctype)

        return {
            "doctype": read_attr(meta, "name", doctype),
            "module": read_attr(meta, "module"),
            "custom": read_bool(meta, "custom"),
            "is_child_table": read_bool(meta, "istable"),
            "is_single": read_bool(meta, "issingle"),
            "is_submittable": read_bool(meta, "is_submittable"),
            "title_field": read_attr(meta, "title_field"),
            "image_field": read_attr(meta, "image_field"),
            "search_fields": split_csv(read_attr(meta, "search_fields")),
            "sort_field": read_attr(meta, "sort_field"),
            "sort_order": read_attr(meta, "sort_order"),
            "autoname": read_attr(meta, "autoname"),
            "naming": self.discover_naming(meta, fields),
            "fields": fields,
            "mandatory_fields": [field for field in fields if field["mandatory"] or field.get("mandatory_depends_on")],
            "default_values": {
                field["fieldname"]: field["default"]
                for field in fields
                if field.get("fieldname") and field.get("default") not in (None, "")
            },
            "link_fields": [field for field in fields if field["fieldtype"] in LINK_FIELD_TYPES],
            "child_tables": [field for field in fields if field["fieldtype"] in CHILD_TABLE_FIELD_TYPES],
            "permissions": self.serialize_permissions(read_attr(meta, "permissions", [])),
            "search": self.discover_search_metadata(meta, fields),
            "status": self.discover_status_metadata(workflows, fields),
            "indexes": self.discover_indexes(meta, fields),
            "workflows": workflows,
        }

    def serialize_field(self, field):
        fieldtype = read_attr(field, "fieldtype")
        serialized = {
            "fieldname": read_attr(field, "fieldname"),
            "label": read_attr(field, "label"),
            "fieldtype": fieldtype,
            "options": read_attr(field, "options"),
            "mandatory": read_bool(field, "reqd"),
            "default": read_attr(field, "default"),
            "read_only": read_bool(field, "read_only"),
            "hidden": read_bool(field, "hidden"),
            "in_list_view": read_bool(field, "in_list_view"),
            "in_standard_filter": read_bool(field, "in_standard_filter"),
            "in_global_search": read_bool(field, "in_global_search"),
            "search_index": read_bool(field, "search_index"),
            "unique": read_bool(field, "unique"),
            "set_only_once": read_bool(field, "set_only_once"),
            "depends_on": read_attr(field, "depends_on"),
            "mandatory_depends_on": read_attr(field, "mandatory_depends_on"),
            "fetch_from": read_attr(field, "fetch_from"),
            "precision": read_attr(field, "precision"),
            "length": read_attr(field, "length"),
            "permlevel": read_attr(field, "permlevel", 0),
            "is_virtual": read_bool(field, "is_virtual"),
        }
        if fieldtype == "Link":
            serialized["target_doctype"] = serialized["options"]
        if fieldtype == "Dynamic Link":
            serialized["dynamic_target_field"] = serialized["options"]
        if fieldtype in CHILD_TABLE_FIELD_TYPES:
            serialized["child_doctype"] = serialized["options"]
        return serialized

    def serialize_permissions(self, permissions):
        serialized = []
        for permission in permissions or []:
            serialized.append(
                {
                    "role": read_attr(permission, "role"),
                    "permlevel": read_attr(permission, "permlevel", 0),
                    "read": read_bool(permission, "read"),
                    "write": read_bool(permission, "write"),
                    "create": read_bool(permission, "create"),
                    "delete": read_bool(permission, "delete"),
                    "submit": read_bool(permission, "submit"),
                    "cancel": read_bool(permission, "cancel"),
                    "amend": read_bool(permission, "amend"),
                    "report": read_bool(permission, "report"),
                    "export": read_bool(permission, "export"),
                    "import": read_bool(permission, "import"),
                    "share": read_bool(permission, "share"),
                    "print": read_bool(permission, "print"),
                    "email": read_bool(permission, "email"),
                    "if_owner": read_bool(permission, "if_owner"),
                }
            )
        return serialized

    def discover_naming(self, meta, fields):
        autoname = read_attr(meta, "autoname")
        naming = {
            "autoname": autoname,
            "rule": read_attr(meta, "naming_rule"),
            "series_field": None,
            "series_options": [],
        }
        if isinstance(autoname, str) and ":" in autoname:
            rule, series_field = autoname.split(":", 1)
            naming["rule"] = rule
            naming["series_field"] = series_field
            for field in fields:
                if field.get("fieldname") == series_field:
                    naming["series_options"] = split_csv(field.get("options"))
                    break
        return naming

    def discover_search_metadata(self, meta, fields):
        title_field = read_attr(meta, "title_field")
        configured_search_fields = split_csv(read_attr(meta, "search_fields"))
        visible_fields = [
            field["fieldname"]
            for field in fields
            if field.get("fieldname")
            and not field.get("hidden")
            and field.get("fieldtype") in DISPLAY_FIELD_TYPES
            and (field.get("in_list_view") or field.get("in_standard_filter") or field.get("in_global_search"))
        ]
        return {
            "title_field": title_field,
            "search_fields": unique(configured_search_fields),
            "filter_fields": unique(field["fieldname"] for field in fields if field.get("in_standard_filter")),
            "list_fields": unique(field["fieldname"] for field in fields if field.get("in_list_view")),
            "autocomplete_fields": unique([title_field] + configured_search_fields + visible_fields),
        }

    def discover_status_metadata(self, workflows, fields):
        workflow_state_fields = unique(
            workflow.get("workflow_state_field") for workflow in workflows if workflow.get("workflow_state_field")
        )
        selectable_fields = [
            {
                "fieldname": field["fieldname"],
                "label": field.get("label"),
                "options": split_csv(field.get("options")),
            }
            for field in fields
            if field.get("fieldtype") == "Select" and field.get("fieldname")
        ]
        return {
            "workflow_state_fields": workflow_state_fields,
            "select_field_candidates": selectable_fields,
        }

    def discover_indexes(self, meta, fields):
        explicit_indexes = read_attr(meta, "indexes", []) or []
        return {
            "explicit": list(explicit_indexes) if not isinstance(explicit_indexes, str) else split_csv(explicit_indexes),
            "field_indexes": [
                {
                    "fieldname": field["fieldname"],
                    "search_index": field.get("search_index"),
                    "unique": field.get("unique"),
                }
                for field in fields
                if field.get("fieldname") and (field.get("search_index") or field.get("unique"))
            ],
        }

    def get_workflow_metadata(self, doctype):
        return [
            {
                "name": read_attr(workflow, "name"),
                "document_type": read_attr(workflow, "document_type"),
                "workflow_state_field": read_attr(workflow, "workflow_state_field"),
                "is_active": read_bool(workflow, "is_active", True),
            }
            for workflow in self.adapter.list_workflows(doctype=doctype)
        ]
