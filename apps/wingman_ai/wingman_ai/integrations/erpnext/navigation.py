DOCUMENT_SEARCH_FIELDS = {
    "Student": ["name", "student_name", "first_name", "middle_name", "last_name", "student_email_id", "student_mobile_number", "talisma_student_number", "talisma_preferred_name"],
    "Student Applicant": ["name", "student_name", "first_name", "middle_name", "last_name", "student_email_id", "student_mobile_number", "program"],
    "Guardian": ["name", "guardian_name", "email_address", "mobile_number"],
    "Instructor": ["name", "instructor_name", "employee"],
    "Program Enrollment": ["name", "student", "student_name", "program", "academic_year", "academic_term"],
    "Course Enrollment": ["name", "student", "student_name", "program", "course"],
    "Student Attendance": ["name", "student", "student_name", "course_schedule", "date", "status"],
    "Assessment Result": ["name", "student", "student_name", "course", "assessment_plan", "grade"],
    "Fees": ["name", "student", "student_name", "program", "academic_year", "academic_term"],
    "User": ["name", "email", "username", "first_name", "last_name", "full_name"],
    "Customer": ["name", "customer_name", "customer_group", "territory"],
    "Supplier": ["name", "supplier_name", "supplier_group"],
    "Lead": ["name", "lead_name", "company_name", "email_id", "mobile_no"],
    "Opportunity": ["name", "title", "party_name", "customer_name"],
    "Sales Order": ["name", "customer", "customer_name", "title"],
    "Sales Invoice": ["name", "customer", "customer_name", "title"],
    "Quotation": ["name", "quotation_to", "party_name", "customer_name", "title"],
    "Delivery Note": ["name", "customer", "customer_name", "title"],
    "Purchase Order": ["name", "supplier", "supplier_name", "title"],
    "Purchase Invoice": ["name", "supplier", "supplier_name", "title"],
    "Material Request": ["name", "title", "material_request_type"],
    "Item": ["name", "item_code", "item_name", "item_group"],
    "Warehouse": ["name", "warehouse_name"],
    "Employee": ["name", "employee_name", "first_name", "last_name", "user_id"],
    "Project": ["name", "project_name", "customer"],
    "Task": ["name", "subject", "project"],
    "Issue": ["name", "subject", "customer"],
    "Workflow": ["name", "workflow_name", "document_type"],
}

FUZZY_DOCUMENT_THRESHOLD = 0.78
FUZZY_ROUTE_THRESHOLD = 0.86


def find_workspace_by_query(query, alias_candidates, normalize, allow_fallback=False):
    available = get_available_workspaces()
    if available:
        normalized = {normalize(item): item for item in available}
        for candidate in alias_candidates:
            match = normalized.get(normalize(candidate))
            if match:
                return match

    return alias_candidates[0] if allow_fallback and alias_candidates else None


def find_doctype_by_query(query, normalize):
    available = get_available_doctypes()
    if not available:
        return None

    normalized = {normalize(item): item for item in available}
    return normalized.get(query)


def find_report_by_query(query, normalize):
    return find_route_record(query, get_available_reports(), normalize)


def find_page_by_query(query, normalize):
    return find_route_record(query, get_available_pages(), normalize)


def find_route_record(query, records, normalize):
    if not records:
        return None

    normalized_query = normalize(query)
    for record in records:
        for value in record.get("match_values") or []:
            if normalize(value) == normalized_query:
                return record

    best = None
    for record in records:
        for value in record.get("match_values") or []:
            score = similarity(normalized_query, normalize(value))
            if score >= FUZZY_ROUTE_THRESHOLD and (not best or score > best[0]):
                best = (score, record)

    return best[1] if best else None


def find_document(doctype, document_query, normalize):
    matches = find_documents(doctype, document_query, normalize)
    return matches[0] if matches else None


def find_documents(doctype, document_query, normalize, limit=5):
    cleaned_query = clean_document_query(document_query)
    if not cleaned_query:
        return []

    try:
        import frappe
    except Exception:
        return [{"name": cleaned_query, "display": cleaned_query}]

    exact = find_exact_document(frappe, doctype, cleaned_query)
    if exact:
        return [exact]

    return find_matching_documents(frappe, doctype, cleaned_query, normalize, limit=limit)


def find_exact_document(frappe, doctype, document_query):
    try:
        rows = frappe.get_list(
            doctype,
            filters={"name": document_query},
            fields=["name"],
            limit_page_length=1,
        )
    except Exception:
        return None

    if not rows:
        return None

    name = rows[0].get("name")
    return {"name": name, "display": name}


def find_matching_document(frappe, doctype, document_query, normalize):
    matches = find_matching_documents(frappe, doctype, document_query, normalize, limit=1)
    return matches[0] if matches else None


def find_matching_documents(frappe, doctype, document_query, normalize, limit=5):
    search_fields = get_document_search_fields(frappe, doctype)
    if not search_fields:
        return []

    like_value = make_like_value(document_query, normalize)
    or_filters = [[doctype, field, "like", like_value] for field in search_fields]
    fields = unique_list(["name"] + get_display_fields(frappe, doctype))

    try:
        rows = frappe.get_list(
            doctype,
            fields=fields,
            or_filters=or_filters,
            limit_page_length=limit,
        )
    except Exception:
        return []

    if rows:
        return [make_document_match(row, doctype) for row in rows]

    fuzzy_match = find_fuzzy_document(frappe, doctype, document_query, fields, normalize)
    return [fuzzy_match] if fuzzy_match else []


