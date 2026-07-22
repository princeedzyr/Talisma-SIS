from wingman_ai.conversation_decision_policy import (
    ALWAYS_ASK_GROUP,
    CONTEXT_DERIVED_GROUP,
    DERIVATION_CONFIDENCE_THRESHOLD,
    ERP_DEFAULT_GROUP,
    SYSTEM_FIELD_GROUP,
    can_use_metadata_default,
    confidence_for_source,
    field_policy,
)
from wingman_ai.crm_crud.framework import UniversalCRMCRUDFramework
from wingman_ai.field_behavior import component_for_field
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.operation_engine.blueprint import split_options


MANDATED_CRM_AUDIT_DOCTYPES = (
    "Lead",
    "Opportunity",
    "Contact",
    "Customer",
    "Appointment",
    "Contract",
    "Territory",
    "Lead Source",
    "Opportunity Type",
    "Sales Stage",
    "Email Campaign",
    "Newsletter",
    "Email Group",
)


class ConversationDecisionAuditor:
    """Audits whether Wingman conversation decisions are justified by metadata."""

    def __init__(self, framework=None, erp_service=None):
        self.framework = framework or UniversalCRMCRUDFramework(erp_service=erp_service)

    def audit(self, user=None, include_mandated=True):
        doctypes = self.audit_doctypes(include_mandated=include_mandated)
        results = [self.audit_doctype(doctype, user=user) for doctype in doctypes]
        findings = [finding for result in results for finding in result.get("incorrect_decisions") or []]
        scores = intelligence_scores(results)
        return {
            "success": not findings and bool(results),
            "production_ready": bool(results) and scores.get("Overall AI Decision Accuracy") == 100,
            "confidence_threshold": DERIVATION_CONFIDENCE_THRESHOLD,
            "doctype_count": len(results),
            "scores": scores,
            "conversation_intelligence_score": scores.get("Conversation Intelligence Score", 0),
            "metadata_accuracy": scores.get("Metadata Accuracy", 0),
            "derivation_accuracy": scores.get("Derivation Accuracy", 0),
            "question_accuracy": scores.get("Question Accuracy", 0),
            "validation_accuracy": scores.get("Validation Accuracy", 0),
            "ui_accuracy": scores.get("UI Accuracy", 0),
            "overall_ai_decision_accuracy": scores.get("Overall AI Decision Accuracy", 0),
            "incorrect_decisions": findings,
            "results": results,
        }

    def audit_doctypes(self, include_mandated=True):
        discovered = []
        try:
            discovered = [row.get("name") for row in self.framework.discover_doctypes() if row.get("name")]
        except Exception:
            discovered = []
        names = list(MANDATED_CRM_AUDIT_DOCTYPES if include_mandated else ())
        names.extend(discovered)
        return ordered_unique(names)

    def audit_doctype(self, doctype, user=None):
        result = {
            "doctype": doctype,
            "metadata": "NOT RUN",
            "blueprint": "NOT RUN",
            "field_decisions": [],
            "dependency_decisions": [],
            "recommendation_decisions": [],
            "incorrect_decisions": [],
            "scores": {},
            "overall": "NOT RUN",
        }
        try:
            blueprint = self.framework.build_blueprint(doctype, operation="create")
        except Exception as exc:
            finding = finding_record(
                doctype=doctype,
                field=None,
                decision="Metadata Load",
                expected="Load DocType metadata",
                source="Metadata",
                confidence=0,
                correct=False,
                reason=f"{type(exc).__name__}: {exc}",
                severity="CRITICAL",
                component="Metadata Engine",
                fix="Fix CRMMetadataService metadata loading for this DocType.",
            )
            result["metadata"] = "FAIL"
            result["blueprint"] = "FAIL"
            result["incorrect_decisions"].append(finding)
            result["scores"] = doctype_scores(result)
            result["overall"] = "FAIL"
            return result

        fields = (blueprint.get("fields") or {}).get("all") or []
        result["metadata"] = "PASS" if fields else "FAIL"
        result["blueprint"] = "PASS" if blueprint.get("doctype") == doctype else "FAIL"
        if not fields:
            result["incorrect_decisions"].append(
                finding_record(
                    doctype=doctype,
                    field=None,
                    decision="Metadata Load",
                    expected="Fields loaded",
                    source="Metadata",
                    confidence=0,
                    correct=False,
                    reason="No fields were returned for this DocType.",
                    severity="CRITICAL",
                    component="Metadata Engine",
                    fix="Load complete DocType metadata from Talisma OneCampus before conversation planning.",
                )
            )

        for field in fields:
            decision = self.audit_field(doctype, field, blueprint)
            result["field_decisions"].append(decision)
            if not decision.get("correct"):
                result["incorrect_decisions"].append(to_finding(decision))

        result["dependency_decisions"] = self.audit_dependencies(doctype, blueprint)
        result["recommendation_decisions"] = self.audit_recommendations(doctype, blueprint)
        for item in result["dependency_decisions"] + result["recommendation_decisions"]:
            if not item.get("correct"):
                result["incorrect_decisions"].append(to_finding(item))

        result["scores"] = doctype_scores(result)
        result["overall"] = "PASS" if not result["incorrect_decisions"] else "FAIL"
        return result

    def audit_field(self, doctype, field, blueprint):
        fieldname = field.get("fieldname")
        fields = blueprint.get("fields") or {}
        primary = blueprint.get("primary_field") or {}
        policy = field_policy(field, primary_fieldname=primary.get("fieldname"))
        editable_names = {item.get("fieldname") for item in fields.get("editable") or []}
        required_names = {item.get("fieldname") for item in fields.get("required") or []}
        default_values = blueprint.get("default_values") or {}
        dependency_names = {item.get("fieldname") for item in blueprint.get("dependency_rules") or []}
        ui_components = blueprint.get("ui_components") or {}

        actual = actual_decision(field, policy, editable_names, required_names, default_values, dependency_names)
        source = decision_source(actual, field, default_values)
        confidence = confidence_for_source(source)
        expected = policy["expected_decision"]
        correct, reason, severity, component, fix = validate_field_decision(
            field,
            policy,
            actual,
            expected,
            default_values,
            editable_names,
            required_names,
            dependency_names,
        )

        ui_decision = self.audit_ui_component(field, policy, ui_components)
        if not ui_decision["correct"]:
            correct = False
            reason = ui_decision["reason"]
            severity = ui_decision["severity"]
            component = "UI Engine"
            fix = "Fix shared UI component mapping for the field type."

        return {
            "doctype": doctype,
            "field": fieldname,
            "label": field.get("label") or humanize(fieldname),
            "field_type": field.get("fieldtype"),
            "mandatory": policy["mandatory"],
            "conditionally_mandatory": policy["conditionally_mandatory"],
            "read_only": policy["read_only"],
            "hidden": policy["hidden"],
            "virtual": policy["virtual"],
            "system_generated": policy["system_generated"],
            "user_default": policy["user_default"],
            "company_default": policy["company_default"],
            "derived": actual in {"Defaulted", "Context Derived"},
            "editable": policy["editable"],
            "link": policy["link"],
            "select": policy["select"],
            "table": policy["table"],
            "can_safely_derive": policy["can_derive"],
            "allowed_derivation_sources": policy["allowed_derivation_sources"],
            "policy_group": policy["derivation_policy_group"],
            "decision": actual,
            "expected_behavior": expected,
            "source": source,
            "confidence": int(confidence * 100),
            "correct": correct,
            "reason": reason,
            "severity": severity,
            "framework_component": component,
            "recommended_framework_fix": fix,
            "ui_component": ui_decision,
        }

    def audit_ui_component(self, field, policy, ui_components):
        fieldname = field.get("fieldname")
        actual = ui_components.get(fieldname)
        expected = expected_ui_component(field)
        if not policy["editable"]:
            return {
                "expected": None,
                "actual": actual,
                "correct": actual is None,
                "reason": "Non-editable/system fields must not receive conversational UI controls.",
                "severity": "CRITICAL" if actual else "INFO",
            }
        if not actual:
            return {
                "expected": expected,
                "actual": None,
                "correct": False,
                "reason": "Editable field is missing a UI component.",
                "severity": "HIGH",
            }
        actual_type = actual.get("type")
        if actual_type != expected.get("type"):
            return {
                "expected": expected,
                "actual": actual,
                "correct": False,
                "reason": f"Expected {expected.get('type')} but got {actual_type}.",
                "severity": "HIGH",
            }
        return {
            "expected": expected,
            "actual": actual,
            "correct": True,
            "reason": "UI component matches field metadata.",
            "severity": "INFO",
        }

    def audit_dependencies(self, doctype, blueprint):
        fields = (blueprint.get("fields") or {}).get("all") or []
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
        dependencies = blueprint.get("dependency_rules") or []
        decisions = []
        for dependency in dependencies:
            field = field_map.get(dependency.get("fieldname")) or {}
            editable = is_editable_business_field(field)
            valid_type = field.get("fieldtype") in {"Link", "Dynamic Link", "Table", "Table MultiSelect"}
            correct = bool(editable and valid_type)
            decisions.append(
                {
                    "doctype": doctype,
                    "field": dependency.get("fieldname"),
                    "decision": "Dependency Resolution",
                    "expected_behavior": "Resolve only editable business Link/Table fields.",
                    "source": "Metadata",
                    "confidence": 95,
                    "correct": correct,
                    "reason": "Dependency targets an editable business relationship." if correct else "Dependency was generated for a non-business or non-link field.",
                    "severity": "INFO" if correct else "CRITICAL",
                    "framework_component": "Dependency Engine",
                    "recommended_framework_fix": "Filter dependency generation through is_editable_business_field and relationship field types.",
                }
            )
        return decisions

    def audit_recommendations(self, doctype, blueprint):
        recommendations = blueprint.get("post_operation_recommendations") or []
        return [
            {
                "doctype": doctype,
                "field": None,
                "decision": "Post-operation Recommendations",
                "expected_behavior": "Provide context-aware next steps.",
                "source": "Metadata",
                "confidence": 90 if recommendations else 0,
                "correct": bool(recommendations),
                "reason": "Recommendations were generated." if recommendations else "No recommendations were generated.",
                "severity": "INFO" if recommendations else "MEDIUM",
                "framework_component": "Recommendation Engine",
                "recommended_framework_fix": "Generate metadata-driven recommendations for every CRM operation.",
            }
        ]


