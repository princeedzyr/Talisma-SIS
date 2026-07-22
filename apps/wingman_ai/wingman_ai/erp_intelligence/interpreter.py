from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.models import split_csv, unique


LAYOUT_FIELD_TYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "Fold",
    "HTML",
    "Heading",
    "Button",
}
RELATIONSHIP_PREVIEW_LIMIT = 8
FIELD_PREVIEW_LIMIT = 8
CHILD_TABLE_PREVIEW_LIMIT = 6


class BusinessMetadataInterpreter:
    def __init__(self, intelligence_service=None, config=None):
        self.intelligence_service = intelligence_service
        self.config = config or get_erp_intelligence_config()

    def describe_doctype(self, doctype, user=None):
        service = self.get_service()
        metadata = service.get_doctype_metadata(doctype)
        relationships = service.get_relationships(doctype)
        workflow = service.get_workflow(doctype, user=user)
        search = service.get_search_metadata(doctype)

        summary = {
            "doctype": doctype,
            "module": metadata.get("module"),
            "is_custom": metadata.get("custom"),
            "is_submittable": metadata.get("is_submittable"),
            "overview": self.build_overview(metadata, relationships),
            "key_fields": self.pick_key_fields(metadata),
            "required_fields": self.pick_required_fields(metadata),
            "child_tables": self.pick_child_tables(metadata),
            "relationships": self.summarize_relationships(relationships),
            "workflow": self.summarize_workflow(workflow),
            "search": self.summarize_search(search),
        }
        summary["message"] = format_business_summary(summary)
        return summary

    def get_service(self):
        if self.intelligence_service:
            return self.intelligence_service

        from wingman_ai.erp_intelligence.service import get_erp_intelligence_service

        return get_erp_intelligence_service()

    def build_overview(self, metadata, relationships):
        doctype = metadata.get("doctype")
        module = metadata.get("module") or "Talisma OneCampus"
        descriptor = "custom DocType" if metadata.get("custom") else "DocType"
        document_type = "submittable document" if metadata.get("is_submittable") else "record type"
        field_count = len(metadata.get("fields") or [])
        child_count = len(metadata.get("child_tables") or [])
        related_count = len((relationships or {}).get("incoming") or []) + len((relationships or {}).get("outgoing") or [])

        return (
            f"{doctype} is a {descriptor} in the {module} module. "
            f"It behaves as a {document_type} with {field_count} discovered fields, "
            f"{child_count} child tables, and {related_count} metadata relationships."
        )

    def pick_key_fields(self, metadata):
        fields = [field for field in metadata.get("fields") or [] if is_business_field(field)]
        search = metadata.get("search") or {}
        title_field = metadata.get("title_field")
        search_fields = set(search.get("search_fields") or [])
        filter_fields = set(search.get("filter_fields") or [])
        list_fields = set(search.get("list_fields") or [])
        scored = []

        for field in fields:
            score = score_field(field, title_field, search_fields, filter_fields, list_fields)
            scored.append((score, field))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [serialize_business_field(field) for score, field in scored[:FIELD_PREVIEW_LIMIT]]

    def pick_required_fields(self, metadata):
        required = []
        for field in metadata.get("mandatory_fields") or []:
            if not is_business_field(field):
                continue
            required.append(serialize_business_field(field))
        return required[:FIELD_PREVIEW_LIMIT]

    def pick_child_tables(self, metadata):
        child_tables = []
        for field in metadata.get("child_tables") or []:
            child_tables.append(
                {
                    "fieldname": field.get("fieldname"),
                    "label": field.get("label") or humanize(field.get("fieldname")),
                    "child_doctype": field.get("child_doctype") or field.get("options"),
                    "mandatory": bool(field.get("mandatory")),
                }
            )
        return child_tables[:CHILD_TABLE_PREVIEW_LIMIT]

    def summarize_relationships(self, relationships):
        outgoing = []
        incoming = []
        dynamic_candidates = []

        for item in (relationships or {}).get("outgoing") or []:
            if item.get("relationship_type") == "Link" and item.get("target_doctype"):
                outgoing.append(
                    {
                        "label": humanize(item.get("source_field")),
                        "fieldname": item.get("source_field"),
                        "target_doctype": item.get("target_doctype"),
                        "mandatory": bool(item.get("mandatory")),
                    }
                )

        for item in (relationships or {}).get("incoming") or []:
            if item.get("relationship_type") == "Link":
                incoming.append(
                    {
                        "source_doctype": item.get("source_doctype"),
                        "source_field": item.get("source_field"),
                        "label": f"{item.get('source_doctype')} via {humanize(item.get('source_field'))}",
                        "mandatory": bool(item.get("mandatory")),
                    }
                )
            elif item.get("relationship_type") == "Dynamic Link Candidate":
                dynamic_candidates.append(
                    {
                        "source_doctype": item.get("source_doctype"),
                        "source_field": item.get("source_field"),
                        "dynamic_target_field": item.get("dynamic_target_field"),
                    }
                )

        return {
            "outgoing_links": outgoing[:RELATIONSHIP_PREVIEW_LIMIT],
            "incoming_links": incoming[:RELATIONSHIP_PREVIEW_LIMIT],
            "dynamic_candidate_count": len(dynamic_candidates),
            "dynamic_candidates_preview": dynamic_candidates[:3],
        }

    def summarize_workflow(self, workflow):
        workflows = (workflow or {}).get("workflows") or []
        if not workflows:
            return {"enabled": False, "message": "No active workflow metadata was discovered."}

        active = workflows[0]
        return {
            "enabled": True,
            "name": active.get("name"),
            "state_field": active.get("workflow_state_field"),
            "state_count": len(active.get("states") or []),
            "action_count": len(active.get("transitions") or []),
            "allowed_actions": [item.get("action") for item in active.get("allowed_actions") or [] if item.get("action")],
        }

    def summarize_search(self, search):
        return {
            "title_field": (search or {}).get("title_field"),
            "search_fields": (search or {}).get("search_fields") or [],
            "filter_fields": (search or {}).get("filter_fields") or [],
            "autocomplete_fields": (search or {}).get("autocomplete_fields") or [],
        }


