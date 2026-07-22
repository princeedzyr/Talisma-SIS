from dataclasses import dataclass


SYSTEM_FIELD_TYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Image", "Fold", "Heading"}
SYSTEM_FIELDNAMES = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}

SEMANTIC_FIELD_CANDIDATES = {
    "lead_name": ("lead_name", "contact_name", "full_name", "name"),
    "company_name": ("company_name", "organization", "company"),
    "email": ("email_id", "email"),
    "phone": ("mobile_no", "phone", "phone_no"),
    "source": ("source", "lead_source"),
    "territory": ("territory",),
    "status": ("status",),
    "sales_person": ("sales_person", "sales_owner"),
    "owner": ("owner",),
    "city": ("city",),
    "notes": ("notes", "remarks"),
}


@dataclass(frozen=True)
class LeadMetadata:
    raw: dict
    fields: list
    fieldnames: set
    mandatory_fields: list
    select_options: dict
    link_fields: dict
    semantic_fields: dict


class LeadMetadataService:
    def __init__(self, erp_service):
        self.erp_service = erp_service

    def get_metadata(self):
        response = self.erp_service.get_metadata("Lead")
        meta = response.get("result") if isinstance(response, dict) else response
        meta = meta or {}
        fields = normalize_fields(meta)
        fieldnames = {field.get("fieldname") for field in fields if field.get("fieldname")}
        return LeadMetadata(
            raw=meta,
            fields=fields,
            fieldnames=fieldnames,
            mandatory_fields=[field for field in fields if is_required(field)],
            select_options={field["fieldname"]: split_options(field.get("options")) for field in fields if field.get("fieldtype") == "Select"},
            link_fields={field["fieldname"]: field.get("options") for field in fields if field.get("fieldtype") == "Link"},
            semantic_fields=build_semantic_field_map(fieldnames),
        )

    def field_for(self, semantic_name):
        return self.get_metadata().semantic_fields.get(semantic_name)

    def lead_display_fields(self, limit=10):
        metadata = self.get_metadata()
        preferred = [
            metadata.semantic_fields.get("lead_name"),
            metadata.semantic_fields.get("company_name"),
            metadata.semantic_fields.get("status"),
            metadata.semantic_fields.get("source"),
            metadata.semantic_fields.get("territory"),
            metadata.semantic_fields.get("email"),
            metadata.semantic_fields.get("phone"),
            "owner",
            "creation",
            "modified",
        ]
        fields = unique([field for field in preferred if field and (field in metadata.fieldnames or field in SYSTEM_FIELDNAMES)])
        return fields[:limit] or ["name"]


def normalize_fields(meta):
    if isinstance(meta, dict):
        fields = meta.get("fields") or []
    else:
        fields = getattr(meta, "fields", []) or []
    return [field_to_dict(field) for field in fields if field_to_dict(field).get("fieldname")]


def field_to_dict(field):
    if isinstance(field, dict):
        return dict(field)
    data = {}
    for key in ("fieldname", "label", "fieldtype", "options", "default", "reqd", "mandatory", "hidden", "read_only"):
        data[key] = getattr(field, key, None)
    return data


def build_semantic_field_map(fieldnames):
    mapped = {}
    for semantic, candidates in SEMANTIC_FIELD_CANDIDATES.items():
        for candidate in candidates:
            if candidate in fieldnames or candidate in SYSTEM_FIELDNAMES:
                mapped[semantic] = candidate
                break
    return mapped


def split_options(options):
    if not options:
        return []
    if isinstance(options, (list, tuple)):
        return [str(item).strip() for item in options if str(item).strip()]
    values = []
    for line in str(options).replace(",", "\n").splitlines():
        value = line.strip()
        if value:
            values.append(value)
    return values


def is_required(field):
    return bool(field.get("reqd") or field.get("mandatory"))


def is_business_field(field):
    fieldname = field.get("fieldname")
    fieldtype = field.get("fieldtype")
    if not fieldname or fieldname in SYSTEM_FIELDNAMES:
        return False
    if fieldtype in SYSTEM_FIELD_TYPES:
        return False
    if field.get("hidden"):
        return False
    return True


def unique(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
