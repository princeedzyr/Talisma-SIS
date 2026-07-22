from datetime import datetime

from wingman_ai.crm_crud.framework import UniversalCRMCRUDFramework
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.operation_engine.blueprint import split_options


class CRMCRUDCertificationRunner:
    """Runs metadata-driven create/update certification against the active ERP service."""

    def __init__(self, framework=None, erp_service=None):
        self.framework = framework or UniversalCRMCRUDFramework(erp_service=erp_service)
        self.erp_service = erp_service or self.framework.erp_service
        self.created_records = []
        self.run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    def run(self, user=None, execute_writes=False, cleanup=False):
        results = []
        for row in self.framework.discover_doctypes():
            doctype = row.get("name")
            if not doctype:
                continue
            results.append(self.certify_doctype(doctype, user=user, execute_writes=execute_writes))

        if cleanup and execute_writes:
            self.cleanup(user=user)

        return {
            "success": all(item.get("overall") == "PASS" for item in results),
            "execute_writes": bool(execute_writes),
            "run_id": self.run_id,
            "doctype_count": len(results),
            "results": results,
            "health_score": health_score(results),
        }

    def certify_doctype(self, doctype, user=None, execute_writes=False):
        result = certification_result(doctype)
        try:
            blueprint = self.framework.build_blueprint(doctype, operation="create")
            result["metadata"] = pass_or_fail(bool(blueprint.get("metadata")))
            result["blueprint"] = pass_or_fail(bool(blueprint.get("doctype") == doctype))
            result["conversation"] = pass_or_fail(bool((blueprint.get("fields") or {}).get("editable") is not None))
            result["dependencies"] = pass_or_fail(
                all(
                    item.get("resolver") == "UniversalLinkResolutionEngine"
                    for item in blueprint.get("dependency_rules") or []
                    if item.get("target_doctype")
                )
            )
            result["recommendations"] = pass_or_fail(bool(blueprint.get("post_operation_recommendations")))

            payload_result = self.build_create_payload(doctype, blueprint, user=user, stack=[])
            if not payload_result.get("success"):
                return self.fail(result, "Create Payload", payload_result)
            create_payload = payload_result.get("data") or {}
            result["create_payload"] = safe_payload(create_payload)

            preflight = self.erp_service.validate_document(
                doctype,
                data=create_payload,
                operation="create",
                user=user,
                run_business_hooks=True,
            )
            if not response_success(preflight):
                return self.fail(
                    result,
                    "Preflight Validation",
                    {
                        "classification": "Validation",
                        "component": "UniversalPreflightValidationEngine",
                        "response": preflight,
                        "message": first_issue_message(preflight),
                    },
                )
            result["validation"] = "PASS"

            if not execute_writes:
                result["create"] = "NOT RUN"
                result["read"] = "NOT RUN"
                result["update"] = "NOT RUN"
                result["search"] = "NOT RUN"
                result["overall"] = "NOT LIVE CERTIFIED"
                return result

            create_response = self.framework.create_record(doctype, create_payload, user=user)
            if not response_success(create_response):
                return self.fail(
                    result,
                    "Create API",
                    {
                        "classification": "Execution",
                        "component": "UniversalCreateService",
                        "response": create_response,
                        "message": first_issue_message(create_response),
                    },
                )
            result["create"] = "PASS"
            created = create_response.get("result") or {}
            docname = created.get("name") or created.get("docname")
            if not docname:
                return self.fail(
                    result,
                    "Create API",
                    {
                        "classification": "Execution",
                        "component": "UniversalCreateService",
                        "message": "Talisma OneCampus create response did not include a document name.",
                    },
                )
            result["docname"] = docname
            self.created_records.append((doctype, docname))

            read_response = self.framework.read_record(doctype, docname, user=user)
            if not response_success(read_response):
                return self.fail(
                    result,
                    "Read Back",
                    {
                        "classification": "API",
                        "component": "UniversalReadService",
                        "response": read_response,
                        "message": first_issue_message(read_response),
                    },
                )
            result["read"] = "PASS"
            stored = read_response.get("result") or {}
            verification = verify_payload(create_payload, stored)
            if not verification.get("success"):
                return self.fail(
                    result,
                    "Create Verification",
                    {
                        "classification": "Execution",
                        "component": "UniversalCreateService",
                        "message": verification.get("message"),
                        "mismatches": verification.get("mismatches"),
                    },
                )

            update_payload = self.build_update_payload(blueprint, stored)
            result["update_payload"] = safe_payload(update_payload)
            if not update_payload:
                result["update"] = "SKIPPED"
            else:
                update_preflight = self.erp_service.validate_document(
                    doctype,
                    data=update_payload,
                    docname=docname,
                    operation="write",
                    user=user,
                    run_business_hooks=True,
                )
                if not response_success(update_preflight):
                    return self.fail(
                        result,
                        "Update Preflight",
                        {
                            "classification": "Validation",
                            "component": "UniversalPreflightValidationEngine",
                            "response": update_preflight,
                            "message": first_issue_message(update_preflight),
                        },
                    )
                update_response = self.framework.update_record(doctype, docname, update_payload, user=user)
                if not response_success(update_response):
                    return self.fail(
                        result,
                        "Update API",
                        {
                            "classification": "Execution",
                            "component": "UniversalUpdateService",
                            "response": update_response,
                            "message": first_issue_message(update_response),
                        },
                    )
                read_after_update = self.framework.read_record(doctype, docname, user=user)
                if not response_success(read_after_update):
                    return self.fail(
                        result,
                        "Update Read Back",
                        {
                            "classification": "API",
                            "component": "UniversalReadService",
                            "response": read_after_update,
                            "message": first_issue_message(read_after_update),
                        },
                    )
                update_verification = verify_payload(update_payload, read_after_update.get("result") or {})
                if not update_verification.get("success"):
                    return self.fail(
                        result,
                        "Update Verification",
                        {
                            "classification": "Execution",
                            "component": "UniversalUpdateService",
                            "message": update_verification.get("message"),
                            "mismatches": update_verification.get("mismatches"),
                        },
                    )
                result["update"] = "PASS"

            search_response = self.framework.search_records(doctype, text=docname, fields=["name"], page_size=5, user=user)
            if not response_success(search_response):
                return self.fail(
                    result,
                    "Search",
                    {
                        "classification": "API",
                        "component": "UniversalSearchService",
                        "response": search_response,
                        "message": first_issue_message(search_response),
                    },
                )
            result["search"] = "PASS"
            result["overall"] = "PASS" if result.get("update") in {"PASS", "SKIPPED"} else "FAIL"
            return result
        except Exception as exc:
            return self.fail(
                result,
                "Unexpected Exception",
                {
                    "classification": "Unknown",
                    "component": "CRMCRUDCertificationRunner",
                    "message": f"{type(exc).__name__}: {exc}",
                },
            )

    def build_create_payload(self, doctype, blueprint, user=None, stack=None):
        stack = list(stack or [])
        if doctype in stack:
            return {
                "success": False,
                "classification": "Dependency",
                "component": "DependencyResolutionService",
                "message": f"Dependency cycle detected while preparing {doctype}.",
            }

        data = {}
        primary = blueprint.get("primary_field") or {}
        if primary.get("fieldname"):
            data[primary["fieldname"]] = self.sample_value(doctype, primary)

        for field in (blueprint.get("fields") or {}).get("required") or []:
            if not is_editable_business_field(field):
                continue
            fieldname = field.get("fieldname")
            if not fieldname or data.get(fieldname) not in (None, "", []):
                continue
            value_result = self.value_for_field(doctype, field, user=user, stack=stack)
            if not value_result.get("success"):
                return value_result
            if value_result.get("value") not in (None, "", []):
                data[fieldname] = value_result.get("value")

        for fieldname, value in (blueprint.get("default_values") or {}).items():
            if fieldname not in data and value not in (None, "", "__user"):
                data[fieldname] = value

        return {"success": True, "data": data}

    def value_for_field(self, doctype, field, user=None, stack=None):
        fieldtype = field.get("fieldtype")
        if fieldtype == "Link":
            return self.resolve_link_value(field, user=user, stack=stack)
        if fieldtype in {"Table", "Table MultiSelect"}:
            return self.child_table_value(field, user=user, stack=stack)
        return {"success": True, "value": self.sample_value(doctype, field)}

    def resolve_link_value(self, field, user=None, stack=None):
        target = field.get("options")
        if not target:
            return {"success": True, "value": None}

        default = field.get("default")
        if default and default != "__user":
            read_default = self.framework.read_record(target, default, user=user)
            if response_success(read_default):
                return {"success": True, "value": default}

        search = self.framework.search_records(target, text="", fields=["name"], page_size=1, user=user)
        rows = ((search.get("result") or {}).get("rows") or []) if isinstance(search, dict) else []
        if rows and rows[0].get("name"):
            return {"success": True, "value": rows[0]["name"]}

        if target in (stack or []):
            return {
                "success": False,
                "classification": "Dependency",
                "component": "DependencyResolutionService",
                "message": f"No existing {target} record was found and creating it would create a dependency cycle.",
            }

        target_blueprint = self.framework.build_blueprint(target, operation="create")
        target_payload = self.build_create_payload(target, target_blueprint, user=user, stack=(stack or []) + [target])
        if not target_payload.get("success"):
            return target_payload

        create_response = self.framework.create_record(target, target_payload.get("data") or {}, user=user)
        if not response_success(create_response):
            return {
                "success": False,
                "classification": "Dependency",
                "component": "DependencyResolutionService",
                "response": create_response,
                "message": first_issue_message(create_response),
            }
        created = create_response.get("result") or {}
        docname = created.get("name") or created.get("docname")
        if docname:
            self.created_records.append((target, docname))
        return {"success": True, "value": docname}

    def child_table_value(self, field, user=None, stack=None):
        child_doctype = field.get("options")
        if not child_doctype:
            return {"success": True, "value": []}
        child_blueprint = self.framework.build_blueprint(child_doctype, operation="create")
        row = self.build_create_payload(child_doctype, child_blueprint, user=user, stack=(stack or []) + [child_doctype])
        if not row.get("success"):
            return row
        return {"success": True, "value": [row.get("data") or {}]}

    def build_update_payload(self, blueprint, stored):
        updates = {}
        for field in (blueprint.get("fields") or {}).get("editable") or []:
            fieldname = field.get("fieldname")
            if not fieldname or field.get("fieldtype") in {"Link", "Dynamic Link", "Table", "Table MultiSelect"}:
                continue
            if fieldname not in stored:
                continue
            value = self.next_update_value(blueprint.get("doctype"), field, stored.get(fieldname))
            if value in (None, "", []) or value == stored.get(fieldname):
                continue
            updates[fieldname] = value
            if len(updates) >= 2:
                break
        return updates

    def sample_value(self, doctype, field):
        fieldname = str(field.get("fieldname") or "").lower()
        label = str(field.get("label") or "").lower()
        fieldtype = field.get("fieldtype")
        if "email" in fieldname or "email" in label:
            return f"wingman.qa+{self.run_id}@example.com"
        if "phone" in fieldname or "mobile" in fieldname:
            return "9999999999"
        if fieldtype == "Select":
            return field.get("default") or first_option(field)
        if fieldtype == "Check":
            return 0
        if fieldtype in {"Int", "Float", "Currency", "Percent"}:
            return 1
        if fieldtype == "Date":
            return datetime.utcnow().strftime("%Y-%m-%d")
        if fieldtype == "Datetime":
            return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return f"Wingman QA {doctype} {self.run_id}"

    def next_update_value(self, doctype, field, current):
        fieldtype = field.get("fieldtype")
        if fieldtype == "Select":
            options = split_options(field.get("options"))
            for option in options:
                if option != current:
                    return option
            return current
        if fieldtype == "Check":
            return 0 if bool(current) else 1
        if fieldtype == "Int":
            return int(current or 0) + 1
        if fieldtype in {"Float", "Currency", "Percent"}:
            return float(current or 0) + 1
        if fieldtype in {"Date", "Datetime", "Time"}:
            return None
        if "email" in str(field.get("fieldname") or "").lower():
            return f"wingman.qa.updated+{self.run_id}@example.com"
        return f"{current or f'Wingman QA {doctype}'} Updated"

    def cleanup(self, user=None):
        for doctype, docname in reversed(self.created_records):
            try:
                self.framework.delete_record(doctype, docname, user=user)
            except Exception:
                pass

    def fail(self, result, stage, details):
        result["overall"] = "FAIL"
        result["failure"] = {
            "stage": stage,
            "root_cause": details.get("message") or "Certification failed.",
            "classification": details.get("classification") or "Unknown",
            "framework_component": details.get("component") or "Unknown",
            "erpnext_validation_message": details.get("message") or first_issue_message(details.get("response")),
            "wingman_analysis": details.get("message") or "Wingman could not complete this certification stage.",
            "recommended_framework_fix": recommended_fix(details.get("classification")),
            "fix_applied": False,
            "retest_result": "NOT RETESTED",
            "response": details.get("response"),
            "mismatches": details.get("mismatches") or [],
        }
        for key in ("create", "read", "update", "search", "validation"):
            result.setdefault(key, "NOT RUN")
        return result


