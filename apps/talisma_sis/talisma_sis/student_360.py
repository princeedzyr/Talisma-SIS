"""Student-centered US higher-education views backed by standard Education records."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import getdate, today


DEMO_SITE = "demo.talisma.local"


def configure_student_360() -> None:
	"""Apply the upgrade-safe Student layout without replacing standard data models."""
	create_custom_fields(
		{
			"Student": [
				_field("talisma_student_number", "Student Number", "Read Only", "first_name"),
				_field("talisma_identity_name_column_2", "", "Column Break", "first_name"),
				_field("talisma_identity_name_column_3", "", "Column Break", "middle_name"),
				_field("talisma_identity_name_column_4", "", "Column Break", "last_name"),
				_field("talisma_additional_column_2", "", "Column Break", "gender"),
				_field("talisma_additional_column_3", "", "Column Break", "talisma_marital_status"),
				_field(
					"talisma_marital_status",
					"Marital Status",
					"Select",
					"gender",
					options="\nSingle\nMarried\nDivorced\nWidowed",
				),
				_field(
					"talisma_ethnic_group",
					"Ethnic Group",
					"Select",
					"talisma_marital_status",
					options="\nAmerican Indian or Alaska Native\nAsian\nBlack or African American\nHispanic or Latino\nNative Hawaiian or Other Pacific Islander\nWhite\nTwo or More Races\nNot Specified",
				),
				_field("talisma_contact_section", "Contact Information", "Section Break", "nationality"),
				_field("talisma_secondary_phone", "Secondary Phone Number", "Data", "student_mobile_number"),
				_field(
					"talisma_secondary_email",
					"Secondary Email ID",
					"Data",
					"student_email_id",
					options="Email",
				),
				_field("talisma_contact_column_2", "", "Column Break", "talisma_secondary_email"),
				_field("talisma_contact_column_3", "", "Column Break", "pincode"),
				_field("talisma_enrollment_tab", "Enrollment Information", "Tab Break", "country"),
				_field(
					"talisma_current_enrollment_section",
					"Current Enrollment",
					"Section Break",
					"talisma_enrollment_tab",
				),
				_field(
					"talisma_current_enrollment_html",
					"",
					"HTML",
					"talisma_current_enrollment_section",
				),
				_field(
					"talisma_enrollment_history_section",
					"Program Enrollment",
					"Section Break",
					"talisma_current_enrollment_html",
				),
				_field(
					"talisma_enrollment_history_html",
					"",
					"HTML",
					"talisma_enrollment_history_section",
				),
				_field(
					"talisma_course_registration_tab",
					"Course Registration",
					"Tab Break",
					"talisma_enrollment_history_html",
				),
				_field(
					"talisma_course_registration_section",
					"Course Registration",
					"Section Break",
					"talisma_course_registration_tab",
				),
				_field(
					"talisma_course_registration_html",
					"",
					"HTML",
					"talisma_course_registration_section",
				),
				_field(
					"talisma_finance_tab",
					"Student Account",
					"Tab Break",
					"talisma_course_registration_html",
				),
				_field(
					"talisma_payment_summary_section",
					"Account Summary",
					"Section Break",
					"talisma_finance_tab",
				),
				_field(
					"talisma_payment_summary_html",
					"",
					"HTML",
					"talisma_payment_summary_section",
				),
				_field(
					"talisma_fee_structure_section",
					"Billing Statements",
					"Section Break",
					"talisma_payment_summary_html",
				),
				_field("talisma_fee_structure_html", "", "HTML", "talisma_fee_structure_section"),
				_field(
					"talisma_fee_details_section",
					"Student Payments",
					"Section Break",
					"talisma_fee_structure_html",
				),
				_field("talisma_fee_details_html", "", "HTML", "talisma_fee_details_section"),
				_field("talisma_refunds_section", "Refunds", "Section Break", "talisma_fee_details_html"),
				_field("talisma_refunds_html", "", "HTML", "talisma_refunds_section"),
				_field("talisma_academic_profile_tab", "Academic Profile", "Tab Break", "talisma_refunds_html"),
				_field("talisma_profile_overview_section", "Current Academic Profile", "Section Break", "talisma_academic_profile_tab"),
				_field("talisma_profile_overview_html", "", "HTML", "talisma_profile_overview_section"),
				_field("talisma_advisor_assignments_section", "Advisor Assignments", "Section Break", "talisma_profile_overview_html"),
				_field("talisma_advisor_assignments_html", "", "HTML", "talisma_advisor_assignments_section"),
				_field("talisma_academic_standing_section", "Academic Standing", "Section Break", "talisma_advisor_assignments_html"),
				_field("talisma_academic_standing_html", "", "HTML", "talisma_academic_standing_section"),
				_field("talisma_degree_audit_section", "Degree Audit", "Section Break", "talisma_academic_standing_html"),
				_field("talisma_degree_audit_html", "", "HTML", "talisma_degree_audit_section"),
				_field("talisma_holds_privacy_tab", "Holds & Privacy", "Tab Break", "talisma_degree_audit_html"),
				_field("talisma_student_holds_section", "Administrative Holds", "Section Break", "talisma_holds_privacy_tab"),
				_field("talisma_student_holds_html", "", "HTML", "talisma_student_holds_section"),
				_field("talisma_privacy_preferences_section", "FERPA & Privacy", "Section Break", "talisma_student_holds_html"),
				_field("talisma_privacy_preferences_html", "", "HTML", "talisma_privacy_preferences_section"),
				_field("talisma_student_history_tab", "History", "Tab Break", "talisma_privacy_preferences_html"),
				_field("talisma_documents_section", "Student Documents", "Section Break", "talisma_student_history_tab"),
				_field("talisma_documents_html", "", "HTML", "talisma_documents_section"),
				_field("talisma_status_history_section", "Status History", "Section Break", "talisma_documents_html"),
				_field("talisma_status_history_html", "", "HTML", "talisma_status_history_section"),
			]
		},
		update=True,
	)

	_set_property("section_break_3", "label", "Student Information", "Data")
	_set_property("section_break_7", "label", "Additional Information", "Data")
	_set_property("last_name", "reqd", 1, "Check")
	_set_property("student_name", "hidden", 0, "Check")
	_set_property("student_name", "read_only", 1, "Check")
	_set_property("student_name", "label", "Student Full Name", "Data")
	_set_property("student_mobile_number", "label", "Phone Number", "Data")
	_set_property("student_email_id", "label", "Email ID", "Data")
	_set_property("address_line_1", "label", "Address", "Data")
	_set_property("pincode", "label", "Postal Code", "Data")
	_set_property("nationality", "options", "Country", "Data")
	_set_property("nationality", "fieldtype", "Link", "Data")
	_set_property("section_break_18", "label", "Family Details", "Data")
	_set_property("section_break_18", "hidden", 0, "Check")
	_set_property("talisma_family_members", "hidden", 0, "Check")
	_set_property("relations_tab", "hidden", 1, "Check")
	_set_property("guardians", "hidden", 1, "Check")
	_set_property("section_break_20", "hidden", 1, "Check")
	_set_property("siblings", "hidden", 1, "Check")
	_set_property("talisma_status_history_section", "label", "Student History", "Data")
	_set_property("talisma_student_history_tab", "label", "Documents", "Data")
	for fieldname in ("talisma_identity_name_section", "talisma_full_name_section"):
		custom_field = frappe.db.exists("Custom Field", {"dt": "Student", "fieldname": fieldname})
		if custom_field:
			frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True)

	meta = frappe.get_meta("Student")
	details_fields = [
		"section_break_3",
		"talisma_student_number",
		"student_name",
		"talisma_identity_name_column_2",
		"first_name",
		"talisma_preferred_name",
		"talisma_identity_name_column_3",
		"middle_name",
		"talisma_pronouns",
		"talisma_identity_name_column_4",
		"last_name",
		"talisma_contact_section",
		"student_email_id",
		"talisma_secondary_email",
		"address_line_1",
		"talisma_contact_column_2",
		"student_mobile_number",
		"talisma_secondary_phone",
		"pincode",
		"talisma_contact_column_3",
		"city",
		"state",
		"country",
		"section_break_7",
		"date_of_birth",
		"gender",
		"talisma_additional_column_2",
		"talisma_ethnic_group",
		"talisma_marital_status",
		"talisma_additional_column_3",
		"blood_group",
		"nationality",
		"section_break_18",
		"talisma_family_members",
	]
	student_views = [
		"talisma_academic_profile_tab",
		"talisma_profile_overview_section",
		"talisma_profile_overview_html",
		"talisma_status_history_section",
		"talisma_status_history_html",
		"talisma_advisor_assignments_section",
		"talisma_advisor_assignments_html",
		"talisma_academic_standing_section",
		"talisma_academic_standing_html",
		"talisma_degree_audit_section",
		"talisma_degree_audit_html",
		"talisma_enrollment_tab",
		"talisma_current_enrollment_section",
		"talisma_current_enrollment_html",
		"talisma_enrollment_history_section",
		"talisma_enrollment_history_html",
		"talisma_course_registration_tab",
		"talisma_course_registration_section",
		"talisma_course_registration_html",
		"talisma_finance_tab",
		"talisma_payment_summary_section",
		"talisma_payment_summary_html",
		"talisma_fee_structure_section",
		"talisma_fee_structure_html",
		"talisma_fee_details_section",
		"talisma_fee_details_html",
		"talisma_refunds_section",
		"talisma_refunds_html",
		"talisma_holds_privacy_tab",
		"talisma_student_holds_section",
		"talisma_student_holds_html",
		"talisma_privacy_preferences_section",
		"talisma_privacy_preferences_html",
		"talisma_student_history_tab",
		"talisma_documents_section",
		"talisma_documents_html",
	]
	visible_fields = set(details_fields + student_views)
	all_fields = [field.fieldname for field in meta.fields]
	missing = visible_fields - set(all_fields)
	if missing:
		frappe.throw(
			_("Student 360 layout fields are missing: {0}").format(", ".join(sorted(missing)))
		)

	for fieldname in visible_fields:
		_set_property(fieldname, "hidden", 0, "Check")
	hidden_fields = [fieldname for fieldname in all_fields if fieldname not in visible_fields]
	for fieldname in hidden_fields:
		_set_property(fieldname, "hidden", 1, "Check")

	field_order = details_fields + hidden_fields + student_views
	make_property_setter(
		"Student", None, "field_order", json.dumps(field_order), "Data", for_doctype=True
	)
	frappe.clear_cache(doctype="Student")


def _field(
	fieldname: str,
	label: str,
	fieldtype: str,
	insert_after: str,
	**values,
) -> dict:
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"insert_after": insert_after,
		"translatable": 0,
		**values,
	}


def _set_property(fieldname: str, property_name: str, value, property_type: str) -> None:
	make_property_setter("Student", fieldname, property_name, value, property_type)


def apply_relations_layout_direct() -> None:
	"""Apply the reduced relations layout without replacing existing Property Setters."""
	_set_existing_property("relations_tab", "hidden", 1)
	_set_existing_property("section_break_18", "label", "Family Details")
	_set_existing_property("section_break_18", "hidden", 0)
	_set_existing_property("talisma_family_members", "hidden", 0)
	_set_existing_property("guardians", "hidden", 1)
	_set_existing_property("section_break_20", "hidden", 1)
	_set_existing_property("siblings", "hidden", 1)

	setter = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Student", "property": "field_order"},
		["name", "value"],
		as_dict=True,
	)
	if not setter:
		frappe.throw(_("The Student field-order Property Setter is missing."))
	order = json.loads(setter.value)
	family = ["section_break_18", "talisma_family_members"]
	removed = ["relations_tab", "guardians", "section_break_20", "siblings"]
	order = [field for field in order if field not in family + removed]
	insert_at = order.index("country") + 1
	order[insert_at:insert_at] = family
	hidden_at = order.index("talisma_academic_profile_tab")
	order[hidden_at:hidden_at] = removed
	frappe.db.set_value("Property Setter", setter.name, "value", json.dumps(order), update_modified=False)
	frappe.clear_cache(doctype="Student")


def _set_existing_property(fieldname: str, property_name: str, value) -> None:
	setter = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Student", "field_name": fieldname, "property": property_name},
		"name",
	)
	if setter:
		frappe.db.set_value("Property Setter", setter, "value", value, update_modified=False)
		return
	property_type = "Check" if property_name == "hidden" else "Data"
	make_property_setter("Student", fieldname, property_name, value, property_type)


@frappe.whitelist()
def get_student_360(student: str) -> dict:
	"""Return permission-aware Student 360 data from authoritative linked records."""
	_require_demo_site()
	student_doc = frappe.get_doc("Student", student)
	if not frappe.has_permission("Student", "read", doc=student_doc):
		frappe.throw(_("You do not have permission to view this student."), frappe.PermissionError)

	from talisma_sis.curriculum import get_degree_audit
	return {
		"student": student_doc.name,
		"student_name": student_doc.student_name,
		"student_records": _student_records_view(student_doc),
		"degree_audit": get_degree_audit(student_doc.name),
		"enrollment": _enrollment_view(student_doc),
		"course_registration": _course_registration_view(student_doc),
		"finance": _finance_view(student_doc),
	}


def _student_records_view(student_doc) -> dict:
	from talisma_sis.academics import refresh_academic_standing
	from talisma_sis.student_records import active_holds

	student = student_doc.name
	refresh_academic_standing(student)
	programs = _permitted_rows(
		"Talisma Student Academic Program",
		student,
		["name", "degree", "program", "affiliation_type", "primary_program", "program_version", "catalog_year", "academic_level", "start_term", "expected_graduation_term", "status", "effective_from", "effective_to"],
		"primary_program desc, effective_from desc",
	)
	advisors = _permitted_rows(
		"Talisma Student Advisor Assignment",
		student,
		["name", "advisor", "advisor_type", "program", "academic_unit", "primary_advisor", "status", "effective_from", "effective_to", "end_reason"],
		"primary_advisor desc, effective_from desc",
	)
	advisor_names = {
		row.advisor: frappe.db.get_value("Instructor", row.advisor, "instructor_name")
		for row in advisors
		if row.advisor
	}
	academic_unit_names = {
		row.academic_unit: frappe.db.get_value("Talisma Academic Unit", row.academic_unit, "unit_name")
		for row in advisors
		if row.academic_unit
	}
	for row in advisors:
		row["advisor_name"] = advisor_names.get(row.advisor) or row.advisor
		row["academic_unit_name"] = academic_unit_names.get(row.academic_unit) or row.academic_unit
	standings = _permitted_rows(
		"Talisma Student Academic Standing",
		student,
		["name", "academic_term", "program", "standing", "term_gpa", "cumulative_gpa", "attempted_credits", "earned_credits", "effective_date"],
		"effective_date desc",
	)
	holds = (
		active_holds(student)
		if frappe.has_permission("Talisma Student Hold", "read")
		else []
	)
	privacy = _permitted_rows(
		"Talisma Student Privacy Preference",
		student,
		["name", "ferpa_restriction", "directory_information_consent", "restriction_scope", "effective_from", "effective_to", "consent_source", "emergency_disclosure_permission"],
		"effective_from desc",
	)
	documents = _permitted_rows(
		"Talisma Student Document",
		student,
		["name", "document_type", "required", "status", "due_date", "document_file", "expiry_date", "uploaded_by", "uploaded_on", "rejection_reason"],
		"required desc, due_date asc, creation asc",
	)
	for row in documents:
		placeholder = frappe.db.get_value(
			"Talisma Student Document Type",
			row.document_type,
			["description", "allowed_extensions", "max_file_size_mb"],
			as_dict=True,
		) or {}
		row.update(placeholder)
	statuses = _permitted_rows(
		"Talisma Student Status History",
		student,
		["name", "previous_status", "status", "reason", "academic_term", "effective_from", "effective_to", "source", "changed_by", "transition_timestamp", "creation"],
		"effective_from desc, creation desc",
	)
	classifications = _permitted_rows(
		"Talisma Student Classification History",
		student,
		["name", "residency_classification", "tuition_residency", "student_type", "academic_level", "class_standing", "cohort", "campus", "academic_term", "effective_from", "effective_to"],
		"effective_from desc",
	)
	names = _permitted_rows(
		"Talisma Student Name History",
		student,
		["name", "first_name", "middle_name", "last_name", "preferred_name", "effective_from", "effective_to", "reason", "source"],
		"effective_from desc",
	)
	primary_program = next((row for row in programs if row.primary_program and row.status == "Active"), None)
	as_of = getdate(today())
	primary_advisor = next((
		row for row in advisors
		if row.primary_advisor
		and row.status == "Active"
		and row.effective_from
		and getdate(row.effective_from) <= as_of
		and (not row.effective_to or getdate(row.effective_to) >= as_of)
	), None)
	current_standing = standings[0] if standings else None
	current_privacy = privacy[0] if privacy else None
	return {
		"summary": {
			"record_status": student_doc.get("talisma_record_status"),
			"primary_program": primary_program.program if primary_program else student_doc.get("talisma_primary_program"),
			"academic_level": student_doc.get("talisma_academic_level"),
			"advisor": primary_advisor.advisor_name if primary_advisor else None,
			"standing": current_standing.standing if current_standing else None,
			"active_holds": len(holds),
			"privacy_restriction": bool(current_privacy and current_privacy.ferpa_restriction),
		},
		"programs": programs,
		"advisors": advisors,
		"standings": standings,
		"holds": holds,
		"privacy": privacy,
		"documents": documents,
		"statuses": statuses,
		"classifications": classifications,
		"names": names,
	}


def _permitted_rows(doctype: str, student: str, fields: list[str], order_by: str) -> list:
	if not frappe.has_permission(doctype, "read"):
		return []
	return frappe.get_list(
		doctype,
		filters={"student": student},
		fields=fields,
		order_by=order_by,
	)


def _enrollment_view(student_doc) -> dict:
	if not frappe.has_permission("Program Enrollment", "read"):
		return {"restricted": True, "current": None, "records": []}

	rows = frappe.get_all(
		"Program Enrollment",
		filters={"student": student_doc.name},
		fields=[
			"name",
			"program",
			"academic_year",
			"academic_term",
			"enrollment_date",
			"docstatus",
			"talisma_registration_status",
			"talisma_curriculum_version",
			"talisma_campus",
			"creation",
		],
		order_by="enrollment_date desc, creation desc",
	)
	programs = {
		row.program: frappe.db.get_value(
			"Program", row.program, ["program_name", "talisma_academic_unit"], as_dict=True
		)
		for row in rows
	}
	academic_unit_names = {
		program.get("talisma_academic_unit"): frappe.db.get_value(
			"Talisma Academic Unit", program.get("talisma_academic_unit"), "unit_name"
		)
		for program in programs.values()
		if program and program.get("talisma_academic_unit")
	}
	term_starts = {
		row.academic_term: frappe.db.get_value("Academic Term", row.academic_term, "term_start_date")
		for row in rows
		if row.academic_term
	}
	campus_names = {
		row.talisma_campus: frappe.db.get_value("Talisma Campus", row.talisma_campus, "campus_name")
		for row in rows
		if row.talisma_campus
	}
	records = []
	for index, row in enumerate(rows):
		program = programs.get(row.program) or {}
		status = _enrollment_status(row, student_doc)
		academic_unit = program.get("talisma_academic_unit")
		records.append({
			"name": row.name,
			"academic_unit": academic_unit,
			"academic_unit_name": academic_unit_names.get(academic_unit) or academic_unit,
			"program": row.program,
			"program_name": program.get("program_name") or row.program,
			"program_version": row.talisma_curriculum_version,
			"campus": row.talisma_campus,
			"campus_name": campus_names.get(row.talisma_campus) or row.talisma_campus,
			"expected_start_date": term_starts.get(row.academic_term),
			"student_start_date": row.enrollment_date,
			"enrollment_status": status,
			"academic_year": row.academic_year,
			"academic_term": row.academic_term,
			"primary_program": index == 0 and row.docstatus != 2,
			"docstatus": row.docstatus,
			"remarks": "",
		})
	current = next((row for row in records if row["enrollment_status"] != "Cancelled"), None)
	return {"restricted": False, "current": current, "records": records}


def _enrollment_status(row, student_doc) -> str:
	if row.docstatus == 2:
		return "Cancelled"
	if row.enrollment_date and getdate(row.enrollment_date) > getdate(today()):
		return "Planned"
	return student_doc.get("talisma_enrollment_status") or "Active"


def _course_registration_view(student_doc) -> dict:
	if not frappe.has_permission("Course Enrollment", "read"):
		return {"restricted": True, "records": []}

	rows = frappe.get_all(
		"Course Enrollment",
		filters={"student": student_doc.name},
		fields=[
			"name",
			"program_enrollment",
			"program",
			"course",
			"enrollment_date",
			"talisma_course_section",
			"talisma_attempt_number",
			"talisma_academic_term",
			"talisma_grade_earned",
			"talisma_grade_points",
			"talisma_completion_status",
			"talisma_status_date",
			"talisma_status_reason",
			"creation",
		],
		order_by="enrollment_date desc, creation desc",
	)
	courses = {
		row.course: frappe.db.get_value(
			"Course",
			row.course,
			["course_name", "talisma_credit_hours", "talisma_effective_term"],
			as_dict=True,
		)
		for row in rows
	}
	section_names = {row.talisma_course_section for row in rows if row.talisma_course_section}
	sections = {
		name: frappe.db.get_value(
			"Talisma Class Section",
			name,
			[
				"talisma_section_status",
				"talisma_campus",
				"talisma_section_number",
				"talisma_primary_instructor",
				"student_group_name",
			],
			as_dict=True,
		)
		for name in section_names
	}
	campus_ids = {
		section.get("talisma_campus")
		for section in sections.values()
		if section and section.get("talisma_campus")
	}
	campus_names = {
		campus: frappe.db.get_value("Talisma Campus", campus, "campus_name")
		for campus in campus_ids
	}
	instructor_ids = {
		section.get("talisma_primary_instructor")
		for section in sections.values()
		if section and section.get("talisma_primary_instructor")
	}
	instructor_names = {
		instructor: frappe.db.get_value("Instructor", instructor, "instructor_name")
		for instructor in instructor_ids
	}
	grades = {
		row.course: row.grade
		for row in frappe.get_all(
			"Assessment Result",
			filters={"student": student_doc.name, "docstatus": 1},
			fields=["course", "grade"],
			order_by="modified asc",
		)
		if row.course and row.grade
	}
	records = []
	for row in rows:
		course = courses.get(row.course) or {}
		section = sections.get(row.talisma_course_section) or {}
		records.append({
			"name": row.name,
			"program_enrollment": row.program_enrollment,
			"course_code": row.course,
			"course_name": course.get("course_name") or row.course,
			"course_status": section.get("talisma_section_status") or "Registered",
			"credit_hours": course.get("talisma_credit_hours"),
			"effective_term": row.talisma_academic_term or course.get("talisma_effective_term"),
			"instructor": section.get("talisma_primary_instructor"),
			"instructor_name": instructor_names.get(section.get("talisma_primary_instructor")) or section.get("talisma_primary_instructor"),
			"campus": section.get("talisma_campus"),
			"campus_name": campus_names.get(section.get("talisma_campus")) or section.get("talisma_campus"),
			"section": section.get("student_group_name") or section.get("talisma_section_number") or row.talisma_course_section,
			"course_section": row.talisma_course_section,
			"registration_date": row.enrollment_date,
			"attempt_number": row.talisma_attempt_number or 1,
			"completion_status": row.talisma_completion_status or "In Progress",
			"grade": row.talisma_grade_earned or grades.get(row.course),
			"grade_points": row.talisma_grade_points,
			"status_date": row.talisma_status_date,
			"status_reason": row.talisma_status_reason,
		})
	return {"restricted": False, "records": records}


def _finance_view(student_doc) -> dict:
	from talisma_sis.finance import get_student_account

	return get_student_account(student_doc.name)


def _require_demo_site() -> None:
	if frappe.local.site != DEMO_SITE:
		frappe.throw(_("Student 360 is restricted to {0}.").format(DEMO_SITE))
