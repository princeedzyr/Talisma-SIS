import json
from urllib.parse import unquote


FORM_ROUTE_TYPES = ("Form",)
LIST_ROUTE_TYPES = ("List",)
WORKSPACE_ROUTE_TYPES = ("Workspace", "Workspaces")
REPORT_ROUTE_TYPES = ("query-report", "Query Report")
KNOWN_ROUTE_TYPES = FORM_ROUTE_TYPES + LIST_ROUTE_TYPES + WORKSPACE_ROUTE_TYPES + REPORT_ROUTE_TYPES


def parse_context(context):
    if not context:
        return {}

    if isinstance(context, dict):
        return context

    if isinstance(context, str):
        try:
            parsed = json.loads(context)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    return {}


def summarize_context(context):
    context_object = get_context_object(context)
    route_type = context_object.get("route_type")
    doctype = context_object.get("doctype")
    docname = context_object.get("docname")
    workspace = context_object.get("workspace")
    report_name = context_object.get("report_name")

    if route_type == "Form" and doctype and docname:
        return f"You are currently viewing {doctype} {docname}."
    if route_type == "List" and doctype:
        return f"You are currently viewing the {doctype} list."
    if route_type == "Workspace" and workspace:
        return f"You are currently in the {workspace} workspace."
    if route_type == "Query Report" and report_name:
        return f"You are currently viewing the {report_name} report."
    if route_type:
        return f"You are currently on the {route_type} page."

    page_title = context.get("page_title")
    if page_title:
        return f"You are currently on {page_title}."

    return "You are currently in Talisma OneCampus."


def get_context_object(context):
    route = normalize_route(context.get("route"))
    route_type = route[0] if route else None
    explicit_doctype = context.get("doctype")
    explicit_docname = context.get("docname")
    pathname_context = parse_pathname(context.get("pathname"))

    if route_type in WORKSPACE_ROUTE_TYPES and len(route) > 1:
        doctype = None
        docname = None
        route_type = "Workspace"
    elif route_type in REPORT_ROUTE_TYPES and len(route) > 1:
        doctype = None
        docname = None
        route_type = "Query Report"
        route = ["query-report", route[1]]
    elif route_type in FORM_ROUTE_TYPES and len(route) > 2:
        doctype = route[1]
        docname = route[2]
    elif route_type in LIST_ROUTE_TYPES and len(route) > 1:
        doctype = route[1]
        docname = None
    elif explicit_doctype and explicit_docname:
        doctype = explicit_doctype
        docname = explicit_docname
        route_type = "Form"
        route = ["Form", doctype, docname]
    elif explicit_doctype:
        doctype = explicit_doctype
        docname = None
        route_type = "List"
        route = ["List", doctype]
    elif pathname_context:
        route_type = pathname_context["route_type"]
        route = pathname_context["route"]
        doctype = pathname_context.get("doctype")
        docname = pathname_context.get("docname")
    elif route and route_type not in KNOWN_ROUTE_TYPES:
        doctype = label_from_slug(route[0])
        docname = route[1] if len(route) > 1 else None
        route_type = "Form" if docname else "List"
        route = ["Form", doctype, docname] if docname else ["List", doctype]
    else:
        doctype = context.get("doctype")
        docname = context.get("docname")

    workspace = None
    report_name = None
    if route_type == "Workspace" and len(route) > 1:
        workspace = route[1]
    elif route_type == "Query Report" and len(route) > 1:
        report_name = route[1]
    elif not doctype:
        workspace = context.get("workspace")

    return {
        "route": route,
        "route_type": route_type,
        "doctype": doctype,
        "docname": docname,
        "workspace": workspace,
        "report_name": report_name,
        "page_title": context.get("page_title"),
        "pathname": context.get("pathname"),
    }


def normalize_route(route):
    if not route:
        return []
    if isinstance(route, str):
        route = [route]
    return [unquote(str(part)) for part in route if part is not None and str(part) != ""]


def parse_pathname(pathname):
    if not pathname:
        return None

    parts = [unquote(part) for part in str(pathname).strip("/").split("/") if part]
    if not parts or parts[0].lower() != "desk":
        return None

    desk_parts = parts[1:]
    if not desk_parts:
        return None

    if desk_parts[0].lower() == "workspaces" and len(desk_parts) > 1:
        workspace = desk_parts[1]
        return {"route_type": "Workspace", "route": ["Workspace", workspace], "workspace": workspace}

    if desk_parts[0].lower() == "query-report" and len(desk_parts) > 1:
        report_name = desk_parts[1]
        return {
            "route_type": "Query Report",
            "route": ["query-report", report_name],
            "report_name": report_name,
        }

    doctype = label_from_slug(desk_parts[0])
    if len(desk_parts) > 1:
        docname = desk_parts[1]
        return {
            "route_type": "Form",
            "route": ["Form", doctype, docname],
            "doctype": doctype,
            "docname": docname,
        }

    return {"route_type": "List", "route": ["List", doctype], "doctype": doctype}


def label_from_slug(value):
    return " ".join(word.capitalize() for word in str(value or "").replace("-", " ").replace("_", " ").split())
