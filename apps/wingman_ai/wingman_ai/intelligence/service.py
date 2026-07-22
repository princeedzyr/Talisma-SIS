from wingman_ai.intelligence.confidence import ConfidenceCalculator
from wingman_ai.intelligence.impact import BusinessImpactEngine
from wingman_ai.intelligence.insights import InsightEngine
from wingman_ai.intelligence.readiness import ExecutionReadinessEngine
from wingman_ai.intelligence.recommendations import RecommendationEngine
from wingman_ai.intelligence.risk import RiskAssessmentEngine
from wingman_ai.intelligence.utils import (
    dependencies,
    docname_from,
    doctype_from,
    operation_from,
    utc_timestamp,
    validation_issues,
)


class WingmanIntelligenceService:
    def __init__(
        self,
        confidence_calculator=None,
        recommendation_engine=None,
        insight_engine=None,
        risk_engine=None,
        readiness_engine=None,
        impact_engine=None,
    ):
        self.readiness_engine = readiness_engine or ExecutionReadinessEngine()
        self.confidence_calculator = confidence_calculator or ConfidenceCalculator()
        self.recommendation_engine = recommendation_engine or RecommendationEngine()
        self.insight_engine = insight_engine or InsightEngine()
        self.risk_engine = risk_engine or RiskAssessmentEngine()
        self.impact_engine = impact_engine or BusinessImpactEngine()

    def build(self, payload=None, intent=None, context=None, user=None):
        payload = payload or {}
        context = context or {}
        readiness = self.readiness_engine.assess(payload)
        confidence = self.confidence_calculator.calculate(payload, intent=intent, readiness=readiness)
        recommendations = self.recommendation_engine.recommend(payload, context=context)
        impact = self.impact_engine.summarize(payload)
        risk = self.risk_engine.assess(payload, readiness=readiness)

        return {
            "version": "1.0",
            "administrator_view": self.administrator_view(
                payload,
                readiness=readiness,
                confidence=confidence,
                recommendations=recommendations,
                impact=impact,
                risk=risk,
            ),
            "operation_confidence": {
                "score": confidence["score"],
                "meter": confidence["meter"],
                "label": confidence["label"],
            },
            "confidence_breakdown": confidence["breakdown"],
            "execution_readiness": readiness,
            "validation_summary": self.validation_summary(payload),
            "dependency_summary": self.dependency_summary(payload),
            "business_recommendations": recommendations,
            "ai_insights": self.insight_engine.build(payload, context=context),
            "business_impact": impact,
            "risk_assessment": risk,
            "recommended_next_actions": [item["action"] for item in recommendations if item.get("action")],
            "operation_metadata": self.operation_metadata(payload, intent=intent, context=context, user=user),
            "performance_metrics": self.performance_metrics(payload),
        }

    def administrator_view(self, payload, readiness, confidence, recommendations, impact, risk):
        data = (payload or {}).get("data") or {}
        student_360 = data.get("student_360") or {}
        record_summary = data.get("record_summary") or {}
        student_records = (student_360.get("student_records") or {}).get("summary") or {}
        enrollment = (student_360.get("enrollment") or {}).get("current") or {}
        finance = student_360.get("finance") or {}
        finance_summary = finance.get("summary") or {}

        if student_360:
            student_name = student_360.get("student_name") or record_summary.get("title") or "Student"
            focused_view = focused_student_administrator_view(
                data.get("response_mode"), student_name, student_records, enrollment, student_360,
                finance_summary, readiness, confidence,
            )
            if focused_view:
                return focused_view
            summary = compact_rows(
                ("Student", student_name),
                ("Status", student_records.get("record_status") or record_summary.get("status")),
                ("Program", enrollment.get("program_name") or student_records.get("primary_program")),
                ("Academic Level", student_records.get("academic_level")),
                ("Current Term", enrollment.get("academic_term")),
                ("Academic Standing", student_records.get("standing")),
                ("Campus", enrollment.get("campus_name")),
                ("Outstanding Balance", format_money(finance_summary.get("outstanding_balance"), finance_summary.get("currency"))),
            )
            attention = student_attention_items(student_records, enrollment, student_360, finance_summary)
            return {
                "title": "Student Overview",
                "status": "Information Ready",
                "status_tone": readiness.get("indicator") or "green",
                "confidence_score": confidence.get("score", 0),
                "confidence_label": friendly_confidence(confidence.get("score", 0)),
                "message": f"Wingman found {student_name} and prepared the information available to your role.",
                "understanding": understanding_message(confidence.get("score", 0)),
                "summary": summary,
                "attention_title": "Needs Attention",
                "attention": attention or ["No urgent items were identified from the available student information."],
                "actions_title": "Suggested Actions",
                "actions": student_administrator_actions(student_name),
                "note": "Information is limited to records your OneCampus role is allowed to view.",
            }

        attention = []
        if risk.get("level") not in (None, "Low"):
            attention.extend(risk.get("reasons") or [])
        if impact.get("level") not in (None, "Low"):
            attention.extend(impact.get("items") or [])
        return {
            "title": "Response Summary",
            "status": friendly_readiness(readiness.get("state")),
            "status_tone": readiness.get("indicator") or "green",
            "confidence_score": confidence.get("score", 0),
            "confidence_label": friendly_confidence(confidence.get("score", 0)),
            "message": friendly_readiness_reason(readiness.get("reason")),
            "understanding": understanding_message(confidence.get("score", 0)),
            "summary": [],
            "attention_title": "Needs Attention",
            "attention": attention,
            "actions_title": "Suggested Actions",
            "actions": [item.get("action") for item in recommendations if item.get("action")],
            "note": "Wingman follows your OneCampus permissions and asks for confirmation before protected changes.",
        }

    def validation_summary(self, payload):
        data = (payload or {}).get("data") or {}
        result = data.get("result") or {}
        plan = result.get("operation_plan") or {}
        blueprint = plan.get("blueprint_summary") or {}
        issues = validation_issues(payload)
        defaults = result.get("defaults_applied") or []

        rows = []
        if blueprint:
            rows.append({"label": "Mandatory Fields", "value": str(blueprint.get("required_field_count", 0))})
            rows.append({"label": "Conditional Mandatory Fields", "value": str(blueprint.get("conditional_required_field_count", 0))})
        if result.get("missing_fields"):
            rows.append({"label": "Missing Fields", "value": ", ".join(result.get("missing_fields") or [])})
        rows.append({"label": "Dependency Status", "value": "Pending" if dependencies(payload) else "Clear"})
        rows.append({"label": "ERP Validation Status", "value": "Needs Attention" if issues else "Passed"})
        if blueprint:
            rows.append({"label": "Workflow Status", "value": "Configured" if blueprint.get("has_workflow") else "No active workflow detected"})
            rows.append({"label": "Permission Status", "value": "Configured" if blueprint.get("has_permissions") else "Checked by Talisma OneCampus"})
        if defaults:
            rows.append({"label": "System Defaults Applied", "value": str(len(defaults))})
        return rows

    def dependency_summary(self, payload):
        items = []
        for item in dependencies(payload):
            items.append(
                {
                    "fieldname": item.get("fieldname"),
                    "label": item.get("label") or item.get("fieldname"),
                    "target_doctype": item.get("target_doctype"),
                    "value": item.get("value"),
                    "status": "Ready to create" if item.get("ready") else "Waiting",
                }
            )
        if not items:
            return [{"label": "Dependencies", "status": "Clear", "detail": "No missing linked records were detected."}]
        return items

    def operation_metadata(self, payload, intent=None, context=None, user=None):
        context = context or {}
        context_object = context.get("object") or {}
        return {
            "current_operation": operation_from(payload, intent=intent),
            "target_doctype": doctype_from(payload, context=context) or "Not applicable",
            "target_record": docname_from(payload, context=context) or "Not applicable",
            "conversation_session_id": (payload or {}).get("conversation_id") or context.get("conversation_id"),
            "execution_mode": "Review Required" if (payload or {}).get("requires_confirmation") else "Read Only or Assisted",
            "current_workflow_state": context_object.get("workflow_state") or "Not available",
            "current_user": user or (payload or {}).get("user") or "Current User",
            "current_company": context_object.get("company") or "Not available",
            "execution_timestamp": utc_timestamp(),
        }

    def performance_metrics(self, payload):
        data = (payload or {}).get("data") or {}
        result = data.get("result") or {}
        collected = result.get("data") or result.get("changes") or {}
        return {
            "conversation_duration": "Not measured",
            "fields_collected": len(collected) if isinstance(collected, dict) else 0,
            "dependencies_resolved": len(dependencies(payload)),
            "validation_attempts": 1 if result.get("preflight") or validation_issues(payload) else 0,
            "execution_time": "Not measured",
        }


