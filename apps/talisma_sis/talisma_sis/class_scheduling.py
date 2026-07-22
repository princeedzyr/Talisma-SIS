"""US class scheduling engine with cohorts separated from class sections."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import cint, flt, get_timedelta, getdate, now, today


DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
ACTIVE_CLASS_STATUSES = {"Planned", "Open", "Full", "Waitlisted"}


def waitlist_permission_query(user: str | None = None) -> str:
	user = user or frappe.session.user
	if {"System Manager", "Academics User"}.intersection(frappe.get_roles(user)):
		return ""
	from talisma_sis.student_documents import student_for_user
	student = student_for_user(user)
	return f"`tabTalisma Class Waitlist Entry`.`student` = {frappe.db.escape(student)}" if student else "1=0"


def waitlist_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	if {"System Manager", "Academics User"}.intersection(frappe.get_roles(user)):
		return True
	from talisma_sis.student_documents import student_for_user
	return bool(permission_type == "read" and student_for_user(user) == doc.student)


def configure_class_scheduling() -> None:
	create_custom_fields({
		"Student Group": [
			_field("talisma_cohort_general_section", "General Information", "Section Break", "", "student_group_name"),
			_field("talisma_group_type", "Group Type", "Select", "Academic Cohort\nOrientation Group\nHonors Group\nScholarship Group\nStudent Club\nSports Team\nAdvising Group\nCustom", "student_group_name", reqd=1, default="Academic Cohort"),
			_field("talisma_status", "Status", "Select", "Active\nInactive", "talisma_group_type", reqd=1, default="Active"),
			_field("talisma_cohort_general_column_2", "", "Column Break", "", "talisma_status"),
			_field("talisma_cohort_purpose", "Cohort Purpose", "Select", "Admissions\nAcademic Progress\nStudent Services\nGraduation\nReporting\nOther", "student_group_name"),
			_field("talisma_cohort_campus", "Campus", "Link", "Talisma Campus", "talisma_cohort_purpose"),
			_field("talisma_cohort_description", "Description", "Small Text", "", "talisma_cohort_purpose"),
			_field("talisma_effective_from", "Effective From", "Date", "", "talisma_cohort_description"),
			_field("talisma_effective_to", "Effective To", "Date", "", "talisma_effective_from"),
			_field("talisma_cohort_selection_section", "Student Selection", "Section Break", "", "program"),
			_field("talisma_cohort_selection_html", "", "HTML", "", "talisma_cohort_selection_section"),
		],
		"Student Group Student": [
			_field("talisma_program", "Program", "Link", "Program", "student_name", read_only=1, in_list_view=1),
			_field("talisma_academic_term", "Academic Term", "Link", "Academic Term", "talisma_program", read_only=1, in_list_view=1),
			_field("talisma_enrollment_status", "Enrollment Status", "Data", "", "talisma_academic_term", read_only=1, in_list_view=1),
		],
		"Instructor": [
			_field("talisma_max_weekly_contact_hours", "Maximum Weekly Contact Hours", "Float", "", "instructor_name", default=20),
		],
		"Course Enrollment": [
			_field("talisma_course_section", "Course Section / CRN", "Link", "Talisma Class Section", "course"),
		],
		"Course Schedule": [
			_field("talisma_class_section", "Class Section", "Link", "Talisma Class Section", "student_group", in_list_view=1),
		],
	}, update=True)
	for fieldname in (
		"talisma_class_details_section", "talisma_academic_unit", "talisma_primary_instructor",
		"talisma_section_number", "talisma_crn", "talisma_delivery_method", "talisma_section_status",
		"talisma_class_start_date", "talisma_class_end_date", "talisma_periods_section", "talisma_periods",
		"talisma_capacity_section", "talisma_allow_waitlist", "talisma_waitlist_capacity",
		"talisma_registered_students", "talisma_available_seats", "talisma_waitlisted_students",
		"talisma_remaining_waitlist_seats", "talisma_weekly_contact_hours", "talisma_assigned_credit_hours",
		"talisma_meeting_days", "talisma_start_time", "talisma_end_time", "talisma_room",
		"talisma_schedule_location_section", "talisma_schedule_location_column_2",
		"talisma_capacity_column_2", "talisma_capacity_column_3",
		"talisma_campus", "talisma_class_details_section", "talisma_selection_html",
	):
		name = frappe.db.get_value("Custom Field", {"dt": "Student Group", "fieldname": fieldname}, "name")
		if name:
			frappe.db.set_value("Custom Field", name, "hidden", 1, update_modified=False)
	for fieldname, prop, value, prop_type in (
		("talisma_class_details_section", "reqd", 0, "Check"),

		("talisma_class_details_section", "hidden", 1, "Check"),
		("talisma_schedule_location_section", "reqd", 0, "Check"),

		("talisma_schedule_location_section", "hidden", 1, "Check"),
		("talisma_periods_section", "reqd", 0, "Check"),

		("talisma_periods_section", "hidden", 1, "Check"),
		("talisma_periods", "reqd", 0, "Check"),

		("talisma_periods", "hidden", 1, "Check"),
		("max_strength", "reqd", 0, "Check"),

		("max_strength", "hidden", 1, "Check"),
		("waitlist_capacity", "reqd", 0, "Check"),

		("waitlist_capacity", "hidden", 1, "Check"),
		("room", "reqd", 0, "Check"),

		("room", "hidden", 1, "Check"),
		("talisma_primary_instructor", "reqd", 0, "Check"),

		("talisma_primary_instructor", "hidden", 1, "Check"),
		("talisma_registered_students", "reqd", 0, "Check"),

		("talisma_registered_students", "hidden", 1, "Check"),
		("talisma_waitlisted_students", "reqd", 0, "Check"),

		("talisma_waitlisted_students", "hidden", 1, "Check"),
		("talisma_available_seats", "reqd", 0, "Check"),

		("talisma_available_seats", "hidden", 1, "Check"),
		("talisma_remaining_waitlist_seats", "reqd", 0, "Check"),

		("talisma_remaining_waitlist_seats", "hidden", 1, "Check"),
		("talisma_weekly_contact_hours", "reqd", 0, "Check"),

		("talisma_weekly_contact_hours", "hidden", 1, "Check"),
		("talisma_assigned_credit_hours", "reqd", 0, "Check"),

		("talisma_assigned_credit_hours", "hidden", 1, "Check"),
		("talisma_allow_waitlist", "reqd", 0, "Check"),

		("talisma_allow_waitlist", "hidden", 1, "Check"),
		("instructor", "reqd", 0, "Check"),
		("instructor", "hidden", 1, "Check"),
		("student_group_name", "label", "Group Name", "Data"),
		("group_based_on", "reqd", 0, "Check"),

		("group_based_on", "hidden", 1, "Check"),
		("academic_year", "reqd", 0, "Check"),
		("course", "hidden", 1, "Check"),
		("batch", "hidden", 1, "Check"),
		("student_category", "hidden", 1, "Check"),
		("disabled", "hidden", 1, "Check"),
		("talisma_cohort_purpose", "hidden", 1, "Check"),
		("talisma_cohort_description", "hidden", 1, "Check"),
		("talisma_effective_from", "hidden", 1, "Check"),
		("talisma_effective_to", "hidden", 1, "Check"),
		("talisma_academic_unit", "reqd", 0, "Check"),

		("talisma_academic_unit", "hidden", 0, "Check"),
		("talisma_group_type", "label", "Group Type", "Data"),
		("talisma_status", "label", "Status", "Data"),
		("talisma_cohort_campus", "label", "Campus", "Data"),
		("section_break_12", "hidden", 1, "Check"),
		("instructors", "hidden", 1, "Check"),
		("get_students", "hidden", 1, "Check"),
		("section_break_6", "label", "Group Members", "Data"),
		("students", "label", "Group Members", "Data"),
	):
		make_property_setter("Student Group", fieldname, prop, value, prop_type)
	for fieldname, prop, value, prop_type in (
		("student", "label", "Student Number", "Data"),
		("active", "hidden", 1, "Check"),
	):
		make_property_setter("Student Group Student", fieldname, prop, value, prop_type)
	for _field in ("talisma_class_details_section", "talisma_schedule_location_section", "talisma_periods_section", "talisma_periods", "max_strength", "waitlist_capacity", "room", "talisma_primary_instructor", "instructor", "talisma_registered_students", "talisma_waitlisted_students", "talisma_available_seats", "talisma_remaining_waitlist_seats", "talisma_weekly_contact_hours", "talisma_assigned_credit_hours", "talisma_allow_waitlist"):
		make_property_setter("Student Group", _field, "hidden", 1, "Check")
	make_property_setter("Student Group", None, "field_order",
		'["student_group_name", "talisma_group_type", "talisma_status", "talisma_cohort_campus", "academic_year", "academic_term", "talisma_academic_unit", "program", "talisma_cohort_selection_section", "talisma_cohort_selection_html", "section_break_6", "students"]',
		"Data", for_doctype=True,
	)
	_backfill_existing_sections()
	_detach_legacy_class_fields()
	frappe.clear_cache(doctype="Student Group")
	frappe.clear_cache(doctype="Talisma Class Section")


def ensure_cohort_filter_field() -> None:
	"""Add cohort-only fields once without rewriting existing custom fields."""
	student_group_fields = [
		_field("talisma_cohort_general_section", "General Information", "Section Break", "", "student_group_name"),
		_field("talisma_group_type", "Group Type", "Select", "Academic Cohort\nOrientation Group\nHonors Group\nScholarship Group\nStudent Club\nSports Team\nAdvising Group\nCustom", "student_group_name", reqd=1, default="Academic Cohort"),
		_field("talisma_status", "Status", "Select", "Active\nInactive", "talisma_group_type", reqd=1, default="Active"),
		_field("talisma_cohort_general_column_2", "", "Column Break", "", "talisma_status"),
		_field("talisma_cohort_campus", "Campus", "Link", "Talisma Campus", "talisma_cohort_general_column_2"),
		_field("talisma_cohort_selection_section", "Student Selection", "Section Break", "", "program"),
		_field("talisma_cohort_selection_html", "", "HTML", "", "talisma_cohort_selection_section"),
	]
	student_group_student_fields = [
		_field("talisma_program", "Program", "Link", "Program", "student_name", read_only=1, in_list_view=1),
		_field("talisma_academic_term", "Academic Term", "Link", "Academic Term", "talisma_program", read_only=1, in_list_view=1),
		_field("talisma_enrollment_status", "Enrollment Status", "Data", "", "talisma_academic_term", read_only=1, in_list_view=1),
	]
	missing = [field for field in student_group_fields if not frappe.db.exists("Custom Field", {"dt": "Student Group", "fieldname": field["fieldname"]})]
	missing_student_fields = [field for field in student_group_student_fields if not frappe.db.exists("Custom Field", {"dt": "Student Group Student", "fieldname": field["fieldname"]})]
	create_custom_fields(
		{"Student Group": missing, "Student Group Student": missing_student_fields},
		update=False,
	) if missing or missing_student_fields else None
	frappe.clear_cache(doctype="Student Group")


def configure_cohort_ui() -> None:
	"""Apply the logical Student Group layout and remove class-scheduling fields."""
	legacy = ("group_based_on", "course", "batch", "student_category", "disabled", "instructors", "get_students", "max_strength", "talisma_waitlist_capacity", "talisma_room", "talisma_primary_instructor", "talisma_class_details_section", "talisma_schedule_location_section", "talisma_periods_section", "talisma_periods", "talisma_registered_students", "talisma_waitlisted_students", "talisma_available_seats", "talisma_remaining_waitlist_seats", "talisma_weekly_contact_hours", "talisma_assigned_credit_hours", "talisma_allow_waitlist", "talisma_class_start_date", "talisma_class_end_date")
	legacy_list_fields = (
		"group_based_on",
		"course",
		"batch",
		"student_category",
		"talisma_crn",
		"talisma_section_number",
		"talisma_section_status",
		"talisma_delivery_method",
		"talisma_room",
		"talisma_primary_instructor",
	)
	cohort_list_fields = (
		"talisma_group_type",
		"talisma_status",
		"talisma_cohort_campus",
		"academic_year",
		"academic_term",
		"talisma_academic_unit",
		"program",
	)
	quoted = ", ".join("'" + fieldname + "'" for fieldname in legacy)
	frappe.db.sql(f"UPDATE `tabProperty Setter` SET value='1' WHERE doc_type='Student Group' AND property='hidden' AND field_name IN ({quoted})")
	frappe.db.sql(f"UPDATE `tabProperty Setter` SET value='0' WHERE doc_type='Student Group' AND property='reqd' AND field_name IN ({quoted})")
	frappe.db.sql("UPDATE `tabDocField` SET reqd=0 WHERE parent='Student Group' AND fieldname IN ('group_based_on', 'course', 'batch', 'student_category', 'max_strength')")
	frappe.db.sql("UPDATE `tabDocField` SET in_list_view=0, in_standard_filter=0 WHERE parent='Student Group' AND fieldname IN ('group_based_on', 'course', 'batch', 'student_category')")
	frappe.db.sql("UPDATE `tabCustom Field` SET hidden=1, reqd=0, in_list_view=0, in_standard_filter=0 WHERE dt='Student Group' AND fieldname IN ('talisma_waitlist_capacity', 'talisma_room', 'talisma_primary_instructor', 'talisma_class_details_section', 'talisma_schedule_location_section', 'talisma_periods_section', 'talisma_periods', 'talisma_registered_students', 'talisma_waitlisted_students', 'talisma_available_seats', 'talisma_remaining_waitlist_seats', 'talisma_weekly_contact_hours', 'talisma_assigned_credit_hours', 'talisma_allow_waitlist', 'talisma_class_start_date', 'talisma_class_end_date', 'talisma_crn', 'talisma_section_number', 'talisma_delivery_method', 'talisma_section_status', 'talisma_campus', 'talisma_capacity_section', 'talisma_capacity_column_2', 'talisma_capacity_column_3', 'talisma_schedule_location_column_2', 'talisma_cohort_general_column_2')")
	frappe.db.sql("UPDATE `tabCustom Field` SET hidden=0, label='' WHERE dt='Student Group' AND fieldname='talisma_cohort_general_section'")
	frappe.db.sql("UPDATE `tabCustom Field` SET in_list_view=1, in_standard_filter=1 WHERE dt='Student Group' AND fieldname IN ('talisma_group_type', 'talisma_status', 'talisma_cohort_campus', 'talisma_academic_unit')")
	frappe.db.sql("UPDATE `tabDocField` SET in_list_view=1, in_standard_filter=1 WHERE parent='Student Group' AND fieldname IN ('academic_year', 'academic_term', 'program')")
	for fieldname, prop, value, prop_type in (
		("student_group_name", "label", "Group Name", "Data"),
		("talisma_group_type", "label", "Group Type", "Data"),
		("talisma_status", "label", "Status", "Data"),
		("talisma_cohort_campus", "label", "Campus", "Data"),
		("talisma_cohort_general_section", "hidden", 0, "Check"),
		("talisma_cohort_general_section", "label", "", "Data"),
		("group_based_on", "reqd", 0, "Check"),
		("academic_year", "reqd", 0, "Check"),
		("talisma_academic_unit", "reqd", 0, "Check"),
		("section_break_6", "label", "Group Members", "Data"),
		("students", "label", "Group Members", "Data"),
	):
		make_property_setter("Student Group", fieldname, prop, value, prop_type)
	for fieldname in legacy_list_fields:
		make_property_setter("Student Group", fieldname, "in_list_view", 0, "Check")
		make_property_setter("Student Group", fieldname, "in_standard_filter", 0, "Check")
	for fieldname in cohort_list_fields:
		make_property_setter("Student Group", fieldname, "in_list_view", 1, "Check")
		make_property_setter("Student Group", fieldname, "in_standard_filter", 1, "Check")
	make_property_setter("Student Group Student", "student", "label", "Student Number", "Data")
	make_property_setter("Student Group Student", "active", "hidden", 1, "Check")
	make_property_setter("Student Group", None, "field_order", '["talisma_cohort_general_section", "student_group_name", "talisma_group_type", "talisma_status", "talisma_cohort_campus", "academic_year", "academic_term", "talisma_academic_unit", "program", "talisma_cohort_selection_section", "talisma_cohort_selection_html", "section_break_6", "students"]', "Data", for_doctype=True)
	frappe.clear_cache(doctype="Student Group")

@frappe.whitelist()
def get_cohort_students(
	talisma_cohort_campus: str | None = None,
	academic_year: str | None = None,
	academic_term: str | None = None,
	talisma_academic_unit: str | None = None,
	program: str | None = None,
) -> list[dict]:
	"""Return students matching the cohort filters for the member table."""
	student_filters = {"talisma_home_campus": talisma_cohort_campus} if talisma_cohort_campus else {}
	student_meta = frappe.get_meta("Student")
	if student_meta.has_field("enabled"):
		student_filters["enabled"] = 1
	student_names = frappe.get_all("Student", filters=student_filters, pluck="name")
	if not student_names:
		return []

	enrollment_filters = {"student": ("in", student_names), "docstatus": ("!=", 2)}
	for fieldname, value in (
		("academic_year", academic_year),
		("academic_term", academic_term),
		("program", program),
	):
		if value:
			enrollment_filters[fieldname] = value
	if talisma_academic_unit:
		programs = frappe.get_all("Program", filters={"talisma_academic_unit": talisma_academic_unit}, pluck="name")
		if not programs:
			return []
		enrollment_filters["program"] = ("in", programs)
	if any((academic_year, academic_term, talisma_academic_unit, program)):
		enrollment_rows = frappe.get_all(
			"Program Enrollment",
			filters=enrollment_filters,
			fields=["student", "program", "academic_term"],
			order_by="creation desc",
		)
		student_names = list(dict.fromkeys(row.student for row in enrollment_rows))
		if not student_names:
			return []
	else:
		enrollment_rows = []

	students = frappe.get_all(
		"Student",
		filters={"name": ("in", student_names)},
		fields=["name as student", "student_name", "talisma_enrollment_status as enrollment_status"],
		order_by="student_name asc, name asc",
	)
	enrollment_by_student = {}
	for row in enrollment_rows:
		enrollment_by_student.setdefault(row.student, row)
	for student in students:
		enrollment = enrollment_by_student.get(student.student)
		student["program"] = enrollment.program if enrollment else None
		student["academic_term"] = enrollment.academic_term if enrollment else None
	return students


def before_validate_class_schedule(doc, method=None) -> None:
	doc.talisma_section_number = doc.talisma_section_number or _next_section(doc.academic_term, doc.course)
	doc.talisma_crn = doc.talisma_crn or _next_crn()
	doc.student_group_name = doc.student_group_name or f"{doc.course}-{doc.academic_term}-{doc.talisma_section_number}"
	if doc.course and not doc.talisma_academic_unit:
		doc.talisma_academic_unit = frappe.db.get_value("Course", doc.course, "talisma_academic_unit")
	if doc.academic_term:
		term = frappe.db.get_value("Academic Term", doc.academic_term, ["term_start_date", "term_end_date"], as_dict=True)
		if term:
			doc.talisma_class_start_date = doc.talisma_class_start_date or term.term_start_date
			doc.talisma_class_end_date = doc.talisma_class_end_date or term.term_end_date
	_sync_compatibility_group(doc)


def before_validate_student_group(doc, method=None) -> None:
	"""Populate readable member names before Education's legacy validator runs."""
	for row in doc.get("students") or []:
		if row.student and not row.student_name:
			row.student_name = frappe.db.get_value("Student", row.student, "student_name") or row.student


