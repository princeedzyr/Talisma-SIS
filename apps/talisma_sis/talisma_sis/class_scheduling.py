"""US class scheduling engine built on Education Student Group and Course Schedule."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt, get_timedelta, getdate, now, today


DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
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
			_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "course", reqd=1),
			_field("talisma_primary_instructor", "Instructor", "Link", "Instructor", "talisma_academic_unit", reqd=1),
			_field("talisma_section_number", "Section", "Data", "", "talisma_primary_instructor", reqd=1, in_list_view=1),
			_field("talisma_crn", "CRN", "Data", "", "talisma_section_number", unique=1, read_only=1, in_list_view=1),
			_field("talisma_delivery_method", "Delivery Method", "Select", "In Person\nOnline\nHybrid\nHyFlex", "talisma_crn", default="In Person"),
			_field("talisma_section_status", "Class Status", "Select", "Planned\nOpen\nFull\nWaitlisted\nClosed\nCancelled\nCompleted", "talisma_delivery_method", default="Planned", in_list_view=1),
			_field("talisma_class_start_date", "Class Start Date", "Date", "", "talisma_section_status", reqd=1),
			_field("talisma_class_end_date", "Class End Date", "Date", "", "talisma_class_start_date", reqd=1),
			_field("talisma_periods_section", "Meeting Periods", "Section Break", "", "talisma_class_end_date"),
			_field("talisma_periods", "Periods", "Table", "Talisma Class Period", "talisma_periods_section", reqd=1),
			_field("talisma_capacity_section", "Enrollment Summary", "Section Break", "", "talisma_periods"),
			_field("talisma_allow_waitlist", "Allow Waitlist", "Check", "", "max_strength", default=0),
			_field("talisma_waitlist_capacity", "Waitlist Capacity", "Int", "", "talisma_allow_waitlist", depends_on="eval:doc.talisma_allow_waitlist"),
			_field("talisma_registered_students", "Registered Students", "Int", "", "talisma_waitlist_capacity", read_only=1),
			_field("talisma_available_seats", "Available Seats", "Int", "", "talisma_registered_students", read_only=1),
			_field("talisma_waitlisted_students", "Waitlisted Students", "Int", "", "talisma_available_seats", read_only=1),
			_field("talisma_remaining_waitlist_seats", "Remaining Waitlist Seats", "Int", "", "talisma_waitlisted_students", read_only=1),
			_field("talisma_weekly_contact_hours", "Weekly Contact Hours", "Float", "", "talisma_remaining_waitlist_seats", read_only=1, precision="2"),
			_field("talisma_assigned_credit_hours", "Assigned Credit Hours", "Float", "", "talisma_weekly_contact_hours", read_only=1, precision="2"),
		],
		"Instructor": [
			_field("talisma_max_weekly_contact_hours", "Maximum Weekly Contact Hours", "Float", "", "instructor_name", default=20),
		],
	}, update=False)
	for fieldname, values in {
		"talisma_delivery_method": {"options":"In Person\nOnline\nHybrid\nHyFlex", "default":"In Person"},
		"talisma_section_status": {"label":"Class Status", "options":"Planned\nOpen\nFull\nWaitlisted\nClosed\nCancelled\nCompleted", "default":"Planned"},
		"talisma_section_number": {"label":"Section", "reqd":1},
		"talisma_primary_instructor": {"label":"Instructor", "reqd":1},
	}.items():
		name = frappe.db.get_value("Custom Field", {"dt":"Student Group", "fieldname":fieldname}, "name")
		if name:
			frappe.db.set_value("Custom Field", name, values, update_modified=False)
	for fieldname in ("talisma_meeting_days", "talisma_start_time", "talisma_end_time"):
		name = frappe.db.get_value("Custom Field", {"dt": "Student Group", "fieldname": fieldname}, "name")
		if name:
			frappe.db.set_value("Custom Field", name, "hidden", 1, update_modified=False)
	_backfill_existing_sections()
	frappe.clear_cache(doctype="Student Group")


def before_validate_class_schedule(doc, method=None) -> None:
	if doc.group_based_on != "Course":
		return
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
	if doc.talisma_primary_instructor and not any(row.instructor == doc.talisma_primary_instructor for row in doc.instructors):
		doc.append("instructors", {"instructor": doc.talisma_primary_instructor})


def validate_class_schedule(doc, method=None) -> None:
	if doc.group_based_on != "Course":
		return
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
	if not class_schedule or not frappe.db.exists("Student Group", class_schedule):
		return
	doc = frappe.get_doc("Student Group", class_schedule)
	set_enrollment_summary(doc)
	frappe.db.set_value("Student Group", doc.name, {
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
	section = frappe.get_doc("Student Group", class_schedule)
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
	duplicate = frappe.db.exists("Student Group", {"academic_term":doc.academic_term, "course":doc.course, "talisma_section_number":doc.talisma_section_number, "name":("!=", doc.name)})
	if duplicate:
		frappe.throw(_("A Class Schedule already exists for this Course, Academic Term, and Section."))


def _validate_periods(doc) -> None:
	if not doc.talisma_periods:
		frappe.throw(_("Add at least one meeting Period."))
	for row in doc.talisma_periods:
		days = _days(row.get("days"))
		if not days:
			frappe.throw(_("Select at least one meeting day in row {0}.").format(row.idx))
		if _seconds(row.get("end_time")) <= _seconds(row.get("start_time")):
			frappe.throw(_("Period End Time must be later than Start Time in row {0}.").format(row.idx))


def _validate_instructor_conflicts(doc) -> None:
	for name in frappe.get_all("Student Group", filters={"name":("!=", doc.name), "academic_term":doc.academic_term, "talisma_primary_instructor":doc.talisma_primary_instructor, "talisma_section_status":("in", list(ACTIVE_CLASS_STATUSES))}, pluck="name"):
		other = frappe.get_doc("Student Group", name)
		for new_period in doc.talisma_periods:
			for old_period in other.talisma_periods:
				if _days(new_period.get("days")).intersection(_days(old_period.get("days"))) and _seconds(new_period.get("start_time")) < _seconds(old_period.get("end_time")) and _seconds(new_period.get("end_time")) > _seconds(old_period.get("start_time")):
					frappe.throw(_("The selected instructor is already scheduled for another class during this time."))


def _validate_workload(doc) -> None:
	limit = flt(frappe.db.get_value("Instructor", doc.talisma_primary_instructor, "talisma_max_weekly_contact_hours")) or 20
	hours = _weekly_hours(doc.talisma_periods)
	for name in frappe.get_all("Student Group", filters={"name":("!=", doc.name), "academic_term":doc.academic_term, "talisma_primary_instructor":doc.talisma_primary_instructor, "talisma_section_status":("in", list(ACTIVE_CLASS_STATUSES))}, pluck="name"):
		hours += flt(frappe.db.get_value("Student Group", name, "talisma_weekly_contact_hours"))
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
	values = frappe.get_all("Student Group", filters={"academic_term":term, "course":course}, pluck="talisma_section_number")
	numbers = [cint(value) for value in values if str(value or "").isdigit()]
	return f"{(max(numbers) if numbers else 0) + 1:03d}"


def _next_crn() -> str:
	values = frappe.get_all("Student Group", filters={"talisma_crn":("is", "set")}, pluck="talisma_crn")
	numbers = [cint(value) for value in values if str(value or "").isdigit()]
	return str((max(numbers) if numbers else 10000) + 1)


def _backfill_existing_sections() -> None:
	for name in frappe.get_all("Student Group", filters={"group_based_on":"Course"}, pluck="name"):
		doc = frappe.get_doc("Student Group", name)
		term = frappe.db.get_value("Academic Term", doc.academic_term, ["term_start_date", "term_end_date"], as_dict=True) or {}
		values = {
			"talisma_academic_unit": doc.talisma_academic_unit or frappe.db.get_value("Course", doc.course, "talisma_academic_unit"),
			"talisma_class_start_date": doc.talisma_class_start_date or term.get("term_start_date"),
			"talisma_class_end_date": doc.talisma_class_end_date or term.get("term_end_date"),
			"talisma_allow_waitlist": 1 if cint(doc.talisma_waitlist_capacity) else 0,
		}
		doc.update(values)
		valid_periods = [row for row in doc.talisma_periods if row.get("days") and row.get("start_time") and row.get("end_time")]
		if len(valid_periods) != len(doc.talisma_periods):
			doc.set("talisma_periods", valid_periods)
		if not valid_periods and doc.talisma_meeting_days and doc.talisma_start_time and doc.talisma_end_time:
			doc.append("talisma_periods", {"period_type":"Lecture", "days":"\n".join(day for day in DAYS if day in _days(doc.talisma_meeting_days)), "start_time":doc.talisma_start_time, "end_time":doc.talisma_end_time})
		doc.save(ignore_permissions=True)


def _field(fieldname, label, fieldtype, options="", insert_after="", **values):
	return {"fieldname":fieldname, "label":label, "fieldtype":fieldtype, "options":options, "insert_after":insert_after, **values}
