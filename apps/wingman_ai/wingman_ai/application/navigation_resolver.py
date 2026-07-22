import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from wingman_ai.integrations.erpnext.navigation import (
    find_doctype_by_query,
    find_document,
    find_documents,
    find_page_by_query,
    find_report_by_query,
    find_workspace_by_query,
)


COMMAND_PATTERNS = (
    r"\bplease\b",
    r"\bopen\b",
    r"\bgo\s+to\b",
    r"\bgoto\b",
    r"\bnavigate\s+to\b",
    r"\bnavigate\b",
    r"\bnavigae\s+to\b",
    r"\bnavigae\b",
    r"\bnaviagte\s+to\b",
    r"\bnaviagte\b",
    r"\bnavgate\s+to\b",
    r"\bnavgate\b",
    r"\bnaviate\s+to\b",
    r"\bnaviate\b",
    r"\btake\s+me\s+to\b",
    r"\bmove\s+to\b",
    r"\bredirect\s+to\b",
    r"\bshow\s+me\b",
    r"\bshow\b",
    r"\bthe\b",
    r"\bpage\b",
    r"\bworkspace\b",
    r"\bmodule\b",
    r"\breport\b",
)


WORKSPACE_ALIASES = {
    "accounts": ["Accounting"],
    "accounting": ["Accounting"],
    "asset": ["Assets"],
    "assets": ["Assets"],
    "buy": ["Buying"],
    "buying": ["Buying"],
    "crm": ["CRM", "Selling"],
    "erpnext setting": ["Talisma OneCampus Settings"],
    "erpnext settings": ["Talisma OneCampus Settings"],
    "framework": ["Framework"],
    "manufacturing": ["Manufacturing"],
    "organization": ["Organization"],
    "project": ["Projects"],
    "projects": ["Projects"],
    "purchase": ["Buying"],
    "quality": ["Quality"],
    "sales": ["Selling"],
    "selling": ["Selling"],
    "sis": ["Education"],
    "student information system": ["Education"],
    "academics": ["Education"],
    "stock": ["Stock"],
    "subcontracting": ["Subcontracting"],
}


DOCTYPE_ALIASES = {
    "address": "Address",
    "addresses": "Address",
    "bom": "BOM",
    "campaign": "Campaign",
    "campaigns": "Campaign",
    "contact": "Contact",
    "contacts": "Contact",
    "customer": "Customer",
    "customer group": "Customer Group",
    "customer groups": "Customer Group",
    "customergroup": "Customer Group",
    "customers": "Customer",
    "delivery note": "Delivery Note",
    "delivery notes": "Delivery Note",
    "deliverynote": "Delivery Note",
    "employee": "Employee",
    "employees": "Employee",
    "student": "Student",
    "students": "Student",
    "student applicant": "Student Applicant",
    "student applicants": "Student Applicant",
    "student application": "Student Applicant",
    "student applications": "Student Applicant",
    "guardian": "Guardian",
    "guardians": "Guardian",
    "academic program": "Program",
    "academic programs": "Program",
    "program enrollment": "Program Enrollment",
    "student enrollment": "Program Enrollment",
    "enrollments": "Program Enrollment",
    "course": "Course",
    "courses": "Course",
    "course enrollment": "Course Enrollment",
    "course enrollments": "Course Enrollment",
    "student group": "Student Group",
    "student groups": "Student Group",
    "attendance": "Student Attendance",
    "student attendance": "Student Attendance",
    "assessment": "Assessment Plan",
    "assessments": "Assessment Plan",
    "assessment result": "Assessment Result",
    "assessment results": "Assessment Result",
    "results": "Assessment Result",
    "assessment gradebook": "Assessment Gradebook",
    "assessment gradebooks": "Assessment Gradebook",
    "fee plan": "Fee Structure",
    "fee plans": "Fee Structure",
    "student fee": "Fees",
    "student fees": "Fees",
    "fee structure": "Fee Structure",
    "fee structures": "Fee Structure",
    "academic year": "Academic Year",
    "academic years": "Academic Year",
    "academic term": "Academic Term",
    "academic terms": "Academic Term",
    "degree": "Degree",
    "degrees": "Degree",
    "item": "Item",
    "items": "Item",
    "issue": "Issue",
    "issues": "Issue",
    "lead": "Lead",
    "lead source": "Lead Source",
    "lead sources": "Lead Source",
    "leadsource": "Lead Source",
    "leads": "Lead",
    "material request": "Material Request",
    "material requests": "Material Request",
    "opportunity": "Opportunity",
    "opportunities": "Opportunity",
    "project": "Project",
    "projects": "Project",
    "purchase invoice": "Purchase Invoice",
    "purchase invoices": "Purchase Invoice",
    "purchaseinvoice": "Purchase Invoice",
    "purchase order": "Purchase Order",
    "purchase orders": "Purchase Order",
    "purchaseorder": "Purchase Order",
    "quotation": "Quotation",
    "quotations": "Quotation",
    "sales invoice": "Sales Invoice",
    "sales invoices": "Sales Invoice",
    "salesinvoice": "Sales Invoice",
    "sales order": "Sales Order",
    "sales orders": "Sales Order",
    "salesorder": "Sales Order",
    "sales person": "Sales Person",
    "sales persons": "Sales Person",
    "salesperson": "Sales Person",
    "salespeople": "Sales Person",
    "supplier": "Supplier",
    "suppliers": "Supplier",
    "task": "Task",
    "tasks": "Task",
    "territory": "Territory",
    "territories": "Territory",
    "user": "User",
    "users": "User",
    "warehouse": "Warehouse",
    "warehouses": "Warehouse",
    "workflow": "Workflow",
    "workflows": "Workflow",
}