def validate_student_group(doc, method=None) -> None:
	"""Keep Student Group dedicated to cohort membership, not class scheduling."""
	if doc.flags.get("ignore_validate"):
		return
	if doc.group_based_on == "Course" or doc.course:
		frappe.throw(_("Student Groups are cohorts. Create course sections in Class Scheduling."))
	if doc.get("instructors"):
		frappe.throw(_("Instructors belong to Class Scheduling, not Student Cohorts."))
	seen = set()
	for row in doc.get("students") or []:
		if not row.student:
			continue
		if row.student in seen:
			frappe.throw(_("Student {0} is already a member of this group.").format(frappe.bold(row.student)))
		seen.add(row.student)
		profile = frappe.db.get_value(
			"Student", row.student,
			["student_name", "talisma_enrollment_status"], as_dict=True,
		)
		if profile:
			row.student_name = profile.student_name
			row.talisma_enrollment_status = profile.talisma_enrollment_status
		row.talisma_program = row.talisma_program or doc.program
		row.talisma_academic_term = row.talisma_academic_term or doc.academic_term
	if doc.get("talisma_effective_from") and doc.get("talisma_effective_to") and doc.talisma_effective_from > doc.talisma_effective_to:
		frappe.throw(_("Effective From must be on or before Effective To."))


