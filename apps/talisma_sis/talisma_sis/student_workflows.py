"""Student-centered relationship actions used by the Student 360 dialogs."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from talisma_sis.demo import DEMO_SITE


ADVISOR_FIELDS = {
	"advisor",
	"advisor_type",
	"program",
	"academic_unit",
	"primary_advisor",
	"status",
	"effective_from",
	"effective_to",
	"end_reason",
}
ENROLLMENT_FIELDS = {
	"program",
	"talisma_curriculum_version",
	"academic_year",
	"academic_term",
	"enrollment_date",
	"talisma_campus",
}
HOLD_FIELDS = {
	"hold_type", "reason", "owning_department", "effective_from", "effective_to",
	"blocks_registration", "blocks_transcript", "blocks_graduation", "blocks_financial_activity",
}
PRIVACY_FIELDS = {
	"ferpa_restriction", "directory_information_consent", "restriction_scope",
	"effective_from", "effective_to", "consent_source", "consent_document",
	"emergency_disclosure_permission",
}


@frappe.whitelist()
def get_student_action_context(student: str) -> dict:
	_require_student(student, "read")
	student_doc = frappe.get_doc("Student", student)
	active_program = frappe.db.get_value(
		"Talisma Student Academic Program",
		{"student": student, "primary_program": 1, "status": "Active"},
		["program", "program_version", "start_term", "campus"],
		as_dict=True,
		order_by="effective_from desc, creation desc",
	) or {}
	current_enrollment = frappe.db.get_value(
		"Program Enrollment",
		{"student": student, "docstatus": ("<", 2)},
		["academic_year", "academic_term", "talisma_campus"],
		as_dict=True,
		order_by="enrollment_date desc, creation desc",
	) or {}
	term = active_program.get("start_term") or current_enrollment.get("academic_term")
	academic_year = current_enrollment.get("academic_year")
	if term and not academic_year:
		academic_year = frappe.db.get_value("Academic Term", term, "academic_year")
	return {
		"student": student,
		"student_name": student_doc.student_name,
		"today": today(),
		"program": active_program.get("program"),
		"curriculum_version": active_program.get("program_version"),
		"academic_year": academic_year or frappe.defaults.get_user_default("academic_year"),
		"academic_term": term or frappe.defaults.get_user_default("academic_term"),
		"campus": active_program.get("campus") or current_enrollment.get("talisma_campus") or student_doc.get("talisma_home_campus"),
	}


@frappe.whitelist()
def save_advisor_assignment(student: str, values, assignment: str | None = None) -> dict:
	_require_student(student, "read")
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if assignment:
		doc = frappe.get_doc("Talisma Student Advisor Assignment", assignment)
		if doc.student != student:
			frappe.throw(_("This Advisor Assignment does not belong to the selected Student."))
		if not frappe.has_permission(doc.doctype, "write", doc=doc):
			frappe.throw(_("You do not have permission to edit Advisor Assignments."), frappe.PermissionError)
	else:
		if not frappe.has_permission("Talisma Student Advisor Assignment", "create"):
			frappe.throw(_("You do not have permission to create Advisor Assignments."), frappe.PermissionError)
		doc = frappe.new_doc("Talisma Student Advisor Assignment")
		doc.student = student
	for fieldname in ADVISOR_FIELDS:
		if fieldname in values:
			doc.set(fieldname, values.get(fieldname))
	if assignment:
		doc.save()
	else:
		doc.insert()
	return {"name": doc.name, "student": doc.student, "status": doc.status}


@frappe.whitelist()
def save_program_enrollment(student: str, values, program_enrollment: str | None = None) -> dict:
	_require_student(student, "read")
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if program_enrollment:
		doc = frappe.get_doc("Program Enrollment", program_enrollment)
		if doc.student != student:
			frappe.throw(_("This Program Enrollment does not belong to the selected Student."))
		if doc.docstatus != 0:
			frappe.throw(_("Submitted Program Enrollments must be managed from their full record."))
		if not frappe.has_permission("Program Enrollment", "write", doc=doc):
			frappe.throw(_("You do not have permission to edit Program Enrollments."), frappe.PermissionError)
	else:
		if not frappe.has_permission("Program Enrollment", "create"):
			frappe.throw(_("You do not have permission to create Program Enrollments."), frappe.PermissionError)
		doc = frappe.new_doc("Program Enrollment")
		doc.student = student
		doc.student_name = frappe.db.get_value("Student", student, "student_name")
	for fieldname in ENROLLMENT_FIELDS:
		if fieldname in values:
			doc.set(fieldname, values.get(fieldname))
	if program_enrollment:
		doc.save()
	else:
		doc.insert()
	return {
		"name": doc.name,
		"student": doc.student,
		"program": doc.program,
		"curriculum_version": doc.talisma_curriculum_version,
		"docstatus": doc.docstatus,
	}


@frappe.whitelist()
def add_student_hold(student: str, values) -> dict:
	_require_student(student, "read")
	if not frappe.has_permission("Talisma Student Hold", "create"):
		frappe.throw(_("You do not have permission to create Student Holds."), frappe.PermissionError)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	doc = frappe.new_doc("Talisma Student Hold")
	doc.student = student
	doc.status = "Active"
	for fieldname in HOLD_FIELDS:
		if fieldname in values:
			doc.set(fieldname, values.get(fieldname))
	doc.effective_from = doc.effective_from or today()
	doc.insert()
	return {"name": doc.name, "student": doc.student, "status": doc.status}


@frappe.whitelist()
def add_privacy_preference(student: str, values) -> dict:
	_require_student(student, "read")
	if not frappe.has_permission("Talisma Student Privacy Preference", "create"):
		frappe.throw(_("You do not have permission to create Privacy Preferences."), frappe.PermissionError)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	effective_from = getdate(values.get("effective_from") or today())
	current = frappe.get_all(
		"Talisma Student Privacy Preference",
		filters={"student": student, "effective_from": ("<=", effective_from)},
		fields=["name", "effective_from", "effective_to"],
		order_by="effective_from desc, creation desc",
		limit=1,
	)
	if current and (not current[0].effective_to or getdate(current[0].effective_to) >= effective_from):
		if getdate(current[0].effective_from) >= effective_from:
			frappe.throw(_("A Privacy Preference already starts on this date. Choose a later Effective From date."))
		current_doc = frappe.get_doc("Talisma Student Privacy Preference", current[0].name)
		if not frappe.has_permission(current_doc.doctype, "write", doc=current_doc):
			frappe.throw(_("You do not have permission to close the current Privacy Preference."), frappe.PermissionError)
		current_doc.effective_to = add_days(effective_from, -1)
		current_doc.save()
	doc = frappe.new_doc("Talisma Student Privacy Preference")
	doc.student = student
	for fieldname in PRIVACY_FIELDS:
		if fieldname in values:
			doc.set(fieldname, values.get(fieldname))
	doc.effective_from = effective_from
	doc.insert()
	return {"name": doc.name, "student": doc.student, "effective_from": doc.effective_from}


def _require_student(student: str, permission_type: str) -> None:
	if frappe.local.site != DEMO_SITE:
		frappe.throw(_("Student actions are restricted to {0}.").format(DEMO_SITE))
	student_doc = frappe.get_doc("Student", student)
	if not frappe.has_permission("Student", permission_type, doc=student_doc):
		frappe.throw(_("You do not have permission to access this Student."), frappe.PermissionError)