def actual_decision(field, policy, editable_names, required_names, default_values, dependency_names):
    fieldname = field.get("fieldname")
    if fieldname not in editable_names or policy["derivation_policy_group"] == SYSTEM_FIELD_GROUP:
        return "Excluded"
    if fieldname in default_values and default_values.get(fieldname) not in (None, ""):
        return "Defaulted"
    if fieldname in dependency_names:
        return "Dependency Prepared"
    if fieldname in required_names:
        return "Ask User"
    return "Skipped"


def decision_source(decision, field, default_values):
    if decision == "Defaulted":
        return "Talisma OneCampus Default"
    if decision == "Dependency Prepared":
        return "Metadata"
    if decision == "Ask User":
        return "Conversation"
    return "Metadata"


def validate_field_decision(field, policy, actual, expected, default_values, editable_names, required_names, dependency_names):
    fieldname = field.get("fieldname")
    group = policy["derivation_policy_group"]
    if group == SYSTEM_FIELD_GROUP:
        if fieldname in editable_names or fieldname in required_names or fieldname in default_values or fieldname in dependency_names:
            return (
                False,
                "System, hidden, read-only, or virtual fields must never become conversational fields.",
                "CRITICAL",
                "Metadata Engine",
                "Exclude system fields before required/default/dependency planning.",
            )
        return True, "System field correctly excluded.", "INFO", "Metadata Engine", None

    if actual == "Defaulted":
        if not can_use_metadata_default(field, primary_fieldname=fieldname if group == ALWAYS_ASK_GROUP else None):
            return (
                False,
                "This field is user-provided business data and must not be silently defaulted.",
                "CRITICAL",
                "Derivation Engine",
                "Block defaults for identity, contact, title, subject, description, and address fields unless explicitly provided by the conversation.",
            )
        return True, "Default is allowed by field policy.", "INFO", "Derivation Engine", None

    if group == ALWAYS_ASK_GROUP and policy["mandatory"] and actual != "Ask User":
        return (
            False,
            "Required user-provided business data was not asked for.",
            "CRITICAL",
            "Conversation Engine",
            "Ask for required Group A fields unless the user explicitly provided the value.",
        )

    if policy["mandatory"] and actual == "Skipped":
        return (
            False,
            "Mandatory field was skipped.",
            "CRITICAL",
            "Conversation Engine",
            "Route missing mandatory fields into the follow-up question workflow.",
        )

    if group == CONTEXT_DERIVED_GROUP and actual == "Defaulted":
        return (
            False,
            "Context-derived fields require explicit source, confidence, and reason.",
            "HIGH",
            "Derivation Engine",
            "Record derivation source, confidence, and reason for every context-derived value.",
        )

    return True, "Decision matches the field policy.", "INFO", component_for_group(group), None