def validate_class_schedule(doc, method=None) -> None:
	for fieldname in ("academic_term", "course", "talisma_academic_unit", "talisma_primary_instructor", "talisma_section_number", "talisma_class_start_date", "talisma_class_end_date"):
		if not doc.get(fieldname):
			frappe.throw(_("{0} is required for Class Scheduling.").format(doc.meta.get_label(fieldname)))
	if cint(doc.max_strength) <= 0:
		frappe.throw(_("Capacity must be greater than zero."))
	if doc.talisma_allow_waitlist and cint(doc.talisma_waitlist_capacity) <= 0:
		frappe.throw(_("Waitlist Capacity must be greater than zero when waitlisting is enabled."))
	if not doc.talisma_allow_waitlist:
		doc.talisma_waitlist_capacity = 0
	_validate_master_links(doc)
	_validate_term_dates(doc)
	_validate_duplicate(doc)
	_validate_periods(doc)
	_validate_instructor_conflicts(doc)
	_validate_workload(doc)
	set_enrollment_summary(doc)


def set_enrollment_summary(doc) -> None:
	registered = sum(1 for row in doc.students if row.active)
	waitlisted = frappe.db.count("Talisma Class Waitlist Entry", {"class_schedule": doc.name, "status": "Waiting"}) if not doc.is_new() else 0
	doc.talisma_registered_students = registered
	doc.talisma_available_seats = max(cint(doc.max_strength) - registered, 0)
	doc.talisma_waitlisted_students = waitlisted
	doc.talisma_remaining_waitlist_seats = max(cint(doc.talisma_waitlist_capacity) - waitlisted, 0) if doc.talisma_allow_waitlist else 0
	doc.talisma_weekly_contact_hours = _weekly_hours(doc.talisma_periods)
	doc.talisma_assigned_credit_hours = flt(frappe.db.get_value("Course", doc.course, "talisma_credit_hours"))
	if doc.talisma_section_status in {"Full", "Waitlisted", "Open"}:
		doc.talisma_section_status = "Waitlisted" if waitlisted else ("Full" if not doc.talisma_available_seats else "Open")


