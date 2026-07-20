"""Upgrade-safe admissions workflow extensions for the isolated demo site."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, flt, getdate, now_datetime, today


DEMO_SITE = "demo.talisma.local"
INTAKE_STATUSES = ("Draft", "Planned", "Open", "Closed", "Cancelled", "Archived")
PROGRAM_STATUSES = ("Open", "Closed", "Full", "Cancelled")
APPLICATION_STAGES = (
	"Draft", "Submitted", "Under Review", "Decision Pending", "Approved",
	"Waitlisted", "Rejected", "Admitted", "Withdrawn",
)
ELIGIBILITY_STATUSES = ("Pending", "Eligible", "Conditionally Eligible", "Ineligible")
FEE_STATUSES = ("Not Required", "Pending", "Paid", "Waived", "Refunded")


def configure_admission_intake() -> None:
	"""Extend the existing Education intake and program-row DocTypes in place."""
	create_custom_fields(
		{
			"Student Admission": [
				_field("talisma_academic_term", "Academic Term", "Link", "academic_year", options="Academic Term", reqd=1),
				_field("talisma_general_column_2", "", "Column Break", "talisma_academic_term"),
				_field("talisma_campus", "Campus", "Link", "talisma_general_column_2", options="Talisma Campus"),
				_field(
					"talisma_status", "Status", "Select", "talisma_campus",
					options="\n" + "\n".join(INTAKE_STATUSES), default="Draft", reqd=1,
				),
				_field("talisma_timeline_section", "Admission Timeline", "Section Break", "talisma_status"),
				_field("talisma_timeline_column_2", "", "Column Break", "admission_end_date"),
				_field("talisma_decision_release_date", "Decision Release Date", "Date", "talisma_timeline_column_2", reqd=1),
				_field(
					"talisma_enrollment_confirmation_deadline",
					"Enrollment Confirmation Deadline",
					"Date",
					"talisma_decision_release_date",
					reqd=1,
				),
			],
			"Student Admission Program": [
				_field("talisma_degree", "Degree", "Link", "program", options="Degree", read_only=1, in_list_view=1),
				_field(
					"talisma_academic_unit", "Academic Unit", "Link", "talisma_degree",
					options="Talisma Academic Unit", read_only=1, in_list_view=1,
				),
				_field("talisma_intake_capacity", "Intake Capacity", "Int", "application_fee", reqd=1, in_list_view=1),
				_field("talisma_seats_filled", "Seats Filled", "Int", "talisma_intake_capacity", read_only=1, in_list_view=1),
				_field("talisma_seats_available", "Seats Available", "Int", "talisma_seats_filled", read_only=1, in_list_view=1),
				_field(
					"talisma_status", "Status", "Select", "talisma_seats_available",
					options="\n" + "\n".join(PROGRAM_STATUSES), default="Open", reqd=1, in_list_view=1,
				),
				_field("talisma_eligibility_section", "Program Eligibility", "Section Break", "talisma_status"),
				_field("talisma_minimum_gpa", "Minimum GPA", "Float", "talisma_eligibility_section", precision=2),
				_field("talisma_previous_qualification", "Previous Qualification", "Data", "talisma_minimum_gpa"),
				_field("talisma_minimum_credits", "Minimum Credits", "Float", "talisma_previous_qualification", precision=2),
				_field("talisma_eligibility_column_2", "", "Column Break", "talisma_minimum_credits"),
				_field(
					"talisma_english_language_requirement", "English Language Requirement", "Data",
					"talisma_eligibility_column_2",
				),
				_field("talisma_entrance_exam_required", "Entrance Examination Required", "Check", "talisma_english_language_requirement"),
				_field(
					"talisma_minimum_entrance_exam_score", "Minimum Entrance Exam Score", "Float",
					"talisma_entrance_exam_required", depends_on="talisma_entrance_exam_required",
				),
				_field("talisma_work_experience_required", "Work Experience Required", "Check", "talisma_minimum_entrance_exam_score"),
				_field(
					"talisma_minimum_work_experience", "Minimum Work Experience (Years)", "Float",
					"talisma_work_experience_required", depends_on="talisma_work_experience_required", precision=1,
				),
			],
			"Student Applicant": [
				_field("talisma_degree", "Degree", "Link", "program", options="Degree", read_only=1),
				_field(
					"talisma_academic_unit", "Academic Unit", "Link", "talisma_degree",
					options="Talisma Academic Unit", read_only=1,
				),
				_field("talisma_application_fee", "Application Fee", "Currency", "talisma_academic_unit", read_only=1),
				_field(
					"talisma_applicant_classification_section", "Applicant Classification", "Section Break",
					"talisma_application_fee",
				),
				_field(
					"talisma_applicant_classification_column_2", "", "Column Break",
					"talisma_applicant_classification_section",
				),
				_field(
					"talisma_admin_override_section", "Administrative Override", "Section Break", "paid",
					collapsible=1, collapsible_depends_on="eval:doc.talisma_capacity_override",
				),
				_field(
					"talisma_capacity_override", "Override Intake Capacity", "Check", "talisma_admin_override_section",
					description="Restricted administrative override for an otherwise full intake program.",
				),
				_field("talisma_workflow_section", "Application Workflow", "Section Break", "talisma_capacity_override"),
				_field(
					"talisma_application_stage", "Application Stage", "Select", "talisma_workflow_section",
					options="\n" + "\n".join(APPLICATION_STAGES), default="Draft", reqd=1,
					read_only=1, in_list_view=1,
				),
				_field("talisma_last_transition_on", "Last Transition On", "Datetime", "talisma_application_stage", read_only=1),
				_field("talisma_workflow_column_2", "", "Column Break", "talisma_last_transition_on"),
				_field(
					"talisma_last_transition_by", "Last Transition By", "Link", "talisma_workflow_column_2",
					options="User", read_only=1,
				),
				_field("talisma_eligibility_section", "Eligibility Review", "Section Break", "talisma_last_transition_by"),
				_field(
					"talisma_eligibility_status", "Eligibility Status", "Select", "talisma_eligibility_section",
					options="\n" + "\n".join(ELIGIBILITY_STATUSES), default="Pending", reqd=1, read_only=1,
				),
				_field("talisma_eligibility_notes", "Eligibility Notes", "Small Text", "talisma_eligibility_status", read_only=1),
				_field("talisma_eligibility_column_2", "", "Column Break", "talisma_eligibility_notes"),
				_field(
					"talisma_eligibility_reviewed_by", "Reviewed By", "Link", "talisma_eligibility_column_2",
					options="User", read_only=1,
				),
				_field("talisma_eligibility_reviewed_on", "Reviewed On", "Datetime", "talisma_eligibility_reviewed_by", read_only=1),
				_field("talisma_fee_section", "Application Fee", "Section Break", "talisma_eligibility_reviewed_on"),
				_field(
					"talisma_application_fee_status", "Fee Status", "Select", "talisma_fee_section",
					options="\n" + "\n".join(FEE_STATUSES), default="Pending", reqd=1, read_only=1,
				),
				_field("talisma_payment_reference", "Payment Reference", "Data", "talisma_application_fee_status", read_only=1),
				_field("talisma_decision_audit_section", "Decision Audit", "Section Break", "talisma_payment_reference"),
				_field(
					"talisma_decision_by", "Decision By", "Link", "talisma_decision_audit_section",
					options="User", read_only=1,
				),
				_field("talisma_decision_reason", "Decision Reason", "Small Text", "talisma_decision_by", read_only=1),
				_field("talisma_decision_column_3", "", "Column Break", "talisma_decision_reason"),
				_field("talisma_admission_conditions", "Admission Conditions", "Small Text", "talisma_decision_column_3", read_only=1),
				_field("talisma_transfer_audit_section", "Application Transfer", "Section Break", "talisma_admission_conditions", collapsible=1),
				_field("talisma_transfer_reason", "Latest Transfer Reason", "Small Text", "talisma_transfer_audit_section", read_only=1),
				_field("talisma_transfer_column_2", "", "Column Break", "talisma_transfer_reason"),
				_field("talisma_transferred_by", "Transferred By", "Link", "talisma_transfer_column_2", options="User", read_only=1),
				_field("talisma_transferred_on", "Transferred On", "Datetime", "talisma_transferred_by", read_only=1),
			],
		},
		update=True,
	)

	for fieldname, property_name, value, property_type in (
		("title", "label", "Admission Intake Name", "Data"),
		("title", "reqd", 1, "Check"),
		("admission_start_date", "label", "Application Start Date", "Data"),
		("admission_start_date", "reqd", 1, "Check"),
		("admission_end_date", "label", "Application End Date", "Data"),
		("admission_end_date", "reqd", 1, "Check"),
		("route", "hidden", 1, "Check"),
		("published", "hidden", 1, "Check"),
		("enable_admission_application", "hidden", 1, "Check"),
		("section_break_5", "label", "Programs", "Data"),
		("program_details", "label", "Programs", "Data"),
		("introduction", "hidden", 1, "Check"),
	):
		make_property_setter("Student Admission", fieldname, property_name, value, property_type)

	for fieldname, property_name, value, property_type in (
		("program", "reqd", 1, "Check"),
		("min_age", "label", "Minimum Age", "Data"),
		("max_age", "label", "Maximum Age", "Data"),
		("description", "hidden", 1, "Check"),
		("applicant_naming_series", "hidden", 1, "Check"),
	):
		make_property_setter("Student Admission Program", fieldname, property_name, value, property_type)

	make_property_setter("Student Applicant", "student_admission", "label", "Admission Intake", "Data")
	make_property_setter("Student Applicant", "application_status", "hidden", 1, "Check")
	for fieldname in ("academic_year", "academic_term"):
		make_property_setter("Student Applicant", fieldname, "read_only", 1, "Check")
	for fieldname in ("talisma_intake_summary_section", "talisma_intake_summary_html"):
		custom_field = frappe.db.exists("Custom Field", {"dt": "Student Applicant", "fieldname": fieldname})
		if custom_field:
			frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True)
	for doctype in ("Talisma Academic Unit", "Talisma Campus"):
		make_property_setter(doctype, None, "show_title_field_in_link", 1, "Check", for_doctype=True)
	_set_admission_intake_field_order()
	_backfill_student_applications()
	_backfill_admission_intakes()
	frappe.clear_cache(doctype="Student Admission")
	frappe.clear_cache(doctype="Student Admission Program")
	frappe.clear_cache(doctype="Student Applicant")


def _field(fieldname: str, label: str, fieldtype: str, insert_after: str, **values) -> dict:
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"insert_after": insert_after,
		"translatable": 0,
		**values,
	}


def _set_admission_intake_field_order() -> None:
	order = [
		"title", "academic_year", "talisma_academic_term", "talisma_general_column_2",
		"talisma_campus", "talisma_status", "talisma_timeline_section",
		"admission_start_date", "admission_end_date", "talisma_timeline_column_2",
		"talisma_decision_release_date", "talisma_enrollment_confirmation_deadline",
		"section_break_5", "program_details", "route", "published",
		"enable_admission_application", "introduction",
	]
	meta_fields = [field.fieldname for field in frappe.get_meta("Student Admission").fields]
	missing = set(order) - set(meta_fields)
	if missing:
		frappe.throw(_("Admission Intake fields are missing: {0}").format(", ".join(sorted(missing))))
	order.extend(fieldname for fieldname in meta_fields if fieldname not in order)
	make_property_setter("Student Admission", None, "field_order", json.dumps(order), "Data", for_doctype=True)


def _backfill_admission_intakes() -> None:
	for row in frappe.get_all(
		"Student Admission",
		fields=["name", "published", "admission_start_date", "admission_end_date", "academic_year"],
	):
		values = {}
		start = row.admission_start_date or today()
		end = row.admission_end_date or add_days(start, 30)
		if not row.admission_start_date:
			values["admission_start_date"] = start
		if not row.admission_end_date:
			values["admission_end_date"] = end
		if not frappe.db.get_value("Student Admission", row.name, "talisma_status"):
			values["talisma_status"] = "Open" if row.published else "Planned"
		if not frappe.db.get_value("Student Admission", row.name, "talisma_academic_term"):
			values["talisma_academic_term"] = frappe.db.get_value(
				"Academic Term", {"academic_year": row.academic_year}, "name", order_by="term_start_date"
			)
		if not frappe.db.get_value("Student Admission", row.name, "talisma_decision_release_date"):
			values["talisma_decision_release_date"] = add_days(end, 14)
		if not frappe.db.get_value("Student Admission", row.name, "talisma_enrollment_confirmation_deadline"):
			values["talisma_enrollment_confirmation_deadline"] = add_days(end, 28)
		if values:
			frappe.db.set_value("Student Admission", row.name, values, update_modified=False)

	for row in frappe.get_all(
		"Student Admission Program",
		fields=["name", "parent", "program", "talisma_intake_capacity", "talisma_status"],
	):
		filled = _application_count(row.parent, row.program)
		program = frappe.db.get_value(
			"Program", row.program, ["talisma_degree", "talisma_academic_unit"], as_dict=True
		) or frappe._dict()
		capacity = max(int(row.talisma_intake_capacity or 0), filled, 1)
		values = {
			"talisma_degree": program.get("talisma_degree"),
			"talisma_academic_unit": program.get("talisma_academic_unit"),
			"talisma_intake_capacity": capacity,
			"talisma_seats_filled": filled,
			"talisma_seats_available": capacity - filled,
		}
		if not row.talisma_status:
			values["talisma_status"] = "Full" if filled == capacity else "Open"
		frappe.db.set_value("Student Admission Program", row.name, values, update_modified=False)


def _backfill_student_applications() -> None:
	stage_by_status = {
		"Applied": "Submitted",
		"Approved": "Approved",
		"Rejected": "Rejected",
		"Admitted": "Admitted",
	}
	for row in frappe.get_all(
		"Student Applicant",
		fields=[
			"name", "application_status", "paid", "talisma_application_fee",
			"talisma_application_stage", "talisma_eligibility_status",
			"talisma_application_fee_status", "talisma_last_transition_on",
		],
	):
		values = {}
		legacy_default = row.talisma_application_stage == "Draft" and not row.talisma_last_transition_on
		stage = (
			stage_by_status.get(row.application_status, "Submitted")
			if legacy_default else row.talisma_application_stage or stage_by_status.get(row.application_status, "Draft")
		)
		if not row.talisma_application_stage or legacy_default:
			values["talisma_application_stage"] = stage
			values["talisma_last_transition_on"] = now_datetime()
			values["talisma_last_transition_by"] = "Administrator"
		if not row.talisma_eligibility_status or (
			legacy_default and row.talisma_eligibility_status == "Pending"
		):
			values["talisma_eligibility_status"] = (
				"Eligible" if stage in {"Approved", "Admitted"} else
				"Ineligible" if stage == "Rejected" else "Pending"
			)
		if not row.talisma_application_fee_status or legacy_default:
			values["talisma_application_fee_status"] = _fee_status(row)
		if values:
			frappe.db.set_value("Student Applicant", row.name, values, update_modified=False)


def validate_admission_intake(doc, method=None) -> None:
	"""Validate dates, participating programs, eligibility, and live capacity."""
	if doc.talisma_status not in INTAKE_STATUSES:
		frappe.throw(_("Select a valid Admission Intake Status."))
	if not doc.talisma_academic_term:
		frappe.throw(_("Academic Term is required."))
	term_year = frappe.db.get_value("Academic Term", doc.talisma_academic_term, "academic_year")
	if term_year != doc.academic_year:
		frappe.throw(_("Academic Term {0} does not belong to Academic Year {1}.").format(
			frappe.bold(doc.talisma_academic_term), frappe.bold(doc.academic_year)
		))
	_validate_timeline(doc)
	seen = set()
	for row in doc.program_details:
		if row.program in seen:
			frappe.throw(_("Program {0} is listed more than once.").format(frappe.bold(row.program)))
		seen.add(row.program)
		if int(row.talisma_intake_capacity or 0) <= 0:
			frappe.throw(_("Intake Capacity must be greater than zero in row {0}.").format(row.idx))
		if flt(row.application_fee) < 0:
			frappe.throw(_("Application Fee cannot be negative in row {0}.").format(row.idx))
		_set_program_defaults(row)
		filled = _application_count(doc.name, row.program)
		row.talisma_seats_filled = filled
		row.talisma_seats_available = max(int(row.talisma_intake_capacity) - filled, 0)
		if filled > int(row.talisma_intake_capacity):
			frappe.throw(_("Seats Filled cannot exceed Intake Capacity for {0}.").format(frappe.bold(row.program)))
		if filled == int(row.talisma_intake_capacity) and row.talisma_status not in {"Closed", "Cancelled"}:
			row.talisma_status = "Full"
		if row.talisma_status not in PROGRAM_STATUSES:
			frappe.throw(_("Select a valid Program Status in row {0}.").format(row.idx))
		_validate_program_eligibility(row)
	doc.enable_admission_application = int(doc.talisma_status == "Open")


def _validate_timeline(doc) -> None:
	start = getdate(doc.admission_start_date)
	end = getdate(doc.admission_end_date)
	decision = getdate(doc.talisma_decision_release_date)
	confirmation = getdate(doc.talisma_enrollment_confirmation_deadline)
	if start >= end:
		frappe.throw(_("Application Start Date must be before Application End Date."))
	if decision <= end:
		frappe.throw(_("Decision Release Date must be after Application End Date."))
	if confirmation <= decision:
		frappe.throw(_("Enrollment Confirmation Deadline must be after Decision Release Date."))


def _set_program_defaults(row) -> None:
	program = frappe.db.get_value(
		"Program", row.program, ["talisma_degree", "talisma_academic_unit"], as_dict=True
	)
	if not program:
		frappe.throw(_("Program {0} does not exist.").format(frappe.bold(row.program)))
	row.talisma_degree = program.talisma_degree
	row.talisma_academic_unit = program.talisma_academic_unit


def _validate_program_eligibility(row) -> None:
	if flt(row.talisma_minimum_gpa) < 0:
		frappe.throw(_("Minimum GPA cannot be negative in row {0}.").format(row.idx))
	if flt(row.talisma_minimum_credits) < 0:
		frappe.throw(_("Minimum Credits cannot be negative in row {0}.").format(row.idx))
	if row.min_age and row.max_age and int(row.min_age) > int(row.max_age):
		frappe.throw(_("Minimum Age cannot exceed Maximum Age in row {0}.").format(row.idx))
	if row.talisma_entrance_exam_required and flt(row.talisma_minimum_entrance_exam_score) < 0:
		frappe.throw(_("Minimum Entrance Exam Score cannot be negative in row {0}.").format(row.idx))
	if row.talisma_work_experience_required and flt(row.talisma_minimum_work_experience) < 0:
		frappe.throw(_("Minimum Work Experience cannot be negative in row {0}.").format(row.idx))


def validate_student_application_intake(doc, method=None) -> None:
	"""Keep applications authoritative, capacity-safe, auditable, and workflow-compatible."""
	if not doc.student_admission:
		if doc.is_new():
			frappe.throw(_("Admission Intake is required for a new Student Application."))
		return
	old_doc = None if doc.is_new() else doc.get_doc_before_save()
	selection_changed = not old_doc or any(
		old_doc.get(fieldname) != doc.get(fieldname)
		for fieldname in ("student_admission", "program")
	)
	if old_doc and selection_changed and old_doc.get("talisma_application_stage") != "Draft":
		if not doc.flags.get("allow_admission_transfer"):
			frappe.throw(_(
				"Admission Intake and Program are locked after submission. Use Transfer Application."
			))
	intake = frappe.get_doc("Student Admission", doc.student_admission)
	if selection_changed and intake.talisma_status != "Open":
		frappe.throw(_("Admission Intake {0} is not Open.").format(frappe.bold(intake.name)))
	application_date = getdate(doc.application_date or today())
	if selection_changed and (
		application_date < getdate(intake.admission_start_date)
		or application_date > getdate(intake.admission_end_date)
	):
		frappe.throw(_("Application Date must be within the Admission Intake application period."))
	program = next((row for row in intake.program_details if row.program == doc.program), None)
	if not program:
		frappe.throw(_("Program {0} is not offered in Admission Intake {1}.").format(
			frappe.bold(doc.program), frappe.bold(intake.name)
		))
	filled = _application_count(intake.name, program.program, exclude=doc.name)
	capacity = int(program.talisma_intake_capacity or 0)
	override = bool(doc.talisma_capacity_override)
	if override and frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only an administrator can override Intake Capacity."), frappe.PermissionError)
	if selection_changed and program.talisma_status in {"Closed", "Cancelled"}:
		frappe.throw(_("Program {0} is not Open for this Admission Intake.").format(frappe.bold(program.program)))
	if selection_changed and program.talisma_status == "Full" and not override:
		frappe.throw(_("Program {0} is not Open for this Admission Intake.").format(frappe.bold(program.program)))
	if selection_changed and filled >= capacity and not override:
		frappe.throw(_("Program {0} has reached its Intake Capacity.").format(frappe.bold(program.program)))
	doc.academic_year = intake.academic_year
	doc.academic_term = intake.talisma_academic_term
	doc.talisma_campus = intake.talisma_campus
	doc.talisma_degree = program.talisma_degree
	doc.talisma_academic_unit = program.talisma_academic_unit
	doc.talisma_application_fee = program.application_fee
	_sync_application_workflow(doc, old_doc)


def _sync_application_workflow(doc, old_doc=None) -> None:
	stage_by_status = {
		"Approved": "Approved",
		"Rejected": "Rejected",
		"Admitted": "Admitted",
	}
	status_by_stage = {
		"Approved": "Approved",
		"Rejected": "Rejected",
		"Admitted": "Admitted",
	}
	stage = doc.get("talisma_application_stage") or "Draft"
	if stage not in APPLICATION_STAGES:
		frappe.throw(_("Select a valid Application Stage."))
	if doc.get("talisma_eligibility_status") not in ELIGIBILITY_STATUSES:
		frappe.throw(_("Select a valid Eligibility Status."))
	if doc.get("talisma_application_fee_status") not in FEE_STATUSES:
		frappe.throw(_("Select a valid Application Fee Status."))

	if old_doc:
		status_changed = old_doc.application_status != doc.application_status
		stage_changed = old_doc.get("talisma_application_stage") != stage
		if status_changed and not stage_changed and doc.application_status in stage_by_status:
			stage = stage_by_status[doc.application_status]
			doc.talisma_application_stage = stage
	else:
		stage_changed = True

	if stage in {"Decision Pending", "Approved", "Admitted"} and doc.talisma_eligibility_status not in {
		"Eligible", "Conditionally Eligible",
	}:
		frappe.throw(_("Complete the Eligibility Review before moving the application to {0}.").format(stage))

	doc.application_status = status_by_stage.get(stage, "Applied")
	if doc.talisma_application_fee_status not in {"Waived", "Refunded"}:
		doc.talisma_application_fee_status = _fee_status(doc)
	if stage_changed:
		doc.talisma_last_transition_on = now_datetime()
		doc.talisma_last_transition_by = frappe.session.user
	if stage in {"Approved", "Waitlisted", "Rejected"}:
		doc.talisma_decision_date = doc.get("talisma_decision_date") or today()
		doc.talisma_decision_by = doc.get("talisma_decision_by") or frappe.session.user


def _fee_status(doc) -> str:
	if flt(doc.get("talisma_application_fee")) <= 0:
		return "Not Required"
	return "Paid" if doc.get("paid") else "Pending"


def refresh_admission_capacity(doc, method=None) -> None:
	intakes = {doc.get("student_admission")}
	if method == "on_update" and callable(getattr(doc, "get_doc_before_save", None)):
		old_doc = doc.get_doc_before_save()
		if old_doc:
			intakes.add(old_doc.get("student_admission"))
	for intake in filter(None, intakes):
		_refresh_intake_capacity(intake)


def _refresh_intake_capacity(intake: str) -> None:
	if not frappe.db.exists("Student Admission", intake):
		return
	for row in frappe.get_all(
		"Student Admission Program",
		filters={"parent": intake, "parenttype": "Student Admission"},
		fields=["name", "program", "talisma_intake_capacity", "talisma_status"],
	):
		filled = _application_count(intake, row.program)
		capacity = int(row.talisma_intake_capacity or 0)
		values = {
			"talisma_seats_filled": filled,
			"talisma_seats_available": max(capacity - filled, 0),
		}
		if filled >= capacity and row.talisma_status not in {"Closed", "Cancelled"}:
			values["talisma_status"] = "Full"
		elif filled < capacity and row.talisma_status == "Full":
			values["talisma_status"] = "Open"
		frappe.db.set_value("Student Admission Program", row.name, values, update_modified=False)


def _application_count(intake: str, program: str, exclude: str | None = None) -> int:
	filters = {
		"student_admission": intake,
		"program": program,
		"docstatus": ("<", 2),
		"application_status": ("!=", "Rejected"),
		"talisma_application_stage": ("not in", ["Draft", "Rejected", "Withdrawn"]),
	}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.db.count("Student Applicant", filters)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def open_admission_intake_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql(
		"""select name, title, academic_year, talisma_academic_term
		from `tabStudent Admission`
		where talisma_status = 'Open' and (name like %(txt)s or title like %(txt)s)
		order by admission_start_date desc limit %(start)s, %(page_len)s""",
		{"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def admission_program_query(doctype, txt, searchfield, start, page_len, filters):
	intake = (filters or {}).get("admission_intake")
	if not intake:
		return []
	return frappe.db.sql(
		"""select sap.program, p.program_name, sap.talisma_seats_available
		from `tabStudent Admission Program` sap
		inner join `tabProgram` p on p.name = sap.program
		where sap.parent = %(intake)s and sap.parenttype = 'Student Admission'
		and sap.talisma_status = 'Open' and sap.talisma_seats_available > 0
		and (sap.program like %(txt)s or p.program_name like %(txt)s)
		order by p.program_name limit %(start)s, %(page_len)s""",
		{"intake": intake, "txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


@frappe.whitelist()
def get_application_defaults(admission_intake: str, program: str | None = None) -> dict:
	intake = frappe.get_doc("Student Admission", admission_intake)
	if not frappe.has_permission("Student Admission", "read", doc=intake):
		frappe.throw(_("You do not have permission to view this Admission Intake."), frappe.PermissionError)
	result = {
		"academic_year": intake.academic_year,
		"academic_term": intake.talisma_academic_term,
		"campus": intake.talisma_campus,
	}
	if program:
		row = next((item for item in intake.program_details if item.program == program), None)
		if not row:
			frappe.throw(_("Program is not part of this Admission Intake."))
		result.update({
			"degree": row.talisma_degree,
			"academic_unit": row.talisma_academic_unit,
			"application_fee": row.application_fee,
			"seats_available": row.talisma_seats_available,
			"program_status": row.talisma_status,
			"eligibility": {
				"minimum_gpa": row.talisma_minimum_gpa,
				"previous_qualification": row.talisma_previous_qualification,
				"minimum_credits": row.talisma_minimum_credits,
				"minimum_age": row.min_age,
				"maximum_age": row.max_age,
				"english_language_requirement": row.talisma_english_language_requirement,
				"entrance_exam_required": row.talisma_entrance_exam_required,
				"minimum_entrance_exam_score": row.talisma_minimum_entrance_exam_score,
				"work_experience_required": row.talisma_work_experience_required,
				"minimum_work_experience": row.talisma_minimum_work_experience,
			},
		})
	return result


@frappe.whitelist()
def review_application_eligibility(applicant_name: str, status: str, notes: str | None = None) -> dict:
	applicant = _application_for_update(applicant_name)
	if status not in ELIGIBILITY_STATUSES or status == "Pending":
		frappe.throw(_("Select Eligible, Conditionally Eligible, or Ineligible."))
	if applicant.talisma_application_stage not in {"Submitted", "Under Review", "Decision Pending"}:
		frappe.throw(_("Eligibility can only be reviewed while an application is under review."))
	applicant.talisma_eligibility_status = status
	applicant.talisma_eligibility_notes = notes
	applicant.talisma_eligibility_reviewed_by = frappe.session.user
	applicant.talisma_eligibility_reviewed_on = now_datetime()
	if applicant.talisma_application_stage == "Submitted":
		applicant.talisma_application_stage = "Under Review"
	applicant.save()
	return _application_workflow_result(applicant)


@frappe.whitelist()
def transition_application(
	applicant_name: str,
	target_stage: str,
	reason: str | None = None,
	conditions: str | None = None,
) -> dict:
	applicant = _application_for_update(applicant_name)
	transitions = {
		"Draft": {"Submitted", "Withdrawn"},
		"Submitted": {"Under Review", "Withdrawn"},
		"Under Review": {"Decision Pending", "Rejected", "Withdrawn"},
		"Decision Pending": {"Approved", "Waitlisted", "Rejected", "Withdrawn"},
		"Waitlisted": {"Decision Pending", "Approved", "Rejected", "Withdrawn"},
		"Approved": {"Withdrawn"},
	}
	current = applicant.talisma_application_stage or "Draft"
	if target_stage not in transitions.get(current, set()):
		frappe.throw(_("Application cannot move from {0} to {1}.").format(current, target_stage))
	if target_stage in {"Decision Pending", "Approved"} and applicant.talisma_eligibility_status not in {
		"Eligible", "Conditionally Eligible",
	}:
		frappe.throw(_("Complete the Eligibility Review before this transition."))
	if target_stage in {"Approved", "Waitlisted", "Rejected"} and not reason:
		frappe.throw(_("Decision Reason is required."))
	applicant.talisma_application_stage = target_stage
	if target_stage in {"Approved", "Waitlisted", "Rejected"}:
		applicant.talisma_decision_date = today()
		applicant.talisma_decision_by = frappe.session.user
		applicant.talisma_decision_reason = reason
		applicant.talisma_decision_note = reason
		applicant.talisma_admission_conditions = conditions if target_stage == "Approved" else None
	applicant.save()
	return _application_workflow_result(applicant)


@frappe.whitelist()
def transfer_application(
	applicant_name: str,
	admission_intake: str,
	program: str,
	reason: str,
) -> dict:
	if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only an administrator can transfer a submitted application."), frappe.PermissionError)
	if not reason:
		frappe.throw(_("Transfer Reason is required."))
	applicant = _application_for_update(applicant_name)
	if applicant.talisma_application_stage in {"Admitted", "Rejected", "Withdrawn"}:
		frappe.throw(_("A final application cannot be transferred."))
	previous_intake = applicant.student_admission
	previous_program = applicant.program
	applicant.flags.allow_admission_transfer = True
	applicant.student_admission = admission_intake
	applicant.program = program
	applicant.talisma_application_stage = "Submitted"
	applicant.talisma_eligibility_status = "Pending"
	applicant.talisma_eligibility_notes = None
	applicant.talisma_eligibility_reviewed_by = None
	applicant.talisma_eligibility_reviewed_on = None
	applicant.talisma_decision_date = None
	applicant.talisma_decision_by = None
	applicant.talisma_decision_reason = None
	applicant.talisma_admission_conditions = None
	applicant.talisma_transfer_reason = reason
	applicant.talisma_transferred_by = frappe.session.user
	applicant.talisma_transferred_on = now_datetime()
	applicant.save()
	applicant.add_comment(
		"Info",
		_("Transferred from intake {0} / program {1} to {2} / {3}. Reason: {4}").format(
			previous_intake, previous_program, admission_intake, program, reason
		),
	)
	return _application_workflow_result(applicant)


def _application_for_update(applicant_name: str):
	applicant = frappe.get_doc("Student Applicant", applicant_name)
	if not frappe.has_permission("Student Applicant", "write", doc=applicant):
		frappe.throw(_("You do not have permission to update this application."), frappe.PermissionError)
	return applicant


def _application_workflow_result(applicant) -> dict:
	return {
		"name": applicant.name,
		"stage": applicant.talisma_application_stage,
		"eligibility_status": applicant.talisma_eligibility_status,
		"fee_status": applicant.talisma_application_fee_status,
		"application_status": applicant.application_status,
	}


def sync_admitted_application(doc, method=None) -> None:
	"""Keep the extended stage aligned when ERPNext creates a Student by its standard mapper."""
	if not doc.get("student_applicant") or not frappe.db.exists("Student Applicant", doc.student_applicant):
		return
	frappe.db.set_value(
		"Student Applicant",
		doc.student_applicant,
		{
			"application_status": "Admitted",
			"talisma_application_stage": "Admitted",
			"talisma_converted_student": doc.name,
			"talisma_decision_date": frappe.db.get_value(
				"Student Applicant", doc.student_applicant, "talisma_decision_date"
			) or today(),
			"talisma_last_transition_on": now_datetime(),
			"talisma_last_transition_by": frappe.session.user,
		},
		update_modified=False,
	)


def seed_demo_admission_intake() -> None:
	"""Create one open, capacity-managed intake and link the synthetic applications."""
	if frappe.local.site != DEMO_SITE:
		frappe.throw(_("Demo Admission Intake setup is restricted to {0}.").format(DEMO_SITE))
	academic_year = frappe.db.get_value("Academic Year", {"year_start_date": ("<=", "2026-08-01")}, "name", order_by="year_start_date desc")
	academic_term = frappe.db.get_value(
		"Academic Term", {"academic_year": academic_year}, "name", order_by="term_start_date"
	)
	campus = frappe.db.get_value("Talisma Campus", {}, "name")
	if not academic_year or not academic_term:
		frappe.throw(_("The demo academic year and term are required before creating Admission Intake data."))

	name = "Fall 2026 Intake"
	if frappe.db.exists("Student Admission", name):
		doc = frappe.get_doc("Student Admission", name)
	else:
		doc = frappe.new_doc("Student Admission")
	doc.update({
		"title": name,
		"academic_year": academic_year,
		"talisma_academic_term": academic_term,
		"talisma_campus": campus,
		"talisma_status": "Open",
		"admission_start_date": "2026-06-01",
		"admission_end_date": "2026-08-15",
		"talisma_decision_release_date": "2026-08-20",
		"talisma_enrollment_confirmation_deadline": "2026-08-31",
	})
	doc.set("program_details", [])
	for program in frappe.get_all(
		"Program",
		fields=["name", "talisma_degree", "talisma_academic_unit"],
		order_by="program_name",
	):
		is_graduate = program.talisma_degree and "Master" in program.talisma_degree
		doc.append("program_details", {
			"program": program.name,
			"talisma_degree": program.talisma_degree,
			"talisma_academic_unit": program.talisma_academic_unit,
			"application_fee": 75 if is_graduate else 50,
			"talisma_intake_capacity": 100,
			"talisma_status": "Open",
			"talisma_minimum_gpa": 3.0 if is_graduate else 2.5,
			"talisma_previous_qualification": "Bachelor's Degree" if is_graduate else "High School Diploma or equivalent",
			"talisma_english_language_requirement": "Institutional English proficiency policy",
		})
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	program_rows = {row.program: row for row in doc.program_details}
	for applicant in frappe.get_all("Student Applicant", fields=["name", "program"]):
		row = program_rows.get(applicant.program)
		if not row:
			continue
		frappe.db.set_value(
			"Student Applicant",
			applicant.name,
			{
				"student_admission": doc.name,
				"academic_year": academic_year,
				"academic_term": academic_term,
				"talisma_campus": campus,
				"talisma_degree": row.talisma_degree,
				"talisma_academic_unit": row.talisma_academic_unit,
				"talisma_application_fee": row.application_fee,
			},
			update_modified=False,
		)
	refresh_admission_capacity(frappe._dict(student_admission=doc.name))


def pipeline_status() -> list[dict]:
	"""Return the demo applicant pipeline without changing records."""
	_require_demo_site()
	return frappe.get_all(
		"Student Applicant",
		fields=[
			"name",
			"first_name",
			"last_name",
			"application_status",
			"student_email_id",
			"talisma_converted_student",
			"talisma_program_enrollment",
		],
		order_by="name",
	)


@frappe.whitelist()
def admit_applicant(applicant_name: str, decision_note: str | None = None) -> dict[str, str]:
	"""Admit an approved applicant and create linked academic records once."""
	_require_demo_site()
	applicant = frappe.get_doc("Student Applicant", applicant_name)
	if not frappe.has_permission("Student Applicant", "write", doc=applicant):
		frappe.throw(_("You do not have permission to admit this applicant."), frappe.PermissionError)

	if applicant.application_status not in {"Approved", "Admitted"}:
		frappe.throw(_("Approve the application before admitting the applicant."))
	if applicant.talisma_eligibility_status not in {"Eligible", "Conditionally Eligible"}:
		frappe.throw(_("Complete the Eligibility Review before admitting the applicant."))

	student = _get_or_create_student(applicant)
	program_enrollment = _get_or_create_program_enrollment(applicant, student)

	applicant.db_set(
		{
			"application_status": "Admitted",
			"talisma_application_stage": "Admitted",
			"talisma_decision_date": today(),
			"talisma_decision_by": frappe.session.user,
			"talisma_decision_note": decision_note or applicant.talisma_decision_note,
			"talisma_last_transition_on": now_datetime(),
			"talisma_last_transition_by": frappe.session.user,
			"talisma_converted_student": student.name,
			"talisma_program_enrollment": program_enrollment.name,
		},
		update_modified=True,
	)

	return {
		"applicant": applicant.name,
		"student": student.name,
		"program_enrollment": program_enrollment.name,
	}


def _get_or_create_student(applicant):
	student_name = applicant.talisma_converted_student or frappe.db.get_value(
		"Student", {"student_applicant": applicant.name}, "name"
	)
	if not student_name and applicant.student_email_id:
		student_name = frappe.db.get_value("Student", {"student_email_id": applicant.student_email_id}, "name")
	if student_name:
		student = frappe.get_doc("Student", student_name)
	else:
		student = get_mapped_doc(
			"Student Applicant",
			applicant.name,
			{
				"Student Applicant": {
					"doctype": "Student",
					"field_map": {"name": "student_applicant"},
				}
			},
			ignore_permissions=True,
		)
		student.set(
			"talisma_family_members",
			[
				{
					"family_member_name": row.family_member_name,
					"relation": row.relation,
				}
				for row in applicant.get("talisma_family_members", [])
			],
		)
		student.talisma_home_campus = applicant.talisma_campus
		student.insert(ignore_permissions=True)

	if applicant.talisma_campus and not student.talisma_home_campus:
		student.db_set("talisma_home_campus", applicant.talisma_campus)
	return student


def _get_or_create_program_enrollment(applicant, student):
	filters = {
		"student": student.name,
		"program": applicant.program,
		"academic_year": applicant.academic_year,
	}
	if applicant.academic_term:
		filters["academic_term"] = applicant.academic_term

	enrollment_name = applicant.talisma_program_enrollment or frappe.db.get_value(
		"Program Enrollment", filters
	)
	if enrollment_name:
		enrollment = frappe.get_doc("Program Enrollment", enrollment_name)
	else:
		enrollment = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student.name,
				"student_name": student.student_name,
				"student_category": applicant.student_category,
				"program": applicant.program,
				"academic_year": applicant.academic_year,
				"academic_term": applicant.academic_term,
				"enrollment_date": today(),
				"talisma_campus": applicant.talisma_campus,
			}
		).insert(ignore_permissions=True)

	if applicant.talisma_campus and not enrollment.talisma_campus:
		enrollment.db_set("talisma_campus", applicant.talisma_campus)
	return enrollment


def _require_demo_site() -> None:
	if frappe.local.site != DEMO_SITE:
		frappe.throw(_("The demo admissions workflow is restricted to {0}.").format(DEMO_SITE))
