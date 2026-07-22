def get_doctype_summary(doctype):
    if not doctype:
        return None

    try:
        import frappe

        meta = frappe.get_meta(doctype)
    except Exception:
        return {"doctype": doctype, "available": False}

    fields = []
    for field in meta.fields[:20]:
        fields.append(
            {
                "fieldname": field.fieldname,
                "label": field.label,
                "fieldtype": field.fieldtype,
                "reqd": bool(field.reqd),
            }
        )

    return {
        "doctype": meta.name,
        "available": True,
        "module": meta.module,
        "title_field": meta.title_field,
        "fields": fields,
    }