def sync_enrollment_summary(class_schedule: str) -> None:
	if not class_schedule or not frappe.db.exists("Talisma Class Section", class_schedule):
		return
	doc = frappe.get_doc("Talisma Class Section", class_schedule)
	set_enrollment_summary(doc)
	frappe.db.set_value("Talisma Class Section", doc.name, {
		"talisma_registered_students": doc.talisma_registered_students,
		"talisma_available_seats": doc.talisma_available_seats,
		"talisma_waitlisted_students": doc.talisma_waitlisted_students,
		"talisma_remaining_waitlist_seats": doc.talisma_remaining_waitlist_seats,
		"talisma_section_status": doc.talisma_section_status,
	}, update_modified=False)


def add_to_waitlist(section, program_enrollment) -> dict:
	student = program_enrollment.student
	existing = frappe.db.get_value("Talisma Class Waitlist Entry", {"class_schedule": section.name, "student": student, "status": "Waiting"}, "name")
	if existing:
		return {"waitlisted": True, "name": existing, "position": frappe.db.get_value("Talisma Class Waitlist Entry", existing, "position")}
	count = frappe.db.count("Talisma Class Waitlist Entry", {"class_schedule": section.name, "status": "Waiting"})
	if not section.talisma_allow_waitlist or count >= cint(section.talisma_waitlist_capacity):
		frappe.throw(_("No seats or waitlist positions are available."))
	doc = frappe.get_doc({
		"doctype": "Talisma Class Waitlist Entry", "class_schedule": section.name,
		"student": student, "program_enrollment": program_enrollment.name,
		"course": section.course, "academic_term": section.academic_term,
		"position": count + 1, "status": "Waiting", "joined_on": now(),
	}).insert(ignore_permissions=True)
	sync_enrollment_summary(section.name)
	return {"waitlisted": True, "name": doc.name, "position": doc.position}