def expected_ui_component(field):
    fieldtype = field.get("fieldtype")
    fieldname = str(field.get("fieldname") or "").lower()
    label = str(field.get("label") or "").lower()
    if fieldtype == "Link":
        return {**component_for_field(field), "label": "Search Dropdown"}
    if fieldtype == "Dynamic Link":
        return {**component_for_field(field), "label": "Search Dropdown"}
    if fieldtype == "Table":
        return {"type": "child_table", "child_doctype": field.get("options"), "label": "Table"}
    if fieldtype == "Table MultiSelect":
        return {"type": "multi_select", "target_doctype": field.get("options"), "label": "Table"}
    if fieldtype == "Select":
        return {"type": "select", "options": split_options(field.get("options")), "label": "Dropdown"}
    if fieldtype == "Check":
        return {"type": "checkbox", "label": "Checkbox"}
    if fieldtype == "Date":
        return {"type": "date", "label": "Date Picker"}
    if fieldtype == "Datetime":
        return {"type": "datetime", "label": "Date Picker"}
    if fieldtype == "Time":
        return {"type": "time", "label": "Date Picker"}
    if fieldtype in {"Int", "Float", "Percent"}:
        return {"type": "number", "label": "Text"}
    if fieldtype == "Currency":
        return {"type": "currency", "label": "Currency"}
    if fieldtype in {"Text", "Small Text", "Long Text", "Text Editor", "Code"}:
        return {"type": "textarea", "label": "Text"}
    if fieldtype in {"Attach", "Attach Image"}:
        return {"type": "attachment", "label": "Attachment"}
    if "email" in fieldname or "email" in label:
        return {"type": "email", "label": "Email"}
    if any(token in fieldname or token in label for token in ("phone", "mobile", "contact number")):
        return {"type": "phone", "label": "Phone"}
    return {"type": "text", "label": "Text"}