def certification_result(doctype):
    return {
        "doctype": doctype,
        "metadata": "NOT RUN",
        "blueprint": "NOT RUN",
        "conversation": "NOT RUN",
        "validation": "NOT RUN",
        "dependencies": "NOT RUN",
        "create": "NOT RUN",
        "read": "NOT RUN",
        "update": "NOT RUN",
        "search": "NOT RUN",
        "recommendations": "NOT RUN",
        "overall": "NOT RUN",
    }


def verify_payload(expected, stored):
    mismatches = []
    for fieldname, value in (expected or {}).items():
        if value in (None, "", []):
            continue
        stored_value = (stored or {}).get(fieldname)
        if normalize_value(stored_value) != normalize_value(value):
            mismatches.append({"fieldname": fieldname, "expected": value, "stored": stored_value})
    return {
        "success": not mismatches,
        "message": "Stored values did not match the conversational input." if mismatches else None,
        "mismatches": mismatches,
    }


def normalize_value(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value or "").strip()


def response_success(response):
    if not isinstance(response, dict):
        return False
    if "success" in response:
        return bool(response.get("success"))
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    if "valid" in result:
        return bool(result.get("valid"))
    return True


def first_issue_message(response):
    if not isinstance(response, dict):
        return None
    for issue in response.get("validation_issues") or []:
        if isinstance(issue, dict) and issue.get("message"):
            return issue.get("message")
    for error in response.get("errors") or []:
        if isinstance(error, dict) and error.get("message"):
            return error.get("message")
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    for issue in result.get("issues") or []:
        if isinstance(issue, dict) and issue.get("message"):
            return issue.get("message")
    return response.get("message")