def promote_waitlist(class_schedule: str) -> str | None:
	section = frappe.get_doc("Talisma Class Section", class_schedule)
	if sum(1 for row in section.students if row.active) >= cint(section.max_strength):
		return None
	entry = frappe.db.get_value("Talisma Class Waitlist Entry", {"class_schedule": class_schedule, "status": "Waiting"}, "name", order_by="position asc, joined_on asc")
	if not entry:
		sync_enrollment_summary(class_schedule)
		return None
	wait = frappe.get_doc("Talisma Class Waitlist Entry", entry)
	if not frappe.db.exists("Course Enrollment", {"program_enrollment": wait.program_enrollment, "student": wait.student, "course": wait.course, "talisma_completion_status": ("not in", ["Dropped", "Withdrawn"])}):
		frappe.get_doc({"doctype":"Course Enrollment", "program_enrollment":wait.program_enrollment, "student":wait.student, "course":wait.course, "enrollment_date":today(), "talisma_course_section":class_schedule}).insert(ignore_permissions=True)
	if not any(row.student == wait.student and row.active for row in section.students):
		section.append("students", {"student": wait.student, "active": 1})
		section.save(ignore_permissions=True)
	wait.db_set({"status":"Promoted", "promoted_on":now()}, update_modified=True)
	for position, name in enumerate(frappe.get_all("Talisma Class Waitlist Entry", filters={"class_schedule":class_schedule, "status":"Waiting"}, pluck="name", order_by="position asc, joined_on asc"), 1):
		frappe.db.set_value("Talisma Class Waitlist Entry", name, "position", position, update_modified=False)
	sync_enrollment_summary(class_schedule)
	return wait.student