_SERVICE = None


def get_wingman_intelligence_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = WingmanIntelligenceService()
    return _SERVICE


def compact_rows(*items):
    return [{"label": label, "value": value} for label, value in items if value not in (None, "")]


def focused_student_administrator_view(mode, student_name, student_records, enrollment, student_360, finance_summary, readiness, confidence):
    courses = (student_360.get("course_registration") or {}).get("records") or []
    common = {
        "status": "Information Ready",
        "status_tone": readiness.get("indicator") or "green",
        "confidence_score": confidence.get("score", 0),
        "confidence_label": friendly_confidence(confidence.get("score", 0)),
        "understanding": understanding_message(confidence.get("score", 0)),
        "note": "Information is limited to records your OneCampus role is allowed to view.",
    }

    if mode == "student_enrollment_read":
        return {
            **common,
            "title": "Enrollment Summary",
            "message": f"Wingman found the current enrollment information for {student_name}.",
            "summary": compact_rows(
                ("Student", student_name),
                ("Program", enrollment.get("program_name")),
                ("Enrollment Status", enrollment.get("enrollment_status") or "Active"),
                ("Academic Year", enrollment.get("academic_year")),
                ("Academic Term", enrollment.get("academic_term")),
                ("Campus", enrollment.get("campus_name")),
                ("Expected Start", enrollment.get("expected_start_date")),
                ("Registered Courses", len(courses)),
            ),
            "attention_title": "Enrollment Notes",
            "attention": [] if enrollment else ["No current program enrollment was found."],
            "actions_title": "Suggested Actions",
            "actions": [
                administrator_action("View Courses & Grades", f"summarize courses and grades for student {student_name}"),
                administrator_action("Open Student Profile", f"open student {student_name}"),
            ],
        }

    if mode == "student_courses_read":
        in_progress = sum((course.get("completion_status") or "").lower() == "in progress" for course in courses)
        graded = sum(course.get("grade") not in (None, "") for course in courses)
        total_credits = sum(float(course.get("credit_hours") or 0) for course in courses)
        return {
            **common,
            "title": "Courses & Grades Summary",
            "message": f"Wingman found {len(courses)} registered course{'s' if len(courses) != 1 else ''} for {student_name}.",
            "summary": compact_rows(
                ("Student", student_name),
                ("Program", enrollment.get("program_name")),
                ("Academic Term", enrollment.get("academic_term")),
                ("Registered Courses", len(courses)),
                ("Total Credits", f"{total_credits:g}"),
                ("Courses In Progress", in_progress),
                ("Grades Available", graded),
            ),
            "attention_title": "Academic Notes",
            "attention": ["No course registrations were found."] if not courses else [],
            "actions_title": "Suggested Actions",
            "actions": [
                administrator_action("Review Enrollment", f"show enrollment for student {student_name}"),
                administrator_action("Open Student Profile", f"open student {student_name}"),
            ],
        }

    if mode == "student_finance_read":
        balance = float(finance_summary.get("outstanding_balance") or 0)
        currency = finance_summary.get("currency")
        return {
            **common,
            "title": "Account Balance Summary",
            "message": f"Wingman prepared the student account summary for {student_name}.",
            "summary": compact_rows(
                ("Student", student_name),
                ("Outstanding Balance", format_money(balance, currency)),
                ("Account Status", "Balance Due" if balance > 0 else "Paid in Full"),
                ("Total Charges", format_money(finance_summary.get("total_charges"), currency)),
                ("Total Payments", format_money(finance_summary.get("total_payments"), currency)),
                ("Last Payment", finance_summary.get("last_payment_date")),
                ("Next Due Date", finance_summary.get("next_due_date")),
            ),
            "attention_title": "Account Notes",
            "attention": [f"An outstanding balance of {format_money(balance, currency)} needs review."] if balance > 0 else ["No outstanding balance is currently due."],
            "actions_title": "Suggested Actions",
            "actions": [
                administrator_action("Review Enrollment", f"show enrollment for student {student_name}"),
                administrator_action("Open Student Profile", f"open student {student_name}"),
            ],
        }

    return None