def health_score(results):
    categories = {
        "Metadata Coverage": ("metadata",),
        "CRUD Coverage": ("create", "read", "update", "search"),
        "Conversation Coverage": ("conversation",),
        "Validation Coverage": ("validation",),
        "Dependency Resolution Coverage": ("dependencies",),
        "Recommendation Coverage": ("recommendations",),
        "ERP Integration Coverage": ("create", "read", "update"),
        "Regression Coverage": ("overall",),
    }
    scores = {}
    for label, keys in categories.items():
        total = len(results) * len(keys)
        passed = sum(1 for result in results for key in keys if result.get(key) in {"PASS", "SKIPPED"})
        scores[label] = int((passed / total) * 100) if total else 0
    scores["Overall Framework Health"] = int(sum(scores.values()) / len(scores)) if scores else 0
    return scores


def recommended_fix(classification):
    return {
        "Metadata": "Fix CRMMetadataService or metadata normalization.",
        "Validation": "Fix UniversalPreflightValidationEngine interpretation or payload preparation.",
        "Workflow": "Respect Talisma OneCampus workflow state and expose the missing transition guidance.",
        "Permission": "Surface permission guidance without bypassing Talisma OneCampus permissions.",
        "Dependency": "Fix DependencyResolutionService or UniversalLinkResolutionEngine.",
        "Configuration": "Report the missing Talisma OneCampus setup prerequisite and pause the workflow.",
        "API": "Fix ERP service response handling.",
        "Conversation": "Fix ConversationSessionManager state transition.",
        "Execution": "Fix operation service payload execution and read-back verification.",
        "UI": "Fix UI component metadata mapping.",
    }.get(classification or "Unknown", "Investigate the responsible shared framework component.")


def first_option(field):
    options = split_options(field.get("options"))
    return options[0] if options else None


def pass_or_fail(value):
    return "PASS" if value else "FAIL"


def safe_payload(payload):
    redacted = {}
    for key, value in (payload or {}).items():
        if "password" in str(key).lower() or "secret" in str(key).lower():
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted
