import re

from wingman_ai.field_filters import is_editable_business_field, is_system_fieldname


LINK_FIELDTYPES = {"Link", "Dynamic Link"}
CHILD_TABLE_FIELDTYPES = {"Table", "Table MultiSelect"}
DATA_FIELDTYPES = {"Data", "Small Text", "Text"}


class UniversalOperationBlueprintBuilder:
    """Builds the immutable metadata view shared by create, update, and future operations."""

    def __init__(self, erp_service=None):
        self.erp_service = erp_service

    def build(self, doctype, metadata=None, operation="create"):
        metadata = metadata or self.get_metadata(doctype)
        fields = [normalize_field(field) for field in metadata.get("fields") or []]
        editable = [field for field in fields if is_editable_business_field(field)]
        hidden = [field for field in fields if truthy(field.get("hidden"))]
        read_only = [field for field in fields if truthy(field.get("read_only"))]
        virtual = [field for field in fields if truthy(field.get("is_virtual"))]
        required = [field for field in editable if is_required(field)]
        conditional_required = [field for field in editable if field.get("mandatory_depends_on")]
        link_fields = [field for field in editable if field.get("fieldtype") in LINK_FIELDTYPES]
        child_tables = [field for field in editable if field.get("fieldtype") in CHILD_TABLE_FIELDTYPES]

        return {
            "operation": operation or "create",
            "doctype": metadata.get("doctype") or doctype,
            "metadata": dict(metadata or {}),
            "fields": {
                "all": fields,
                "editable": editable,
                "hidden": hidden,
                "read_only": read_only,
                "virtual": virtual,
                "required": required,
                "conditional_required": conditional_required,
                "links": link_fields,
                "child_tables": child_tables,
            },
            "field_map": {field.get("fieldname"): field for field in fields if field.get("fieldname")},
            "default_values": {
                field.get("fieldname"): field.get("default")
                for field in editable
                if field.get("fieldname") and field.get("default") not in (None, "")
            },
            "select_options": {
                field.get("fieldname"): split_options(field.get("options"))
                for field in editable
                if field.get("fieldtype") == "Select" and field.get("fieldname")
            },
            "links": [
                {
                    "fieldname": field.get("fieldname"),
                    "label": field_label(field),
                    "target_doctype": field.get("options") if field.get("fieldtype") == "Link" else None,
                    "dynamic_target_field": field.get("options") if field.get("fieldtype") == "Dynamic Link" else None,
                    "required": is_required(field),
                }
                for field in link_fields
            ],
            "child_tables": [
                {
                    "fieldname": field.get("fieldname"),
                    "label": field_label(field),
                    "child_doctype": field.get("options"),
                    "required": is_required(field),
                }
                for field in child_tables
            ],
            "naming": naming_metadata(metadata, fields),
            "primary_field": infer_primary_input_field(metadata.get("doctype") or doctype, fields, metadata),
            "workflow_rules": metadata.get("workflows") or metadata.get("workflow") or [],
            "permission_rules": metadata.get("permissions") or [],
            "property_setters": metadata.get("property_setters") or [],
            "custom_fields": metadata.get("custom_fields") or [field for field in fields if truthy(field.get("custom"))],
            "installed_app_metadata": metadata.get("installed_app_metadata") or {},
            "validation_metadata": validation_metadata(metadata, fields),
            "related_documents": metadata.get("related_documents") or metadata.get("relationships") or [],
            "post_creation_recommendations": metadata.get("post_creation_recommendations") or [],
        }

    def get_metadata(self, doctype):
        if not self.erp_service or not hasattr(self.erp_service, "get_metadata"):
            return {"doctype": doctype, "fields": []}
        response = self.erp_service.get_metadata(doctype)
        if isinstance(response, dict):
            return response.get("result") or {}
        return response or {}


class CreationBlueprintBuilder(UniversalOperationBlueprintBuilder):
    """Compatibility wrapper for existing create callers."""

    def build(self, doctype, metadata=None):
        return super().build(doctype, metadata=metadata, operation="create")


