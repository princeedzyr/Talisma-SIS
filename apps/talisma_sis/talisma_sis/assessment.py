"""US higher-education assessment lifecycle built on ERPNext Education records."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt, getdate, now_datetime, today


RESULT_STATES = "Draft\nFaculty Submitted\nDepartment Approved\nRegistrar Approved\nLocked\nCancelled"


def configure_assessment() -> None:
	create_custom_fields(
		{
			"Assessment Plan Criteria": [
				_field("talisma_weightage", "Weightage", "Percent", insert_after="assessment_criteria", read_only=1, in_list_view=1),
			],
			"Assessment Plan": [
				_field("talisma_course_grade_weightage", "Course Grade Weightage", "Percent", insert_after="maximum_assessment_score", reqd=1, default="100"),
			],
			"Assessment Result": [
				_field("talisma_percentage", "Percentage", "Percent", insert_after="total_score", read_only=1, in_list_view=1, precision="2", allow_on_submit=1),
				_field("talisma_grade_points", "Grade Points", "Float", insert_after="grade", read_only=1, in_list_view=1, precision="2", allow_on_submit=1),
				_field("talisma_result_status", "Status", "Select", RESULT_STATES, "talisma_grade_points", read_only=1, default="Draft", in_list_view=1, allow_on_submit=1),
				_field("talisma_audit_section", "Approval & Audit", "Section Break", insert_after="comment"),
				_field("talisma_faculty_submitted_by", "Faculty Submitted By", "Link", "User", "talisma_audit_section", read_only=1),
				_field("talisma_faculty_submitted_on", "Faculty Submitted On", "Datetime", insert_after="talisma_faculty_submitted_by", read_only=1),
				_field("talisma_audit_column", "", "Column Break", insert_after="talisma_faculty_submitted_on"),
				_field("talisma_department_approved_by", "Department Approved By", "Link", "User", "talisma_audit_column", read_only=1, allow_on_submit=1),
				_field("talisma_department_approved_on", "Department Approved On", "Datetime", insert_after="talisma_department_approved_by", read_only=1, allow_on_submit=1),
				_field("talisma_registrar_approved_by", "Registrar Approved By", "Link", "User", "talisma_department_approved_on", read_only=1, allow_on_submit=1),
				_field("talisma_registrar_approved_on", "Registrar Approved On", "Datetime", insert_after="talisma_registrar_approved_by", read_only=1, allow_on_submit=1),
				_field("talisma_locked_by", "Locked By", "Link", "User", "talisma_registrar_approved_on", read_only=1, allow_on_submit=1),
				_field("talisma_locked_on", "Locked On", "Datetime", insert_after="talisma_locked_by", read_only=1, allow_on_submit=1),
				_field("talisma_change_reason", "Grade Change Reason", "Small Text", insert_after="talisma_locked_on", allow_on_submit=1),
				_field("talisma_grade_change_history", "Grade Change History", "Table", "Talisma Grade Change History", "talisma_change_reason", read_only=1, allow_on_submit=1),
			],
		},
		update=True,
	)
	for doctype, fieldname, prop, value, prop_type in (
		("Assessment Plan", "student_group", "label", "Class Schedule", "Data"),
		("Assessment Plan", "grading_scale", "label", "Grade Scale", "Data"),
		("Assessment Plan", "schedule_date", "label", "Assessment Date", "Data"),
		("Assessment Plan", "from_time", "label", "Start Time", "Data"),
		("Assessment Plan", "to_time", "label", "End Time", "Data"),
		("Assessment Result", "student_group", "label", "Class Schedule", "Data"),
		("Assessment Result", "grading_scale", "label", "Grade Scale", "Data"),
		("Assessment Result", "details", "label", "Assessment Criteria Scores", "Data"),
		("Assessment Result", "details", "allow_on_submit", 1, "Check"),
		("Assessment Result", "total_score", "allow_on_submit", 1, "Check"),
		("Assessment Result", "grade", "allow_on_submit", 1, "Check"),
		("Assessment Result", None, "track_changes", 1, "Check"),
	):
		make_property_setter(doctype, fieldname, prop, value, prop_type)
	_backfill_assessment_fields()
	for doctype in ("Assessment Plan", "Assessment Plan Criteria", "Assessment Result"):
		frappe.clear_cache(doctype=doctype)


def validate_assessment_plan(doc, method=None) -> None:
	if flt(doc.talisma_course_grade_weightage) <= 0 or flt(doc.talisma_course_grade_weightage) > 100:
		frappe.throw(_("Course Grade Weightage must be greater than 0 and no more than 100%."))
	if doc.academic_term and doc.schedule_date:
		term = frappe.db.get_value("Academic Term", doc.academic_term, ["term_start_date", "term_end_date"], as_dict=True)
		if term and not (getdate(term.term_start_date) <= getdate(doc.schedule_date) <= getdate(term.term_end_date)):
			frappe.throw(_("Assessment Date must fall within Academic Term {0}.").format(frappe.bold(doc.academic_term)))
	duplicate = frappe.db.exists(
		"Assessment Plan",
		{
			"name": ("!=", doc.name or ""),
			"course": doc.course,
			"assessment_group": doc.assessment_group,
			"academic_term": doc.academic_term,
			"student_group": doc.student_group,
			"docstatus": ("!=", 2),
		},
	)
	if duplicate:
		frappe.throw(_("Assessment Plan {0} already exists for this Course, Assessment Group, Academic Term, and Class Schedule.").format(frappe.bold(duplicate)))
	configured_weights = {
		row.assessment_criteria: flt(row.weightage)
		for row in frappe.get_all(
			"Course Assessment Criteria",
			filters={"parent": doc.course, "parenttype": "Course"},
			fields=["assessment_criteria", "weightage"],
		)
	}
	for row in doc.assessment_criteria:
		if not flt(row.talisma_weightage):
			row.talisma_weightage = configured_weights.get(row.assessment_criteria, 0)
		if flt(row.talisma_weightage) and flt(doc.maximum_assessment_score):
			row.maximum_score = flt(doc.maximum_assessment_score) * flt(row.talisma_weightage) / 100
	weightage = sum(flt(row.talisma_weightage) for row in doc.assessment_criteria)
	if doc.assessment_criteria and abs(weightage - 100) > 0.01:
		frappe.throw(_("Assessment Criteria Weightage must total 100%; the current total is {0}%.").format(weightage))


def validate_assessment_result(doc, method=None) -> None:
	previous = doc.get_doc_before_save()
	if previous and previous.talisma_result_status == "Locked" and _result_signature(previous) != _result_signature(doc):
		frappe.throw(_("Locked Assessment Results cannot be modified. Unpublish the Gradebook and explicitly unlock the result first."))
	doc.talisma_percentage = (flt(doc.total_score) / flt(doc.maximum_score) * 100) if flt(doc.maximum_score) else 0
	from talisma_sis.academics import _grade_points

	doc.talisma_grade_points = _grade_points(doc.grading_scale, doc.grade) or 0
	if doc.docstatus == 0:
		doc.talisma_result_status = "Draft"


def assessment_result_submitted(doc, method=None) -> None:
	now = now_datetime()
	doc.db_set("talisma_result_status", "Faculty Submitted", update_modified=False)
	doc.db_set("talisma_faculty_submitted_by", frappe.session.user, update_modified=False)
	doc.db_set("talisma_faculty_submitted_on", now, update_modified=False)


def assessment_result_cancelled(doc, method=None) -> None:
	doc.db_set("talisma_result_status", "Cancelled", update_modified=False)
	_cancel_draft_gradebooks(doc)


def capture_grade_change(doc, method=None) -> None:
	previous = doc.get_doc_before_save()
	if not previous or _result_signature(previous) == _result_signature(doc):
		return
	if previous.talisma_result_status == "Locked":
		frappe.throw(_("Locked Assessment Results cannot be changed."))
	if not (doc.talisma_change_reason or "").strip():
		frappe.throw(_("Grade Change Reason is required when changing a submitted result."))
	doc.append(
		"talisma_grade_change_history",
		{
			"previous_grade": previous.grade,
			"new_grade": doc.grade,
			"previous_score": previous.total_score,
			"new_score": doc.total_score,
			"changed_by": frappe.session.user,
			"changed_on": now_datetime(),
			"reason": doc.talisma_change_reason,
		},
	)
	doc.talisma_result_status = "Faculty Submitted"
	doc.talisma_department_approved_by = None
	doc.talisma_department_approved_on = None
	doc.talisma_registrar_approved_by = None
	doc.talisma_registrar_approved_on = None
	doc.talisma_change_reason = None


@frappe.whitelist()
def transition_assessment_result(name: str, action: str, comment: str | None = None) -> dict:
	doc = frappe.get_doc("Assessment Result", name)
	doc.check_permission("write")
	transitions = {
		"approve_department": ("Faculty Submitted", "Department Approved", "talisma_department_approved_by", "talisma_department_approved_on"),
		"approve_registrar": ("Department Approved", "Registrar Approved", "talisma_registrar_approved_by", "talisma_registrar_approved_on"),
		"lock": ("Registrar Approved", "Locked", "talisma_locked_by", "talisma_locked_on"),
		"unlock": ("Locked", "Registrar Approved", None, None),
	}
	if action not in transitions:
		frappe.throw(_("Unsupported Assessment Result action."))
	expected, target, user_field, date_field = transitions[action]
	if doc.docstatus != 1 or doc.talisma_result_status != expected:
		frappe.throw(_("Assessment Result must be {0} before it can become {1}.").format(expected, target))
	if action != "approve_department" and not ("System Manager" in frappe.get_roles() or frappe.session.user == "Administrator"):
		frappe.throw(_("Only an authorized academic administrator can perform this approval."), frappe.PermissionError)
	if action == "unlock":
		if not (comment or "").strip():
			frappe.throw(_("A reason is required to unlock an official result."))
		published = frappe.db.exists(
			"Assessment Gradebook",
			{"student": doc.student, "course": doc.course, "academic_term": doc.academic_term, "student_group": doc.student_group, "docstatus": 1},
		)
		if published:
			frappe.throw(_("Cancel published Gradebook {0} before unlocking this result.").format(frappe.bold(published)))
		values = {"talisma_result_status": target}
	else:
		values = {"talisma_result_status": target, user_field: frappe.session.user, date_field: now_datetime()}
	frappe.db.set_value("Assessment Result", name, values)
	doc.add_comment("Workflow", text=comment or _("Assessment Result moved to {0}.").format(target))
	if target == "Locked":
		refresh_gradebook_for_result(frappe.get_doc("Assessment Result", name))
	frappe.db.commit()
	return {"name": name, "status": target}


def refresh_gradebook_for_result(result) -> str | None:
	if result.talisma_result_status != "Locked":
		return None
	filters = {
		"student": result.student,
		"course": result.course,
		"academic_term": result.academic_term,
		"student_group": result.student_group,
		"docstatus": ("!=", 2),
	}
	name = frappe.db.get_value("Assessment Gradebook", filters, "name")
	gradebook = frappe.get_doc("Assessment Gradebook", name) if name else frappe.new_doc("Assessment Gradebook")
	if not name:
		gradebook.update(
			{
				"student": result.student,
				"academic_year": result.academic_year,
				"academic_term": result.academic_term,
				"program": result.program,
				"course": result.course,
				"student_group": result.student_group,
				"grading_scale": result.grading_scale,
			}
		)
	gradebook.save(ignore_permissions=True)
	return gradebook.name


def rebuild_assessment_gradebooks() -> dict:
	"""Idempotently create or refresh Gradebooks for migrated Locked results."""
	gradebooks = set()
	for name in frappe.get_all(
		"Assessment Result",
		filters={"docstatus": 1, "talisma_result_status": "Locked"},
		pluck="name",
	):
		gradebook = refresh_gradebook_for_result(frappe.get_doc("Assessment Result", name))
		if gradebook:
			gradebooks.add(gradebook)
	frappe.db.commit()
	return {"gradebooks": len(gradebooks), "names": sorted(gradebooks)}


def populate_gradebook(doc) -> None:
	from education.education import validate_student_belongs_to_group

	validate_student_belongs_to_group(doc.student, doc.student_group)
	duplicate = frappe.db.exists(
		"Assessment Gradebook",
		{
			"name": ("!=", doc.name or ""),
			"student": doc.student,
			"course": doc.course,
			"academic_term": doc.academic_term,
			"student_group": doc.student_group,
			"docstatus": ("!=", 2),
		},
	)
	if duplicate:
		frappe.throw(_("Assessment Gradebook {0} already exists for this student, course, term, and class schedule.").format(frappe.bold(duplicate)))
	plans = frappe.get_all(
		"Assessment Plan",
		filters={"course": doc.course, "academic_term": doc.academic_term, "student_group": doc.student_group, "docstatus": 1},
		fields=["name", "assessment_name", "assessment_group", "talisma_course_grade_weightage"],
		order_by="schedule_date, from_time",
	)
	doc.set("assessment_summary", [])
	missing = []
	for plan in plans:
		result = frappe.db.get_value(
			"Assessment Result",
			{"assessment_plan": plan.name, "student": doc.student, "docstatus": 1},
			["name", "total_score", "maximum_score", "talisma_percentage", "grade", "talisma_result_status"],
			as_dict=True,
		)
		if not result or result.talisma_result_status != "Locked":
			missing.append(plan.assessment_name or plan.name)
			continue
		weight = flt(plan.talisma_course_grade_weightage)
		percentage = flt(result.talisma_percentage)
		doc.append(
			"assessment_summary",
			{
				"assessment_plan": plan.name,
				"assessment_result": result.name,
				"assessment": plan.assessment_name or plan.assessment_group,
				"weightage": weight,
				"student_score": percentage,
				"weighted_score": percentage * weight / 100,
			},
		)
	if missing and (doc.docstatus == 1 or doc.flags.get("publishing")):
		frappe.throw(_("These assessments do not yet have Locked results: {0}").format(", ".join(missing)))
	total_weight = sum(flt(row.weightage) for row in doc.assessment_summary)
	doc.final_score = sum(flt(row.weighted_score) for row in doc.assessment_summary)
	doc.final_percentage = doc.final_score
	if (doc.docstatus == 1 or doc.flags.get("publishing")) and abs(total_weight - 100) > 0.01:
		frappe.throw(_("Assessment Gradebook weightage must total 100%; the current total is {0}%.").format(total_weight))
	if doc.grading_scale:
		from education.education.api import get_grade
		from talisma_sis.academics import _grade_points

		doc.letter_grade = get_grade(doc.grading_scale, doc.final_percentage)
		doc.grade_points = _grade_points(doc.grading_scale, doc.letter_grade) or 0


def publish_gradebook(doc) -> None:
	doc.status = "Published"
	doc.transcript_status = "Ready"
	doc.published_by = frappe.session.user
	doc.published_on = now_datetime()
	enrollment = frappe.db.get_value(
		"Course Enrollment",
		{"student": doc.student, "course": doc.course},
		"name",
		order_by="talisma_attempt_number desc, enrollment_date desc, creation desc",
	)
	if not enrollment:
		frappe.throw(_("No Course Enrollment exists for {0} in {1}.").format(frappe.bold(doc.student), frappe.bold(doc.course)))
	doc.course_enrollment = enrollment
	frappe.db.set_value(
		"Course Enrollment",
		enrollment,
		{
			"talisma_grade_earned": doc.letter_grade,
			"talisma_grade_points": doc.grade_points,
			"talisma_completion_status": "Failed" if flt(doc.grade_points) == 0 else "Completed",
			"talisma_status_date": today(),
		},
		update_modified=False,
	)
	from talisma_sis.academics import refresh_academic_standing

	refresh_academic_standing(doc.student)


@frappe.whitelist()
def publish_gradebook_action(name: str) -> dict:
	doc = frappe.get_doc("Assessment Gradebook", name)
	doc.check_permission("submit")
	if doc.docstatus != 0:
		frappe.throw(_("Only a Draft Assessment Gradebook can be published."))
	doc.submit()
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status, "transcript_status": doc.transcript_status}


def cancel_gradebook(doc) -> None:
	doc.db_set("status", "Cancelled", update_modified=False)
	doc.db_set("transcript_status", "Not Ready", update_modified=False)
	if doc.course_enrollment:
		frappe.db.set_value(
			"Course Enrollment",
			doc.course_enrollment,
			{"talisma_grade_earned": None, "talisma_grade_points": None, "talisma_completion_status": "In Progress"},
			update_modified=False,
		)
		from talisma_sis.academics import refresh_academic_standing

		refresh_academic_standing(doc.student)


@frappe.whitelist()
def mark_transcript_posted(name: str) -> dict:
	doc = frappe.get_doc("Assessment Gradebook", name)
	doc.check_permission("write")
	if doc.docstatus != 1 or doc.status != "Published" or doc.transcript_status != "Ready":
		frappe.throw(_("Only a Published Gradebook with transcript status Ready can be posted."))
	if not ("System Manager" in frappe.get_roles() or frappe.session.user == "Administrator"):
		frappe.throw(_("Only an authorized registrar can post transcript grades."), frappe.PermissionError)
	frappe.db.set_value("Assessment Gradebook", name, "transcript_status", "Posted")
	doc.add_comment("Info", text=_("Official course grade marked as posted to the transcript."))
	frappe.db.commit()
	return {"name": name, "transcript_status": "Posted"}


def _cancel_draft_gradebooks(result) -> None:
	for name in frappe.get_all(
		"Assessment Gradebook",
		filters={"student": result.student, "course": result.course, "academic_term": result.academic_term, "student_group": result.student_group, "docstatus": 0},
		pluck="name",
	):
		frappe.delete_doc("Assessment Gradebook", name, ignore_permissions=True)


def _backfill_assessment_fields() -> None:
	for plan in frappe.get_all("Assessment Plan", fields=["name", "maximum_assessment_score", "talisma_course_grade_weightage"]):
		if not flt(plan.talisma_course_grade_weightage):
			frappe.db.set_value("Assessment Plan", plan.name, "talisma_course_grade_weightage", 100, update_modified=False)
		for row in frappe.get_all("Assessment Plan Criteria", filters={"parent": plan.name}, fields=["name", "maximum_score", "talisma_weightage"]):
			if not flt(row.talisma_weightage) and flt(plan.maximum_assessment_score):
				frappe.db.set_value("Assessment Plan Criteria", row.name, "talisma_weightage", flt(row.maximum_score) / flt(plan.maximum_assessment_score) * 100, update_modified=False)
	for result in frappe.get_all("Assessment Result", filters={"docstatus": 1}, fields=["name", "owner", "modified", "total_score", "maximum_score", "grade", "grading_scale", "talisma_result_status"]):
		from talisma_sis.academics import _grade_points

		values = {
			"talisma_percentage": flt(result.total_score) / flt(result.maximum_score) * 100 if flt(result.maximum_score) else 0,
			"talisma_grade_points": _grade_points(result.grading_scale, result.grade) or 0,
		}
		if result.talisma_result_status in (None, "", "Draft"):
			values.update(
				{
					"talisma_result_status": "Locked",
					"talisma_faculty_submitted_by": result.owner,
					"talisma_faculty_submitted_on": result.modified,
					"talisma_locked_by": "Administrator",
					"talisma_locked_on": result.modified,
				}
			)
		frappe.db.set_value("Assessment Result", result.name, values, update_modified=False)


def _result_signature(doc) -> tuple:
	return (
		flt(doc.total_score),
		doc.grade,
		tuple((row.assessment_criteria, flt(row.score)) for row in doc.details),
	)


def _field(fieldname, label, fieldtype, options="", insert_after="", **values):
	return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "options": options, "insert_after": insert_after, **values}