PAGE_ALIASES = {
    "desk": ["desk"],
    "desktop": ["desk"],
}


BARE_RECORD_DOCTYPE_PRIORITY = (
    "Student",
    "Student Applicant",
    "Guardian",
    "Instructor",
    "Program Enrollment",
    "Course Enrollment",
    "Student Attendance",
    "Assessment Result",
    "Fees",
    "Customer",
    "Lead",
    "Opportunity",
    "Contact",
    "Address",
    "Territory",
    "Lead Source",
    "Campaign",
    "Customer Group",
    "Sales Person",
    "User",
    "Supplier",
    "Sales Order",
    "Quotation",
    "Sales Invoice",
    "Delivery Note",
    "Employee",
    "Item",
    "Project",
    "Task",
    "Issue",
)


@dataclass(frozen=True)
class NavigationTarget:
    label: str
    kind: str
    route: list
    fallback_routes: list = field(default_factory=list)
    query: str = ""
    doctype: str = ""
    docname: str = ""
    document_query: str = ""
    resolved: bool = True
    options: list = field(default_factory=list)

    def to_dict(self):
        return {
            "label": self.label,
            "kind": self.kind,
            "route": self.route,
            "fallback_routes": self.fallback_routes,
            "query": self.query,
            "doctype": self.doctype,
            "docname": self.docname,
            "document_query": self.document_query,
            "resolved": self.resolved,
            "options": self.options,
        }


def normalize_text(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())).strip()


def titleize(value):
    return " ".join(part.capitalize() for part in normalize_text(value).split())


def extract_navigation_query(message):
    query = normalize_text(message)
    for pattern in COMMAND_PATTERNS:
        query = re.sub(pattern, " ", query)

    query = re.sub(r"\blist\s+of\b", " ", query)
    query = re.sub(r"\blist\b", " ", query)
    return normalize_text(query)


def extract_navigation_query_raw(message):
    query = (message or "").strip()
    for pattern in COMMAND_PATTERNS:
        query = re.sub(pattern, " ", query, flags=re.IGNORECASE)

    query = re.sub(r"\blist\s+of\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\blist\b", " ", query, flags=re.IGNORECASE)
    return clean_document_query(query)