def format_money(value, currency):
    if value in (None, ""):
        return None
    try:
        amount = f"{float(value):,.2f}"
    except (TypeError, ValueError):
        amount = str(value)
    if str(currency or "").upper() == "USD":
        return f"${amount}"
    return f"{currency or ''} {amount}".strip()


def understanding_message(score):
    if score >= 85:
        return "Wingman understood the request and found a strong match."
    if score >= 65:
        return "Wingman found a likely match. Review the details before continuing."
    return "Wingman may need more information to identify the correct record."


def friendly_confidence(score):
    if score >= 85:
        return "Strong match"
    if score >= 65:
        return "Good match"
    return "Review match"


def student_attention_items(student_records, enrollment, student_360, finance_summary):
    items = []
    active_holds = int(student_records.get("active_holds") or 0)
    if active_holds:
        items.append(f"This student has {active_holds} active administrative hold{'s' if active_holds != 1 else ''}.")
    if student_records.get("privacy_restriction"):
        items.append("A privacy restriction is active. Handle student information according to institutional policy.")
    balance = finance_summary.get("outstanding_balance")
    if balance not in (None, "") and float(balance or 0) > 0:
        due = finance_summary.get("next_due_date")
        message = f"Outstanding balance: {format_money(balance, finance_summary.get('currency'))}."
        if due:
            message = f"{message[:-1]} due by {due}."
        items.append(message)
    courses = (student_360.get("course_registration") or {}).get("records") or []
    if student_records.get("record_status") == "Graduated" and any((course.get("completion_status") or "").lower() == "in progress" for course in courses):
        items.append("The student is marked Graduated but still has courses shown as In Progress. Review the record for consistency.")
    if not enrollment:
        items.append("No current program enrollment was found.")
    return items