class UpdateBlueprintBuilder(UniversalOperationBlueprintBuilder):
    """Compatibility wrapper for update callers."""

    def build(self, doctype, metadata=None):
        return super().build(doctype, metadata=metadata, operation="update")


def normalize_field(field):
    field = dict(field or {})
    if "mandatory" not in field:
        field["mandatory"] = truthy(field.get("reqd"))
    if "reqd" not in field:
        field["reqd"] = 1 if truthy(field.get("mandatory")) else 0
    return field


def validation_metadata(metadata, fields):
    return {
        "depends_on": {field.get("fieldname"): field.get("depends_on") for field in fields if field.get("fieldname") and field.get("depends_on")},
        "mandatory_depends_on": {
            field.get("fieldname"): field.get("mandatory_depends_on")
            for field in fields
            if field.get("fieldname") and field.get("mandatory_depends_on")
        },
        "read_only_depends_on": {
            field.get("fieldname"): field.get("read_only_depends_on")
            for field in fields
            if field.get("fieldname") and field.get("read_only_depends_on")
        },
        "server_validation": metadata.get("server_validation") or [],
    }


def naming_metadata(metadata, fields):
    naming = dict(metadata.get("naming") or {})
    autoname = metadata.get("autoname") or naming.get("autoname")
    naming.setdefault("autoname", autoname)
    naming.setdefault("title_field", metadata.get("title_field"))
    naming.setdefault("naming_rule", metadata.get("naming_rule"))
    if autoname and ":" in str(autoname):
        rule, fieldname = str(autoname).split(":", 1)
        naming.setdefault("rule", rule)
        naming.setdefault("series_field", fieldname)
        field = next((item for item in fields if item.get("fieldname") == fieldname), None)
        naming.setdefault("series_options", split_options((field or {}).get("options")))
    return naming


def infer_primary_input_field(doctype, fields, metadata=None):
    metadata = metadata or {}
    field_map = {field.get("fieldname"): field for field in fields or [] if field.get("fieldname")}

    for fieldname in naming_field_candidates(metadata):
        field = field_map.get(fieldname)
        if field and accepts_free_text_name(field):
            return field

    title_field = metadata.get("title_field")
    if title_field and accepts_free_text_name(field_map.get(title_field)):
        return field_map[title_field]

    normalized = scrub(doctype)
    preferred_names = {f"{normalized}_name", "title", "subject"}
    for field in fields or []:
        fieldname = field.get("fieldname")
        if fieldname in preferred_names and accepts_free_text_name(field):
            return field

    for field in fields or []:
        fieldname = str(field.get("fieldname") or "")
        if fieldname.endswith("_name") and accepts_free_text_name(field):
            return field

    required_text = [field for field in fields or [] if is_required(field) and accepts_free_text_name(field)]
    required_text = [field for field in required_text if not looks_like_contact_method(field)]
    if required_text:
        return required_text[0]

    return None


def naming_field_candidates(metadata):
    candidates = []
    autoname = str(metadata.get("autoname") or "")
    if autoname.startswith("field:"):
        candidates.append(autoname.split(":", 1)[1])
    naming = metadata.get("naming") or {}
    if naming.get("series_field"):
        candidates.append(naming.get("series_field"))
    return [item for item in candidates if item]


def accepts_free_text_name(field):
    if not field or not is_editable_business_field(field):
        return False
    if is_system_fieldname(field.get("fieldname")):
        return False
    return field.get("fieldtype") in DATA_FIELDTYPES


def looks_like_contact_method(field):
    text = normalize(f"{field.get('fieldname')} {field.get('label')}")
    return any(token in text for token in ("email", "phone", "mobile", "fax"))


def is_required(field):
    return truthy((field or {}).get("reqd")) or truthy((field or {}).get("mandatory"))


def split_options(options):
    if not options:
        return []
    if isinstance(options, (list, tuple)):
        return [str(item).strip() for item in options if str(item).strip()]
    return [line.strip() for line in str(options).replace(",", "\n").splitlines() if line.strip()]


def field_label(field):
    return (field or {}).get("label") or str((field or {}).get("fieldname") or "Field").replace("_", " ").title()


def truthy(value):
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "none", "null")
    return bool(value)


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


def scrub(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
