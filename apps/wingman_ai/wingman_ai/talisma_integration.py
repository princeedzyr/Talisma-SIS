import frappe

from wingman_ai.application.navigation_resolver import DOCTYPE_ALIASES, WORKSPACE_ALIASES


def healthcheck():
    """Verify that Wingman is wired to the authoritative Talisma SIS model."""
    expected_aliases = {
        "students": "Student",
        "guardians": "Guardian",
        "enrollments": "Program Enrollment",
        "attendance": "Student Attendance",
        "results": "Assessment Result",
        "student fees": "Fees",
    }
    missing_doctypes = sorted(
        {doctype for doctype in expected_aliases.values() if not frappe.db.exists("DocType", doctype)}
    )
    mismatched_aliases = {
        alias: {"expected": doctype, "actual": DOCTYPE_ALIASES.get(alias)}
        for alias, doctype in expected_aliases.items()
        if DOCTYPE_ALIASES.get(alias) != doctype
    }
    hooks = frappe.get_hooks()
    desk_scripts = hooks.get("app_include_js") or []
    desk_styles = hooks.get("app_include_css") or []
    bot_script = "/assets/wingman_ai/js/wingman_chat.js"
    bot_style = "/assets/wingman_ai/css/wingman_chat.css"

    checks = {
        "talisma_sis_installed": "talisma_sis" in frappe.get_installed_apps(),
        "education_installed": "education" in frappe.get_installed_apps(),
        "authoritative_doctypes": not missing_doctypes,
        "navigation_aliases": not mismatched_aliases,
        "sis_workspace_alias": WORKSPACE_ALIASES.get("sis") == ["Education"],
        "bot_script_hook": any(str(asset).split("?", 1)[0] == bot_script for asset in desk_scripts),
        "bot_style_hook": any(str(asset).split("?", 1)[0] == bot_style for asset in desk_styles),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "missing_doctypes": missing_doctypes,
        "mismatched_aliases": mismatched_aliases,
        "bot_script": bot_script,
        "bot_style": bot_style,
    }