def student_administrator_actions(student_name):
    return [
        administrator_action("Open Student Profile", f"open student {student_name}"),
        administrator_action("Review Enrollment", f"show enrollment for student {student_name}"),
        administrator_action("Review Account Balance", f"show account balance for student {student_name}"),
    ]


def administrator_action(label, message):
    return {
        "type": "send_message",
        "label": label,
        "payload": {"message": message},
        "requires_confirmation": False,
        "auto_execute": False,
        "enabled": True,
    }


def friendly_readiness(state):
    return {
        "Response Ready": "Information Ready",
        "Ready to Execute": "Ready for Your Review",
        "Action Available": "Next Step Available",
        "Waiting for User Input": "More Information Needed",
        "Waiting for Dependency": "Setup Needed",
        "Validation Failed": "Needs Attention",
        "Not Ready": "Could Not Complete",
    }.get(state, state or "Information Ready")


def friendly_readiness_reason(reason):
    replacements = {
        "Wingman generated an informational response.": "Wingman prepared the information you requested.",
        "The operation is ready for user confirmation.": "Review the proposed change before confirming it.",
        "Wingman prepared a safe next action.": "A suggested next step is available below.",
        "Wingman needs one or more details from the user.": "Wingman needs a little more information before continuing.",
        "A linked record or setup dependency must be resolved.": "A required OneCampus setup item must be completed first.",
        "Talisma OneCampus validation or permission checks need attention.": "The request needs attention before it can continue.",
    }
    return replacements.get(reason, reason or "Wingman prepared the information you requested.")