def resolve_navigation_target(message, context=None):
    query = extract_navigation_query(message)
    raw_query = extract_navigation_query_raw(message)
    if not query:
        return NavigationTarget(label="Desk", kind="page", route=["desk"], query=query)

    page_route = PAGE_ALIASES.get(query)
    if page_route:
        return NavigationTarget(label=titleize(query), kind="page", route=page_route, query=query)

    workspace = find_workspace(query)
    if workspace:
        return make_workspace_target(workspace, query)

    doctype = find_doctype(query)
    if doctype:
        return NavigationTarget(label=doctype, kind="doctype_list", route=["List", doctype], query=query)

    candidates = WORKSPACE_ALIASES.get(query)
    if candidates:
        return make_workspace_target(candidates[0], query, candidates[1:])

    doctype = DOCTYPE_ALIASES.get(query)
    if doctype:
        return NavigationTarget(label=doctype, kind="doctype_list", route=["List", doctype], query=query)

    report_target = resolve_report_navigation(query)
    if report_target:
        return report_target

    desk_page_target = resolve_desk_page_navigation(query)
    if desk_page_target:
        return desk_page_target

    document_target = resolve_document_navigation(raw_query, query)
    if document_target:
        return document_target

    fuzzy_workspace = find_fuzzy_workspace_alias(query)
    if fuzzy_workspace:
        return make_workspace_target(fuzzy_workspace, query)

    fuzzy_doctype = find_fuzzy_doctype_alias(query)
    if fuzzy_doctype:
        return NavigationTarget(label=fuzzy_doctype, kind="doctype_list", route=["List", fuzzy_doctype], query=query)

    bare_record_target = resolve_bare_record_navigation(raw_query, query, context=context)
    if bare_record_target:
        return bare_record_target

    label = titleize(query)
    return NavigationTarget(
        label=label,
        kind="navigation_not_found",
        route=[],
        query=query,
        resolved=False,
    )


def resolve_report_navigation(query):
    report = find_report_by_query(query, normalize_text)
    if not report:
        return None
    return NavigationTarget(
        label=report.get("label") or report.get("name"),
        kind="report",
        route=report.get("route") or ["query-report", report.get("name")],
        fallback_routes=[],
        query=query,
    )


def resolve_desk_page_navigation(query):
    page = find_page_by_query(query, normalize_text)
    if not page:
        return None
    return NavigationTarget(
        label=page.get("label") or page.get("name"),
        kind="desk_page",
        route=page.get("route") or ["page", page.get("name")],
        fallback_routes=[],
        query=query,
    )


def resolve_document_navigation(raw_query, normalized_query):
    document_request = split_doctype_and_document(raw_query, normalized_query)
    if not document_request:
        return None

    doctype, document_query = document_request
    if not document_query:
        return NavigationTarget(
            label=doctype,
            kind="doctype_list",
            route=["List", doctype],
            query=normalized_query,
            doctype=doctype,
        )

    match = find_document(doctype, document_query, normalize_text)
    if match:
        docname = match.get("name")
        display = match.get("display") or docname
        return NavigationTarget(
            label=f"{doctype} {display}",
            kind="document",
            route=["Form", doctype, docname],
            query=normalized_query,
            doctype=doctype,
            docname=docname,
            document_query=document_query,
        )

    alternate_matches = find_alternate_documents(document_query, normalize_text, exclude_doctype=doctype)
    if alternate_matches:
        return NavigationTarget(
            label=f"{doctype} {document_query}",
            kind="document_type_mismatch",
            route=[],
            query=normalized_query,
            doctype=doctype,
            document_query=document_query,
            resolved=False,
            options=make_document_options(document_query, normalized_query, alternate_matches),
        )

    return NavigationTarget(
        label=f"{doctype} list",
        kind="document_not_found",
        route=["List", doctype],
        query=normalized_query,
        doctype=doctype,
        document_query=document_query,
        resolved=False,
    )


def resolve_bare_record_navigation(raw_query, normalized_query, context=None):
    if not should_search_bare_record(normalized_query):
        return None

    # A person name in OneCampus represents the parent Student record. Related
    # enrollment, course, assessment, contact, and finance records remain
    # accessible from Student 360 and must not compete as navigation targets.
    student_matches = find_documents("Student", raw_query, normalize_text, limit=2)
    if len(student_matches) == 1:
        match = student_matches[0]
        docname = match.get("name")
        display = match.get("display") or docname
        if docname:
            return NavigationTarget(
                label=f"Student {display}",
                kind="document",
                route=["Form", "Student", docname],
                query=normalized_query,
                doctype="Student",
                docname=docname,
                document_query=clean_document_query(raw_query),
            )

    context_object = ((context or {}).get("object") or {}) if isinstance(context, dict) else {}
    current_doctype = context_object.get("doctype")
    if current_doctype:
        contextual_matches = find_documents(current_doctype, raw_query, normalize_text, limit=2)
        if len(contextual_matches) == 1:
            match = contextual_matches[0]
            docname = match.get("name")
            display = match.get("display") or docname
            if docname:
                return NavigationTarget(
                    label=f"{current_doctype} {display}",
                    kind="document",
                    route=["Form", current_doctype, docname],
                    query=normalized_query,
                    doctype=current_doctype,
                    docname=docname,
                    document_query=clean_document_query(raw_query),
                )

    matches = find_bare_documents(raw_query, normalize_text, get_bare_record_doctype_priority(context))
    if not matches:
        return None
    if len(matches) > 1:
        return make_ambiguous_document_target(raw_query, normalized_query, matches)

    match = matches[0]
    doctype = match.get("doctype")
    docname = match.get("name")
    display = match.get("display") or docname
    if not doctype or not docname:
        return None

    return NavigationTarget(
        label=f"{doctype} {display}",
        kind="document",
        route=["Form", doctype, docname],
        query=normalized_query,
        doctype=doctype,
        docname=docname,
        document_query=clean_document_query(raw_query),
    )


def make_ambiguous_document_target(raw_query, normalized_query, matches):
    options = make_document_options(raw_query, normalized_query, matches)
    if not options:
        return None

    return NavigationTarget(
        label=clean_document_query(raw_query),
        kind="ambiguous_document",
        route=[],
        query=normalized_query,
        document_query=clean_document_query(raw_query),
        resolved=False,
        options=options,
    )


def make_document_options(raw_query, normalized_query, matches):
    options = []
    for match in matches[:6]:
        doctype = match.get("doctype")
        docname = match.get("name")
        display = match.get("display") or docname
        if not doctype or not docname:
            continue
        options.append(
            NavigationTarget(
                label=f"{doctype} {display}",
                kind="document",
                route=["Form", doctype, docname],
                query=normalized_query,
                doctype=doctype,
                docname=docname,
                document_query=clean_document_query(raw_query),
            ).to_dict()
        )
    return options


def split_doctype_and_document(raw_query, normalized_query):
    aliases = sorted(DOCTYPE_ALIASES.items(), key=lambda item: len(normalize_text(item[0])), reverse=True)
    for alias, doctype in aliases:
        alias_norm = normalize_text(alias)
        if normalized_query == alias_norm:
            return doctype, ""
        if normalized_query.startswith(f"{alias_norm} "):
            alias_word_count = len(alias_norm.split())
            words = raw_query.split()
            document_query = " ".join(words[alias_word_count:])
            return doctype, clean_document_query(document_query)

    fuzzy_request = split_fuzzy_doctype_and_document(raw_query, normalized_query)
    if fuzzy_request:
        return fuzzy_request

    doctype = find_doctype(normalized_query)
    if doctype:
        return doctype, ""

    return None


def should_search_bare_record(normalized_query):
    words = normalized_query.split()
    if not words or len(words) > 6:
        return False
    if normalized_query in PAGE_ALIASES or normalized_query in WORKSPACE_ALIASES or normalized_query in DOCTYPE_ALIASES:
        return False
    return True


def get_bare_record_doctype_priority(context=None):
    priority = list(BARE_RECORD_DOCTYPE_PRIORITY)
    context_object = ((context or {}).get("object") or {}) if isinstance(context, dict) else {}
    current_doctype = context_object.get("doctype")
    if current_doctype and current_doctype in priority:
        priority.remove(current_doctype)
        priority.insert(0, current_doctype)
    return priority