def _validate_term_dates(doc) -> None:
	term = frappe.db.get_value("Academic Term", doc.academic_term, ["term_start_date", "term_end_date"], as_dict=True)
	if not term or not term.term_start_date or not term.term_end_date:
		frappe.throw(_("The selected Academic Term must have start and end dates."))
	if doc.is_new() and getdate(term.term_end_date) < getdate(today()):
		frappe.throw(_("Select an active Academic Term for a new Class Schedule."))
	start, end = getdate(doc.talisma_class_start_date), getdate(doc.talisma_class_end_date)
	if start > end:
		frappe.throw(_("Class Start Date must be on or before Class End Date."))
	if start < getdate(term.term_start_date) or end > getdate(term.term_end_date):
		frappe.throw(_("Class dates must fall within the selected Academic Term."))


def _validate_master_links(doc) -> None:
	instructor_status = frappe.db.get_value("Instructor", doc.talisma_primary_instructor, "status")
	if instructor_status and instructor_status != "Active":
		frappe.throw(_("Select an active Instructor."))
	course_unit = frappe.db.get_value("Course", doc.course, "talisma_academic_unit")
	if course_unit and course_unit != doc.talisma_academic_unit:
		frappe.throw(_("The selected Course does not belong to the selected Academic Unit."))


def _validate_duplicate(doc) -> None:
	duplicate = frappe.db.exists("Talisma Class Section", {"academic_term":doc.academic_term, "course":doc.course, "talisma_section_number":doc.talisma_section_number, "name":("!=", doc.name)})
	if duplicate:
		frappe.throw(_("A Class Schedule already exists for this Course, Academic Term, and Section."))


