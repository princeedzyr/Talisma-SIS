import frappe


@frappe.whitelist()
def confirm(action=None, payload=None):
    return {
        "status": "review_required",
        "message": "Action confirmation is wired, but write execution is not enabled in this migration step.",
        "action": action,
        "payload": payload,
    }

