from wingman_ai.operation_engine.blueprint import field_label


class OperationPlanBuilder:
    """Builds the mutable state object shared by create, update, and future operations."""

    def build_create_plan(
        self,
        blueprint,
        data=None,
        supplied_data=None,
        defaults_applied=None,
        missing_fields=None,
        dependencies=None,
        preflight=None,
        setup_field=None,
    ):
        return self.build_operation_plan(
            "create",
            blueprint,
            data=data,
            supplied_data=supplied_data,
            defaults_applied=defaults_applied,
            missing_fields=missing_fields,
            dependencies=dependencies,
            preflight=preflight,
            setup_field=setup_field,
        )

    def build_update_plan(
        self,
        blueprint,
        changes=None,
        current=None,
        missing_fields=None,
        dependencies=None,
        preflight=None,
        docname=None,
    ):
        return self.build_operation_plan(
            "update",
            blueprint,
            data=changes,
            supplied_data=changes,
            missing_fields=missing_fields,
            dependencies=dependencies,
            preflight=preflight,
            current_data=current,
            docname=docname,
        )

    def build_operation_plan(
        self,
        operation,
        blueprint,
        data=None,
        supplied_data=None,
        defaults_applied=None,
        missing_fields=None,
        dependencies=None,
        preflight=None,
        setup_field=None,
        current_data=None,
        docname=None,
    ):
        data = dict(data or {})
        supplied_data = dict(supplied_data or {})
        defaults_applied = list(defaults_applied or [])
        missing_fields = list(missing_fields or [])
        dependencies = list(dependencies or [])
        preflight = preflight or {"valid": True, "issues": []}

        unresolved = []
        for field in missing_fields:
            append_unresolved(unresolved, field, reason="required")

        preflight_field = preflight.get("field") if not preflight.get("valid") else None
        if preflight_field and not has_unresolved(unresolved, preflight_field.get("fieldname")):
            append_unresolved(unresolved, preflight_field, reason="validation")

        if setup_field and not has_unresolved(unresolved, setup_field.get("fieldname")):
            append_unresolved(unresolved, setup_field, reason="recommended_setup", optional=bool(setup_field.get("optional")))

        next_item = unresolved[0] if unresolved else None
        next_field = next_item.get("field") if next_item else None
        ready = not unresolved and not dependencies and bool(preflight.get("valid", True))

        return {
            "operation": operation or (blueprint or {}).get("operation") or "create",
            "doctype": (blueprint or {}).get("doctype"),
            "docname": docname,
            "status": operation_status(ready, unresolved, dependencies, preflight),
            "conversation_step": 1,
            "collected_fields": data,
            "current_fields": dict(current_data or {}),
            "supplied_fields": supplied_data,
            "defaulted_fields": defaults_applied,
            "missing_fields": [item.get("label") for item in unresolved],
            "unresolved_fields": unresolved,
            "dependencies": dependencies,
            "validation_state": "Passed" if preflight.get("valid", True) else "Pending",
            "validation": preflight,
            "next_field": next_field,
            "ready": ready,
            "blueprint_summary": summarize_blueprint(blueprint),
        }


def append_unresolved(items, field, reason=None, optional=False):
    if not field:
        return
    items.append(
        {
            "fieldname": field.get("fieldname"),
            "label": field_label(field),
            "fieldtype": field.get("fieldtype"),
            "options": field.get("options"),
            "reason": reason,
            "optional": optional,
            "field": field,
        }
    )


def has_unresolved(items, fieldname):
    return any(item.get("fieldname") == fieldname for item in items or [])


def operation_status(ready, unresolved, dependencies, preflight):
    if ready:
        return "Ready"
    if dependencies:
        return "Resolving Dependencies"
    if unresolved:
        return "Collecting"
    if not preflight.get("valid", True):
        return "Validation Pending"
    return "Planning"


def summarize_blueprint(blueprint):
    fields = (blueprint or {}).get("fields") or {}
    return {
        "editable_field_count": len(fields.get("editable") or []),
        "required_field_count": len(fields.get("required") or []),
        "conditional_required_field_count": len(fields.get("conditional_required") or []),
        "link_field_count": len(fields.get("links") or []),
        "child_table_count": len(fields.get("child_tables") or []),
        "has_permissions": bool((blueprint or {}).get("permission_rules")),
        "has_workflow": bool((blueprint or {}).get("workflow_rules")),
    }