def _validate_periods(doc) -> None:
	if not doc.talisma_periods:
		frappe.throw(_("Add at least one meeting Period."))
	for row in doc.talisma_periods:
		raw_days = (row.get("days") or "").strip()
		if raw_days and not re.search(r"[,\n]", raw_days) and raw_days.upper() == raw_days:
			invalid_days = [code for code in raw_days if code not in {"M", "T", "W", "R", "F", "S", "U"}]
		else:
			invalid_days = [
				part.strip()
				for part in re.split(r"[,\n]+", raw_days)
				if part.strip() and part.strip() not in DAYS
			]
		if invalid_days:
			frappe.throw(_("Select valid meeting days in row {0}.").format(row.idx))
		days = _days(row.get("days"))
		if not days:
			frappe.throw(_("Select at least one meeting day in row {0}.").format(row.idx))
		row.days = ", ".join(day for day in DAYS if day in days)
		if _seconds(row.get("end_time")) <= _seconds(row.get("start_time")):
			frappe.throw(_("Period End Time must be later than Start Time in row {0}.").format(row.idx))


def _validate_instructor_conflicts(doc) -> None:
	for name in frappe.get_all("Talisma Class Section", filters={"name":("!=", doc.name), "academic_term":doc.academic_term, "talisma_primary_instructor":doc.talisma_primary_instructor, "talisma_section_status":("in", list(ACTIVE_CLASS_STATUSES))}, pluck="name"):
		other = frappe.get_doc("Talisma Class Section", name)
		for new_period in doc.talisma_periods:
			for old_period in other.talisma_periods:
				if _days(new_period.get("days")).intersection(_days(old_period.get("days"))) and _seconds(new_period.get("start_time")) < _seconds(old_period.get("end_time")) and _seconds(new_period.get("end_time")) > _seconds(old_period.get("start_time")):
					frappe.throw(_("The selected instructor is already scheduled for another class during this time."))


def _validate_workload(doc) -> None:
	limit = flt(frappe.db.get_value("Instructor", doc.talisma_primary_instructor, "talisma_max_weekly_contact_hours")) or 20
	hours = _weekly_hours(doc.talisma_periods)
	for name in frappe.get_all("Talisma Class Section", filters={"name":("!=", doc.name), "academic_term":doc.academic_term, "talisma_primary_instructor":doc.talisma_primary_instructor, "talisma_section_status":("in", list(ACTIVE_CLASS_STATUSES))}, pluck="name"):
		hours += flt(frappe.db.get_value("Talisma Class Section", name, "talisma_weekly_contact_hours"))
	if hours > limit:
		frappe.throw(_("This assignment exceeds the instructor's maximum teaching workload."))


def _weekly_hours(periods) -> float:
	return sum(((_seconds(row.get("end_time")) - _seconds(row.get("start_time"))) / 3600) * len(_days(row.get("days"))) for row in periods)


def _days(value) -> set[str]:
	raw = (value or "").strip()
	if raw and not re.search(r"[,\n]", raw) and raw.upper() == raw:
		codes = {"M":"Monday", "T":"Tuesday", "W":"Wednesday", "R":"Thursday", "F":"Friday", "S":"Saturday", "U":"Sunday"}
		return {codes[code] for code in raw if code in codes}
	return {part.strip() for part in re.split(r"[,\n]+", raw) if part.strip() in DAYS}


def _seconds(value) -> float:
	return get_timedelta(value).total_seconds() if value else 0


def _next_section(term: str, course: str) -> str:
	values = frappe.get_all("Talisma Class Section", filters={"academic_term":term, "course":course}, pluck="talisma_section_number")
	numbers = [cint(value) for value in values if str(value or "").isdigit()]
	return f"{(max(numbers) if numbers else 0) + 1:03d}"


