"""Effective-dated Student Records foundation for the demo SIS."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, getdate, now_datetime, today


DEMO_SITE = "demo.talisma.local"
EFFECTIVE_DOCTYPES = {
	"Talisma Student Identifier": ("effective_from", "effective_to"),
	"Talisma Student Status History": ("effective_from", "effective_to"),
	"Talisma Student Academic Program": ("effective_from", "effective_to"),
	"Talisma Student Advisor Assignment": ("effective_from", "effective_to"),
	"Talisma Student Hold": ("effective_from", "effective_to"),
	"Talisma Student Privacy Preference": ("effective_from", "effective_to"),
	"Talisma Student Classification History": ("effective_from", "effective_to"),
	"Talisma Student Name History": ("effective_from", "effective_to"),
}


def configure_student_records() -> None:
	"""Add current-snapshot and contact governance fields without replacing Student."""
	create_custom_fields(
		{
			"Student": [
				_field("talisma_record_status", "Student Record Status", "Select", "talisma_enrollment_status", options="Applicant\nAdmitted\nActive\nLeave of Absence\nWithdrawn\nSuspended\nDismissed\nGraduated\nDeceased", read_only=1),
				_field("talisma_primary_program", "Primary Program", "Link", "talisma_record_status", options="Program", read_only=1),
				_field("talisma_privacy_restriction", "Privacy Restriction", "Check", "talisma_primary_program", read_only=1),
				_field("talisma_active_hold_count", "Active Holds", "Int", "talisma_privacy_restriction", read_only=1),
				_field("talisma_legal_sex", "Legal Sex", "Select", "gender", options="\nFemale\nMale\nIntersex\nNot Specified"),
				_field("talisma_primary_language", "Primary Language", "Data", "talisma_legal_sex"),
				_field("talisma_deceased", "Deceased", "Check", "talisma_primary_language", default="0"),
				_field("talisma_deceased_date", "Deceased Date", "Date", "talisma_deceased", depends_on="eval:doc.talisma_deceased == 1"),
			],
			"Address": [
				_field("talisma_student_address_type", "Student Address Type", "Select", "address_type", options="\nPermanent\nMailing\nCampus\nBilling"),
				_field("talisma_effective_from", "Effective From", "Date", "talisma_student_address_type"),
				_field("talisma_effective_to", "Effective To", "Date", "talisma_effective_from"),
				_field("talisma_primary_student_address", "Primary Student Address", "Check", "talisma_effective_to"),
				_field("talisma_confidential", "Confidential", "Check", "talisma_primary_student_address"),
			],
			"Contact": [
				_field("talisma_preferred_contact", "Preferred Contact", "Check", "is_primary_contact"),
				_field("talisma_email_consent", "Email Consent", "Check", "talisma_preferred_contact", default="1"),
				_field("talisma_sms_consent", "SMS Consent", "Check", "talisma_email_consent", default="0"),
				_field("talisma_effective_from", "Effective From", "Date", "talisma_sms_consent"),
				_field("talisma_effective_to", "Effective To", "Date", "talisma_effective_from"),
			],
			"Talisma Family Member": [
				_field("emergency_contact", "Emergency Contact", "Check", "relation", in_list_view=1),
				_field("legal_guardian", "Legal Guardian", "Check", "emergency_contact", in_list_view=1),
				_field("authorized_contact", "Authorized Contact", "Check", "legal_guardian"),
				_field("financially_responsible", "Financially Responsible", "Check", "authorized_contact"),
				_field("ferpa_authorized", "FERPA Authorized", "Check", "financially_responsible"),
				_field("priority", "Priority", "Int", "ferpa_authorized", default="1"),
				_field("phone", "Phone", "Data", "priority"),
				_field("email", "Email", "Data", "phone", options="Email"),
			],
		},
		update=False,
	)


def _field(fieldname, label, fieldtype, insert_after="", options="", **values):
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"insert_after": insert_after,
		"options": options,
		**values,
	}


def validate_effective_record(doc, method=None) -> None:
	if not _is_demo() or doc.doctype not in EFFECTIVE_DOCTYPES:
		return
	from_field, to_field = EFFECTIVE_DOCTYPES[doc.doctype]
	start = doc.get(from_field)
	end = doc.get(to_field)
	if not start:
		return
	if start and end and getdate(end) < getdate(start):
		frappe.throw(_("Effective To cannot be before Effective From."))
	if doc.doctype == "Talisma Student Hold":
		_validate_hold(doc)
	if doc.doctype == "Talisma Student Status History":
		doc.approved_by = doc.approved_by or frappe.session.user
	if doc.doctype == "Talisma Student Privacy Preference":
		doc.verified_by = doc.verified_by or frappe.session.user
	if doc.doctype == "Talisma Student Academic Program":
		program_degree = frappe.db.get_value("Program", doc.program, "talisma_degree")
		if program_degree and program_degree != doc.degree:
			frappe.throw(_("The selected Program belongs to Degree {0}.").format(frappe.bold(program_degree)))
		from talisma_sis.curriculum import validate_student_program_assignment
		validate_student_program_assignment(doc)
	if doc.doctype == "Talisma Student Advisor Assignment":
		_validate_advisor_assignment(doc)
	if doc.doctype in {
		"Talisma Student Status History",
		"Talisma Student Classification History",
		"Talisma Student Privacy Preference",
	}:
		_validate_no_overlap(doc, {})
	if doc.doctype == "Talisma Student Academic Program" and doc.primary_program and doc.status == "Active":
		_validate_no_overlap(doc, {"primary_program": 1, "status": "Active"})
	if doc.doctype == "Talisma Student Advisor Assignment" and doc.primary_advisor and doc.status == "Active":
		_validate_no_overlap(doc, {"primary_advisor": 1, "status": "Active", "advisor_type": doc.advisor_type})
	if doc.doctype == "Talisma Student Identifier" and doc.is_primary and doc.active:
		_validate_no_overlap(doc, {"is_primary": 1, "active": 1, "identifier_type": doc.identifier_type})


def _validate_no_overlap(doc, extra_filters: dict) -> None:
	from_field, to_field = EFFECTIVE_DOCTYPES[doc.doctype]
	start = getdate(doc.get(from_field))
	end = getdate(doc.get(to_field)) if doc.get(to_field) else getdate("2999-12-31")
	for row in frappe.get_all(
		doc.doctype,
		filters={"student": doc.student, "name": ("!=", doc.name or ""), **extra_filters},
		fields=["name", from_field, to_field],
	):
		row_start = getdate(row.get(from_field))
		row_end = getdate(row.get(to_field)) if row.get(to_field) else getdate("2999-12-31")
		if start <= row_end and row_start <= end:
			frappe.throw(
				_("Effective dates overlap existing {0} record {1}.").format(
					doc.doctype, frappe.bold(row.name)
				)
			)


def _validate_hold(doc) -> None:
	if doc.status == "Released":
		doc.released_by = doc.released_by or frappe.session.user
		doc.released_on = doc.released_on or now_datetime()
		if not doc.release_comments:
			frappe.throw(_("Release Comments are required when releasing a Student Hold."))
	if doc.status == "Active" and not any(
		(doc.blocks_registration, doc.blocks_transcript, doc.blocks_graduation, doc.blocks_financial_activity)
	):
		frappe.throw(_("An active Student Hold must block at least one activity."))


def _validate_advisor_assignment(doc) -> None:
	if doc.status == "Ended":
		if not doc.effective_to:
			frappe.throw(_("Effective To is required when ending an Advisor Assignment."))
		if not doc.end_reason:
			frappe.throw(_("End Reason is required when ending an Advisor Assignment."))
	if doc.status == "Active":
		instructor = frappe.db.get_value(
			"Instructor", doc.advisor, ["status", "talisma_academic_unit"], as_dict=True
		) or {}
		if instructor.get("status") != "Active":
			frappe.throw(_("Only an active Instructor can be assigned as an advisor."))
		_validate_no_overlap(
			doc,
			{"advisor": doc.advisor, "advisor_type": doc.advisor_type, "status": "Active"},
		)
	program_unit = frappe.db.get_value("Program", doc.program, "talisma_academic_unit") if doc.program else None
	if program_unit and not doc.academic_unit:
		doc.academic_unit = program_unit
	if program_unit and doc.academic_unit != program_unit:
		frappe.throw(_("The selected Program belongs to Academic Unit {0}.").format(frappe.bold(program_unit)))
	instructor_unit = frappe.db.get_value("Instructor", doc.advisor, "talisma_academic_unit")
	if instructor_unit and doc.academic_unit and instructor_unit != doc.academic_unit:
		frappe.throw(
			_("Advisor {0} belongs to a different Academic Unit.").format(frappe.bold(doc.advisor))
		)


def sync_student_snapshot(doc, method=None) -> None:
	if not _is_demo() or not doc.get("student"):
		return
	refresh_student_snapshot(doc.student)


def refresh_student_snapshot(student: str) -> None:
	if not frappe.db.exists("Student", student):
		return
	as_of = today()
	status = _current_record("Talisma Student Status History", student, as_of)
	program = _current_record(
		"Talisma Student Academic Program",
		student,
		as_of,
		{"primary_program": 1, "status": "Active"},
	)
	advisor = _current_record(
		"Talisma Student Advisor Assignment",
		student,
		as_of,
		{"primary_advisor": 1, "status": "Active"},
	)
	privacy = _current_record("Talisma Student Privacy Preference", student, as_of)
	classification = _current_record("Talisma Student Classification History", student, as_of)
	holds = active_holds(student)
	values = {
		"talisma_record_status": status.status if status else None,
		"talisma_primary_program": program.program if program else None,
		"talisma_privacy_restriction": int(bool(privacy and privacy.ferpa_restriction)),
		"talisma_active_hold_count": len(holds),
		"talisma_deceased": int(bool(status and status.status == "Deceased")),
		"talisma_deceased_date": status.effective_from if status and status.status == "Deceased" else None,
		"talisma_advisor": advisor.advisor if advisor else None,
	}
	if program:
		values.update({
			"talisma_academic_level": program.academic_level,
			"talisma_catalog_year": program.catalog_year,
			"talisma_home_campus": program.campus,
			"talisma_expected_graduation_term": program.expected_graduation_term,
		})
	if classification:
		values.update({
			"talisma_academic_level": classification.academic_level,
			"talisma_class_standing": classification.class_standing,
			"talisma_home_campus": classification.campus,
		})
	frappe.db.set_value("Student", student, values, update_modified=False)


def _current_record(doctype: str, student: str, as_of, extra_filters: dict | None = None):
	from_field, to_field = EFFECTIVE_DOCTYPES[doctype]
	# SQL-style OR filters are clearer and reliable for open-ended effective dates.
	rows = frappe.get_all(
		doctype,
		filters={"student": student, from_field: ("<=", as_of), **(extra_filters or {})},
		fields=["*"],
		order_by=f"{from_field} desc, creation desc",
	)
	return next(
		(row for row in rows if not row.get(to_field) or getdate(row.get(to_field)) >= getdate(as_of)),
		None,
	)


def active_holds(student: str) -> list:
	as_of = getdate(today())
	return [
		row
		for row in frappe.get_all(
			"Talisma Student Hold",
			filters={"student": student, "status": "Active", "effective_from": ("<=", as_of)},
			fields=["*"],
			order_by="effective_from desc",
		)
		if not row.effective_to or getdate(row.effective_to) >= as_of
	]


def validate_student(doc, method=None) -> None:
	if not _is_demo():
		return
	if doc.talisma_deceased and not doc.talisma_deceased_date:
		frappe.throw(_("Deceased Date is required when Deceased is selected."))
	if doc.student_email_id:
		duplicate = frappe.db.get_value(
			"Student",
			{"student_email_id": doc.student_email_id, "name": ("!=", doc.name or "")},
			"name",
		)
		if duplicate:
			frappe.throw(
				_("A Student already uses this email address: {0}").format(
					frappe.bold(duplicate)
				),
				title=_("Possible Duplicate Student"),
			)
	if doc.date_of_birth and doc.first_name and doc.last_name:
		duplicate = frappe.db.get_value(
			"Student",
			{
				"first_name": doc.first_name,
				"last_name": doc.last_name,
				"date_of_birth": doc.date_of_birth,
				"name": ("!=", doc.name or ""),
			},
			"name",
		)
		if duplicate:
			frappe.throw(
				_("A Student with the same legal name and date of birth already exists: {0}").format(
					frappe.bold(duplicate)
				),
				title=_("Possible Duplicate Student"),
			)


def validate_contact_dates(doc, method=None) -> None:
	if not _is_demo() or not doc.meta.has_field("talisma_effective_from"):
		return
	if doc.get("talisma_effective_from") and doc.get("talisma_effective_to"):
		if getdate(doc.talisma_effective_to) < getdate(doc.talisma_effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))


def identifier_query_conditions(user=None) -> str:
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""
	tick = chr(96)
	return f"{tick}tabTalisma Student Identifier{tick}.{tick}identifier_type{tick} != 'Government ID'"


def identifier_has_permission(doc, user=None, permission_type=None) -> bool | None:
	user = user or frappe.session.user
	if doc.identifier_type != "Government ID" or "System Manager" in frappe.get_roles(user):
		return None
	return False


def capture_name_history(doc, method=None) -> None:
	if not _is_demo() or doc.is_new():
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	fields = ("first_name", "middle_name", "last_name", "talisma_preferred_name")
	if not any(before.get(field) != doc.get(field) for field in fields):
		return
	current = frappe.db.get_value(
		"Talisma Student Name History",
		{"student": doc.name, "effective_to": ("is", "not set")},
		"name",
		order_by="effective_from desc, creation desc",
	)
	if current:
		frappe.db.set_value(
			"Talisma Student Name History",
			current,
			"effective_to",
			add_days(today(), -1),
			update_modified=False,
		)
	frappe.get_doc({
		"doctype": "Talisma Student Name History",
		"student": doc.name,
		"first_name": doc.first_name,
		"middle_name": doc.middle_name,
		"last_name": doc.last_name,
		"preferred_name": doc.get("talisma_preferred_name"),
		"effective_from": today(),
		"reason": "Student name updated",
		"source": "Registrar",
	}).insert(ignore_permissions=True)


@frappe.whitelist()
def find_duplicate_students(first_name="", last_name="", date_of_birth=None, email="") -> list[dict]:
	if not frappe.has_permission("Student", "read"):
		frappe.throw(_("You do not have permission to search Student records."), frappe.PermissionError)
	fields = ["name", "student_name", "date_of_birth", "student_email_id", "talisma_record_status"]
	matches = {}
	if email:
		for row in frappe.get_list("Student", filters={"student_email_id": email}, fields=fields, limit=20):
			matches[row.name] = row
	if first_name and last_name:
		filters = {"first_name": first_name, "last_name": last_name}
		if date_of_birth:
			filters["date_of_birth"] = date_of_birth
		for row in frappe.get_list("Student", filters=filters, fields=fields, limit=20):
			matches[row.name] = row
	return list(matches.values())[:20]


def seed_demo_student_records() -> None:
	term = frappe.db.get_value("Academic Term", {"term_name": "Fall 2026"}, "name")
	term_start = frappe.db.get_value("Academic Term", term, "term_start_date") or today()
	advisor = frappe.db.get_value("Instructor", {"instructor_name": "Dr. Maya Chen"}, "name")
	for student in frappe.get_all(
		"Student",
		fields=["name", "first_name", "middle_name", "last_name", "talisma_preferred_name", "talisma_home_campus", "talisma_academic_level", "talisma_class_standing", "talisma_catalog_year"],
	):
		enrollment = frappe.db.get_value(
			"Program Enrollment",
			{"student": student.name, "docstatus": ("!=", 2)},
			["program", "academic_term", "enrollment_date", "talisma_campus"],
			as_dict=True,
			order_by="enrollment_date desc",
		)
		if not enrollment:
			continue
		degree, academic_unit = frappe.db.get_value(
			"Program", enrollment.program, ["talisma_degree", "talisma_academic_unit"]
		)
		start_term = enrollment.academic_term or term
		effective_from = enrollment.enrollment_date or term_start
		_ensure("Talisma Student Status History", {"student": student.name, "status": "Active"}, {
			"student": student.name, "status": "Active", "reason": "Current enrolled student",
			"academic_term": start_term, "effective_from": effective_from, "source": "System Migration",
			"approved_by": "Administrator",
		})
		_ensure("Talisma Student Academic Program", {"student": student.name, "program": enrollment.program, "primary_program": 1}, {
			"student": student.name, "degree": degree, "program": enrollment.program,
			"affiliation_type": "Primary Major", "primary_program": 1,
			"catalog_year": student.talisma_catalog_year or "2026-2027", "academic_unit": academic_unit,
			"campus": enrollment.talisma_campus or student.talisma_home_campus,
			"academic_level": student.talisma_academic_level or "Undergraduate", "start_term": start_term,
			"status": "Active", "effective_from": effective_from,
		})
		if advisor:
			_ensure("Talisma Student Advisor Assignment", {"student": student.name, "advisor": advisor, "primary_advisor": 1}, {
				"student": student.name, "advisor": advisor, "advisor_type": "Academic",
				"program": enrollment.program, "academic_unit": academic_unit, "primary_advisor": 1,
				"status": "Active", "effective_from": effective_from,
			})
		_ensure("Talisma Student Privacy Preference", {"student": student.name}, {
			"student": student.name, "ferpa_restriction": 0,
			"directory_information_consent": "Granted", "effective_from": effective_from,
			"consent_source": "System Migration", "verified_by": "Administrator",
		})
		_ensure("Talisma Student Classification History", {"student": student.name, "academic_term": start_term}, {
			"student": student.name, "residency_classification": "In-State",
			"tuition_residency": "Resident", "student_type": "First-Time",
			"academic_level": student.talisma_academic_level or "Undergraduate",
			"class_standing": student.talisma_class_standing or "Freshman", "admit_type": "New First-Time",
			"cohort": "Fall 2026", "campus": enrollment.talisma_campus or student.talisma_home_campus,
			"academic_term": start_term, "effective_from": effective_from, "source": "System Migration",
		})
		_ensure("Talisma Student Identifier", {"identifier_value": f"LEGACY-{student.name}"}, {
			"student": student.name, "identifier_type": "Legacy Student ID",
			"identifier_value": f"LEGACY-{student.name}", "issuing_organization": "Bryan University",
			"effective_from": effective_from, "is_primary": 0, "active": 1, "verification_status": "Verified",
		})
		_ensure("Talisma Student Name History", {"student": student.name, "effective_to": ("is", "not set")}, {
			"student": student.name, "first_name": student.first_name, "middle_name": student.middle_name,
			"last_name": student.last_name, "preferred_name": student.talisma_preferred_name,
			"effective_from": effective_from, "reason": "Initial student identity", "source": "System Migration",
		})
		_ensure("Talisma Student Academic Standing", {"student": student.name, "academic_term": start_term}, {
			"student": student.name, "academic_term": start_term, "program": enrollment.program,
			"standing": "Good Standing", "term_gpa": 0, "cumulative_gpa": 0,
			"attempted_credits": 0, "earned_credits": 0, "effective_date": effective_from,
			"reason": "Initial standing",
		})
		refresh_student_snapshot(student.name)

	hold_student = frappe.db.get_value("Student", {"first_name": "Prince"}, "name")
	if hold_student:
		_ensure("Talisma Student Hold", {"student": hold_student, "hold_type": "Advising", "status": "Active"}, {
			"student": hold_student, "hold_type": "Advising",
			"reason": "Meet with the academic advisor before changing registration.",
			"effective_from": today(), "status": "Active", "blocks_registration": 1,
		})
		refresh_student_snapshot(hold_student)


def _ensure(doctype: str, filters: dict, values: dict):
	name = frappe.db.exists(doctype, filters)
	if name:
		frappe.db.set_value(doctype, name, values, update_modified=False)
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


def healthcheck() -> dict:
	students = frappe.db.count("Student")
	checks = {
		"snapshot_fields": all(
			frappe.get_meta("Student").get_field(field)
			for field in ("talisma_record_status", "talisma_primary_program", "talisma_privacy_restriction", "talisma_active_hold_count")
		),
		"status_history": frappe.db.count("Talisma Student Status History") >= students,
		"academic_programs": frappe.db.count("Talisma Student Academic Program") >= students,
		"advisor_assignments": frappe.db.count("Talisma Student Advisor Assignment") >= students,
		"standing_history": frappe.db.count("Talisma Student Academic Standing") >= students,
		"privacy_preferences": frappe.db.count("Talisma Student Privacy Preference") >= students,
		"classification_history": frappe.db.count("Talisma Student Classification History") >= students,
		"identifiers": frappe.db.count("Talisma Student Identifier") >= students,
		"name_history": frappe.db.count("Talisma Student Name History") >= students,
		"registration_hold_seeded": frappe.db.count("Talisma Student Hold", {"blocks_registration": 1, "status": "Active"}) >= 1,
	}
	return {"ok": all(checks.values()), "checks": checks}


def _is_demo() -> bool:
	return frappe.local.site == DEMO_SITE