def find_fuzzy_document(frappe, doctype, document_query, fields, normalize):
    try:
        rows = frappe.get_list(
            doctype,
            fields=fields,
            limit_page_length=100,
        )
    except Exception:
        return None

    query_norm = normalize(document_query)
    best = None
    for row in rows:
        values = [row.get("name"), get_display_value(row, doctype)]
        values.extend(row.get(field) for field in fields if field != "name")
        for value in values:
            if not value:
                continue
            score = similarity(query_norm, normalize(str(value)))
            if score >= FUZZY_DOCUMENT_THRESHOLD and (not best or score > best[0]):
                best = (score, row)

    if not best:
        return None

    return make_document_match(best[1], doctype)


def make_document_match(row, doctype):
    return {
        "name": row.get("name"),
        "display": get_display_value(row, doctype),
    }


def get_document_search_fields(frappe, doctype):
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return ["name"]

    candidates = unique_list(
        ["name"]
        + DOCUMENT_SEARCH_FIELDS.get(doctype, [])
        + [
            "title",
            "subject",
            "full_name",
            "first_name",
            "last_name",
            "username",
            "email",
            "customer_name",
            "supplier_name",
            "employee_name",
            "item_name",
            "company_name",
        ]
    )

    return [field for field in candidates if field == "name" or meta.has_field(field)]


def get_display_fields(frappe, doctype):
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return []

    fields = []
    for field in DOCUMENT_SEARCH_FIELDS.get(doctype, []):
        if field != "name" and meta.has_field(field):
            fields.append(field)

    for field in ("title", "full_name", "customer_name", "supplier_name", "employee_name", "item_name"):
        if meta.has_field(field):
            fields.append(field)

    return fields[:8]


def get_display_value(row, doctype):
    for field in get_display_priority(doctype):
        value = row.get(field)
        if value:
            return value

    return row.get("name")


def get_display_priority(doctype):
    readable_fields = [field for field in DOCUMENT_SEARCH_FIELDS.get(doctype, []) if field != "name"]
    return readable_fields + [
        "title",
        "full_name",
        "customer_name",
        "supplier_name",
        "employee_name",
        "item_name",
        "name",
    ]


def make_like_value(document_query, normalize):
    tokens = normalize(document_query).split()
    if not tokens:
        return f"%{document_query}%"

    return "%" + "%".join(tokens) + "%"


def clean_document_query(value):
    import re

    return re.sub(r"\s+", " ", (value or "").strip().strip(".,;:()[]{}\"'")).strip()


def get_available_workspaces():
    def load():
        import frappe

        rows = frappe.get_list("Workspace", fields=["name", "title"], limit_page_length=500)
        workspaces = []
        for row in rows:
            name = row.get("title") or row.get("name")
            if name:
                workspaces.append(name)
        return workspaces

    return get_user_cached_value("wingman_ai:workspaces", load)


def get_available_doctypes():
    def load():
        import frappe

        rows = frappe.get_list("DocType", fields=["name"], limit_page_length=1000)
        return [row.get("name") for row in rows if row.get("name")]

    return get_user_cached_value("wingman_ai:doctypes", load)


def get_available_reports():
    def load():
        import frappe

        rows = safe_get_list(
            frappe,
            "Report",
            fields=["name", "report_name", "ref_doctype", "report_type"],
            limit_page_length=1000,
        )
        reports = []
        for row in rows:
            name = row.get("name") or row.get("report_name")
            if not name:
                continue
            label = row.get("report_name") or name
            reports.append(
                {
                    "name": name,
                    "label": label,
                    "route": ["query-report", name],
                    "kind": "report",
                    "match_values": unique_list([name, label, f"{label} report", f"{name} report"]),
                    "ref_doctype": row.get("ref_doctype"),
                    "report_type": row.get("report_type"),
                }
            )
        return reports

    return get_user_cached_value("wingman_ai:reports", load)


def get_available_pages():
    def load():
        import frappe

        rows = safe_get_list(
            frappe,
            "Page",
            fields=["name", "title"],
            limit_page_length=1000,
        )
        pages = []
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            label = row.get("title") or name
            pages.append(
                {
                    "name": name,
                    "label": label,
                    "route": ["page", name],
                    "kind": "desk_page",
                    "match_values": unique_list([name, label, f"{label} page", f"{name} page"]),
                }
            )
        return pages

    return get_user_cached_value("wingman_ai:pages", load)


def safe_get_list(frappe, doctype, fields=None, **kwargs):
    try:
        return frappe.get_list(doctype, fields=fields or ["name"], **kwargs)
    except Exception:
        try:
            return frappe.get_list(doctype, fields=["name"], **kwargs)
        except Exception:
            return []


def get_user_cached_value(prefix, loader):
    try:
        import frappe
    except Exception:
        return []

    user = getattr(getattr(frappe, "session", None), "user", None) or "Guest"
    key = f"{prefix}:{user}"

    try:
        cache = frappe.cache()
        cached = cache.get_value(key)
        if cached is not None:
            return cached

        value = loader()
        cache.set_value(key, value, expires_in_sec=300)
        return value
    except Exception:
        try:
            return loader()
        except Exception:
            return []


def unique_list(values):
    seen = set()
    unique = []
    for value in values:
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def similarity(left, right):
    from difflib import SequenceMatcher

    return SequenceMatcher(None, left or "", right or "").ratio()