def _next_crn() -> str:
	values = frappe.get_all("Talisma Class Section", filters={"talisma_crn":("is", "set")}, pluck="talisma_crn")
	numbers = [cint(value) for value in values if str(value or "").isdigit()]
	return str((max(numbers) if numbers else 10000) + 1)


def _backfill_existing_sections() -> None:
	if not frappe.db.exists("DocType", "Talisma Class Section"):
		return
	for name in frappe.get_all("Student Group", filters={"group_based_on":"Course"}, pluck="name"):
		legacy = frappe.get_doc("Student Group", name)
		if frappe.db.exists("Talisma Class Section", name):
			continue
		doc = frappe.new_doc("Talisma Class Section")
		doc.student_group_name = name
		for fieldname in (
			"academic_year", "academic_term", "program", "course", "max_strength", "disabled",
			"talisma_academic_unit", "talisma_primary_instructor", "talisma_section_number", "talisma_crn",
			"talisma_delivery_method", "talisma_section_status", "talisma_class_start_date",
			"talisma_class_end_date", "talisma_room", "talisma_allow_waitlist", "talisma_waitlist_capacity",
		):
			doc.set(fieldname, legacy.get(fieldname))
		doc.legacy_student_group = legacy.name
		for period in legacy.get("talisma_periods") or []:
			doc.append("talisma_periods", {
				"period_type": period.period_type,
				"days": period.days,
				"start_time": period.start_time,
				"end_time": period.end_time,
			})
		if not doc.talisma_periods and legacy.get("talisma_meeting_days") and legacy.get("talisma_start_time") and legacy.get("talisma_end_time"):
			doc.append("talisma_periods", {
				"period_type": "Lecture",
				"days": ", ".join(day for day in DAYS if day in _days(legacy.talisma_meeting_days)),
				"start_time": legacy.talisma_start_time,
				"end_time": legacy.talisma_end_time,
			})
		for student in legacy.students:
			doc.append("students", {"student": student.student, "active": student.active})
		doc.insert(ignore_permissions=True)


def _detach_legacy_class_fields() -> int:
	"""Convert migrated course-based Student Groups into logical academic groups."""
	meta = frappe.get_meta("Student Group")
	legacy_fields = (
		"group_based_on",
		"course",
		"batch",
		"student_category",
		"max_strength",
		"disabled",
		"talisma_crn",
		"talisma_section_number",
		"talisma_delivery_method",
		"talisma_section_status",
		"talisma_room",
		"talisma_primary_instructor",
		"talisma_class_start_date",
		"talisma_class_end_date",
		"talisma_waitlist_capacity",
		"talisma_allow_waitlist",
	)
	legacy_groups = set(
		frappe.get_all(
			"Student Group",
			filters=[["Student Group", "group_based_on", "=", "Course"]],
			pluck="name",
		)
	)
	legacy_groups.update(
		name
		for name in frappe.get_all(
			"Talisma Class Section",
			filters={"legacy_student_group": ("is", "set")},
			pluck="legacy_student_group",
		)
		if name
	)
	for group_name in legacy_groups:
		values = {}
		for fieldname in legacy_fields:
			df = meta.get_field(fieldname)
			if not df:
				continue
			values[fieldname] = 0 if df.fieldtype in {"Check", "Int", "Float", "Percent", "Currency"} else None
		frappe.db.set_value("Student Group", group_name, values, update_modified=False)
		for child_fieldname in ("talisma_periods", "instructors"):
			df = meta.get_field(child_fieldname)
			if df and df.fieldtype == "Table" and df.options:
				frappe.db.delete(
					df.options,
					{
						"parent": group_name,
						"parenttype": "Student Group",
						"parentfield": child_fieldname,
					},
				)
	return len(legacy_groups)


@frappe.whitelist()
def migrate_legacy_student_groups() -> dict:
	"""Preserve legacy classroom data in Class Scheduling, then clean Student Groups."""
	before = frappe.db.count("Talisma Class Section")
	_backfill_existing_sections()
	detached = _detach_legacy_class_fields()
	frappe.clear_cache(doctype="Student Group")
	frappe.clear_cache(doctype="Talisma Class Section")
	return {
		"class_sections_created": frappe.db.count("Talisma Class Section") - before,
		"student_groups_detached": detached,
	}


def _sync_compatibility_group(doc) -> None:
	"""Do not recreate course-based Student Groups from Class Scheduling records."""
	return


def _field(fieldname, label, fieldtype, options="", insert_after="", **values):
	return {"fieldname":fieldname, "label":label, "fieldtype":fieldtype, "options":options, "insert_after":insert_after, **values}