def is_business_field(field):
    if not field.get("fieldname"):
        return False
    if field.get("fieldtype") in LAYOUT_FIELD_TYPES:
        return False
    if field.get("hidden") and not field.get("in_standard_filter"):
        return False
    return True


def score_field(field, title_field, search_fields, filter_fields, list_fields):
    fieldname = field.get("fieldname")
    score = 0
    if fieldname == title_field:
        score += 60
    if field.get("mandatory"):
        score += 45
    if fieldname in list_fields:
        score += 30
    if fieldname in search_fields:
        score += 25
    if fieldname in filter_fields:
        score += 20
    if field.get("fieldtype") == "Link":
        score += 18
    if field.get("fieldtype") == "Select":
        score += 14
    if field.get("read_only"):
        score -= 5
    if field.get("hidden"):
        score -= 15
    return score


def serialize_business_field(field):
    return {
        "fieldname": field.get("fieldname"),
        "label": field.get("label") or humanize(field.get("fieldname")),
        "fieldtype": field.get("fieldtype"),
        "mandatory": bool(field.get("mandatory")),
        "conditional_mandatory": bool(field.get("mandatory_depends_on")) and not bool(field.get("mandatory")),
        "read_only": bool(field.get("read_only")),
        "target_doctype": field.get("target_doctype"),
        "options": split_csv(field.get("options")) if field.get("fieldtype") == "Select" else None,
    }


def format_business_summary(summary):
    lines = [
        f"{summary.get('doctype')} Intelligence",
        "",
        "Overview",
        summary.get("overview"),
        "",
        "Key Fields",
    ]

    lines.extend(format_field_lines(summary.get("key_fields") or []))
    add_section(lines, "Required Inputs", format_field_lines(summary.get("required_fields") or []))
    add_section(lines, "Child Tables", format_child_table_lines(summary.get("child_tables") or []))
    add_section(lines, "Related Records", format_relationship_lines(summary.get("relationships") or {}))
    add_section(lines, "Workflow", format_workflow_lines(summary.get("workflow") or {}))

    lines.extend(
        [
            "",
            "How Wingman Uses This",
            "- Understands the record structure without hardcoded assumptions.",
            "- Chooses better fields for summaries, search, and guided actions.",
            "- Keeps future actions aligned with Talisma OneCampus metadata and permissions.",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def add_section(lines, title, section_lines):
    if not section_lines:
        return
    lines.extend(["", title, *section_lines])


def format_field_lines(fields):
    if not fields:
        return ["- No business fields were identified from metadata."]
    lines = []
    for field in fields:
        detail = field.get("fieldtype") or "Field"
        if field.get("target_doctype"):
            detail = f"{detail} to {field.get('target_doctype')}"
        flags = []
        if field.get("mandatory"):
            flags.append("required")
        if field.get("conditional_mandatory"):
            flags.append("conditionally required")
        if field.get("read_only"):
            flags.append("read-only")
        suffix = f" ({detail}; {', '.join(flags)})" if flags else f" ({detail})"
        lines.append(f"- {field.get('label')}{suffix}")
    return lines


def format_child_table_lines(child_tables):
    return [
        f"- {item.get('label')} -> {item.get('child_doctype')}"
        for item in child_tables
        if item.get("child_doctype")
    ]


def format_relationship_lines(relationships):
    lines = []
    for item in relationships.get("incoming_links") or []:
        lines.append(f"- {item.get('label')}")
    for item in relationships.get("outgoing_links") or []:
        lines.append(f"- {item.get('label')} links to {item.get('target_doctype')}")
    dynamic_count = relationships.get("dynamic_candidate_count") or 0
    if dynamic_count:
        lines.append(f"- {dynamic_count} dynamic link candidates can be resolved when a specific record is known.")
    return unique(lines)[:RELATIONSHIP_PREVIEW_LIMIT]


def format_workflow_lines(workflow):
    if not workflow.get("enabled"):
        return [f"- {workflow.get('message') or 'No active workflow metadata was discovered.'}"]

    lines = [
        f"- Workflow: {workflow.get('name')}",
        f"- State field: {workflow.get('state_field')}",
        f"- States: {workflow.get('state_count')}; transitions: {workflow.get('action_count')}",
    ]
    actions = workflow.get("allowed_actions") or []
    if actions:
        lines.append(f"- Current allowed actions: {', '.join(actions)}")
    return lines


def humanize(value):
    return " ".join(str(value or "").replace("_", " ").split()).title()