def to_finding(decision):
    return finding_record(
        doctype=decision.get("doctype"),
        field=decision.get("field"),
        decision=decision.get("decision"),
        expected=decision.get("expected_behavior"),
        source=decision.get("source"),
        confidence=decision.get("confidence"),
        correct=decision.get("correct"),
        reason=decision.get("reason"),
        severity=decision.get("severity"),
        component=decision.get("framework_component"),
        fix=decision.get("recommended_framework_fix"),
    )


def finding_record(doctype, field, decision, expected, source, confidence, correct, reason, severity, component, fix):
    return {
        "doctype": doctype,
        "field": field,
        "decision": decision,
        "expected_behavior": expected,
        "source": source,
        "confidence": confidence,
        "correct": correct,
        "reason": reason,
        "severity": severity,
        "framework_component": component,
        "root_cause": reason,
        "recommended_framework_fix": fix,
        "retest_result": "PASS" if correct else "NOT RETESTED",
    }


def doctype_scores(result):
    field_decisions = result.get("field_decisions") or []
    dependency_decisions = result.get("dependency_decisions") or []
    recommendation_decisions = result.get("recommendation_decisions") or []
    all_decisions = field_decisions + dependency_decisions + recommendation_decisions
    defaulted = [item for item in field_decisions if item.get("decision") in {"Defaulted", "Context Derived"}]
    questions = [item for item in field_decisions if item.get("mandatory") and item.get("editable")]
    ui = [item.get("ui_component") for item in field_decisions if item.get("editable")]
    return {
        "metadata": 100 if result.get("metadata") == "PASS" and result.get("blueprint") == "PASS" else 0,
        "derivation": percent_correct(defaulted),
        "question": percent_correct(questions),
        "validation": percent_correct(field_decisions + dependency_decisions),
        "ui": percent_correct(ui),
        "overall": percent_correct(all_decisions),
    }


def intelligence_scores(results):
    if not results:
        return {
            "Conversation Intelligence Score": 0,
            "Metadata Accuracy": 0,
            "Derivation Accuracy": 0,
            "Question Accuracy": 0,
            "Validation Accuracy": 0,
            "UI Accuracy": 0,
            "Overall AI Decision Accuracy": 0,
        }
    return {
        "Conversation Intelligence Score": average_score(results, "overall"),
        "Metadata Accuracy": average_score(results, "metadata"),
        "Derivation Accuracy": average_score(results, "derivation"),
        "Question Accuracy": average_score(results, "question"),
        "Validation Accuracy": average_score(results, "validation"),
        "UI Accuracy": average_score(results, "ui"),
        "Overall AI Decision Accuracy": average_score(results, "overall"),
    }


def average_score(results, key):
    values = [(result.get("scores") or {}).get(key, 0) for result in results]
    return int(sum(values) / len(values)) if values else 0


def percent_correct(items):
    items = [item for item in items if item]
    if not items:
        return 100
    return int((sum(1 for item in items if item.get("correct")) / len(items)) * 100)


def ordered_unique(values):
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def component_for_group(group):
    if group == ERP_DEFAULT_GROUP:
        return "Derivation Engine"
    if group == CONTEXT_DERIVED_GROUP:
        return "Derivation Engine"
    if group == ALWAYS_ASK_GROUP:
        return "Conversation Engine"
    return "Conversation Engine"


def humanize(value):
    return str(value or "Field").replace("_", " ").title()