def find_bare_document(document_query, normalize, doctypes=None):
    matches = find_bare_documents(document_query, normalize, doctypes=doctypes)
    return matches[0] if matches else None


def find_bare_documents(document_query, normalize, doctypes=None):
    try:
        import frappe  # noqa: F401
    except Exception:
        return []

    matches = []
    seen = set()
    for doctype in doctypes or BARE_RECORD_DOCTYPE_PRIORITY:
        doctype_matches = find_documents(doctype, document_query, normalize, limit=3)
        match = doctype_matches[0] if doctype_matches else None
        if match:
            key = (doctype, match.get("name"))
            if key in seen:
                continue
            seen.add(key)
            matches.append({
                "doctype": doctype,
                "name": match.get("name"),
                "display": match.get("display"),
            })
        if len(matches) >= 6:
            break
    return matches


def find_alternate_documents(document_query, normalize, exclude_doctype=""):
    if not is_frappe_available():
        return []

    matches = []
    seen = set()
    for doctype in BARE_RECORD_DOCTYPE_PRIORITY:
        if doctype == exclude_doctype:
            continue
        for match in find_documents(doctype, document_query, normalize, limit=2):
            key = (doctype, match.get("name"))
            if not match or key in seen:
                continue
            seen.add(key)
            matches.append(
                {
                    "doctype": doctype,
                    "name": match.get("name"),
                    "display": match.get("display"),
                }
            )
        if len(matches) >= 4:
            break
    return matches


def is_frappe_available():
    try:
        import frappe  # noqa: F401
    except Exception:
        return False
    return True


def make_workspace_target(workspace, query, fallbacks=None):
    fallback_routes = [["Workspace", workspace]]
    for fallback in fallbacks or []:
        fallback_routes.append(["Workspaces", fallback])
        fallback_routes.append(["Workspace", fallback])

    return NavigationTarget(
        label=workspace,
        kind="workspace",
        route=["Workspaces", workspace],
        fallback_routes=fallback_routes,
        query=query,
    )


def find_workspace(query):
    alias_candidates = WORKSPACE_ALIASES.get(query, [])
    candidates = alias_candidates + [titleize(query), query]
    return find_workspace_by_query(query, candidates, normalize_text, allow_fallback=bool(alias_candidates))


def find_doctype(query):
    alias = DOCTYPE_ALIASES.get(query)
    if alias:
        return alias

    return find_doctype_by_query(query, normalize_text)


def clean_document_query(value):
    return re.sub(r"\s+", " ", (value or "").strip().strip(".,;:()[]{}\"'")).strip()


def split_fuzzy_doctype_and_document(raw_query, normalized_query):
    words = normalized_query.split()
    raw_words = raw_query.split()
    best = None
    for alias, doctype in DOCTYPE_ALIASES.items():
        alias_norm = normalize_text(alias)
        alias_word_count = len(alias_norm.split())
        if len(words) <= alias_word_count:
            continue

        candidate = " ".join(words[:alias_word_count])
        score = similarity(candidate, alias_norm)
        if score >= 0.78 and (not best or score > best[0]):
            document_query = " ".join(raw_words[alias_word_count:])
            best = (score, doctype, clean_document_query(document_query))

    if not best:
        return None
    return best[1], best[2]


def find_fuzzy_doctype_alias(query):
    match = best_fuzzy_match(query, DOCTYPE_ALIASES.keys(), threshold=0.78)
    return DOCTYPE_ALIASES.get(match) if match else None


def find_fuzzy_workspace_alias(query):
    match = best_fuzzy_match(query, WORKSPACE_ALIASES.keys(), threshold=0.78)
    if match:
        return WORKSPACE_ALIASES[match][0]
    return None


def best_fuzzy_match(query, candidates, threshold=0.78):
    best = None
    for candidate in candidates:
        score = similarity(query, normalize_text(candidate))
        if score >= threshold and (not best or score > best[0]):
            best = (score, candidate)
    return best[1] if best else None


def similarity(left, right):
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()
