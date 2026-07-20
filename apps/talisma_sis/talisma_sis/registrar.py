"""Registrar workflow extensions for the isolated Talisma SIS demo."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now, today

from talisma_sis.demo import DEMO_SITE


MAX_COURSES_PER_TERM = 5


def healthcheck() -> dict:
	"""Verify the Registrar workspace and prepared Avery registration."""
	_require_demo_site()
	workspace = frappe.get_doc("Workspace", "Registrar")
	card_names = [row.number_card_name for row in workspace.number_cards]
	enrollment = frappe.db.get_value(
		"Program Enrollment",
		{"student": "EDU-STU-2026-00008", "program": "Bachelor of Science in Computer Science"},
		"name",
	)
	summary = get_registration_summary(enrollment) if enrollment else None
	checks = {
		"registrar_workspace_exists": bool(workspace.name),
		"student_centered_number_cards": (
			len(card_names) == 2
			and "Talisma Program Enrollments" not in card_names
			and "Talisma Course Registrations" not in card_names
		),
		"bs_cs_has_four_courses": bool(summary and len(summary["courses"]) == 4),
		"avery_has_registration": bool(summary and summary["registered_count"] >= 1),
	}
	return {
		"ok": all(checks.values()),
		"checks": checks,
		"number_cards": card_names,
		"registration": summary,
	}


@frappe.whitelist()
def get_registration_summary(program_enrollment: str) -> dict:
	"""Return allowed and registered courses for one Program Enrollment."""
	_require_demo_site()
	enrollment = frappe.get_doc("Program Enrollment", program_enrollment)
	if not frappe.has_permission("Program Enrollment", "read", doc=enrollment):
		frappe.throw(_("You do not have permission to view this registration."), frappe.PermissionError)

	from talisma_sis.curriculum import allowed_curriculum_courses
	allowed_courses = allowed_curriculum_courses(enrollment)
	required_courses = set(frappe.get_all(
		"Talisma Curriculum Requirement",
		filters={
			"parent": enrollment.talisma_curriculum_version,
			"parenttype": "Talisma Curriculum Version",
			"requirement_type": "Required Course",
			"active": 1,
		},
		pluck="course",
	)) if enrollment.talisma_curriculum_version else set()
	allowed = frappe.get_all(
		"Course",
		filters={"name": ("in", list(allowed_courses))},
		fields=["name as course", "course_name"],
		order_by="course_name",
	) if allowed_courses else []
	registered = frappe.get_all(
		"Course Enrollment",
		filters={"program_enrollment": enrollment.name, "student": enrollment.student},
		fields=["name", "course", "talisma_completion_status"],
		order_by="creation",
	)
	registered = [row for row in registered if row.talisma_completion_status not in {"Dropped", "Withdrawn"}]
	registered_by_course = {row.course: row.name for row in registered}
	return {
		"program_enrollment": enrollment.name,
		"student": enrollment.student,
		"student_name": enrollment.student_name,
		"program": enrollment.program,
		"curriculum_version": enrollment.talisma_curriculum_version,
		"academic_year": enrollment.academic_year,
		"academic_term": enrollment.academic_term,
		"campus": enrollment.talisma_campus,
		"maximum_courses": MAX_COURSES_PER_TERM,
		"registered_count": len(registered_by_course),
		"courses": [
			{
				"course": row.course,
				"course_name": row.course_name,
				"required": row.course in required_courses,
				"registered": row.course in registered_by_course,
				"course_enrollment": registered_by_course.get(row.course),
			}
			for row in allowed
		],
	}


@frappe.whitelist()
def get_section_options(program_enrollment: str, academic_term: str | None = None) -> dict:
	"""Return eligible terms and open sections for a Program Enrollment."""
	_require_demo_site()
	summary = get_registration_summary(program_enrollment)
	allowed_courses = {row["course"] for row in summary["courses"]}
	section_filters = {
		"group_based_on": "Course",
		"program": summary["program"],
		"academic_year": summary["academic_year"],
		"disabled": 0,
		"talisma_section_status": ("in", ["Open", "Full", "Waitlisted"]),
	}
	offered_terms = list(dict.fromkeys(
		row.academic_term
		for row in frappe.get_all(
			"Student Group",
			filters=section_filters,
			fields=["academic_term", "course"],
			order_by="academic_term",
		)
		if row.academic_term and row.course in allowed_courses
	))
	term_rows = frappe.get_all(
		"Academic Term",
		filters={"name": ("in", offered_terms)},
		fields=["name", "term_start_date", "term_end_date"],
		order_by="term_start_date, name",
	) if offered_terms else []
	terms = [
		{
			"value": row.name,
			"label": row.name,
			"start_date": row.term_start_date,
			"end_date": row.term_end_date,
		}
		for row in term_rows
	]
	selected_term = academic_term or summary["academic_term"]
	if selected_term not in offered_terms:
		if academic_term:
			frappe.throw(_("The selected Academic Term has no eligible course sections for this program."))
		selected_term = terms[0]["value"] if terms else None
	if not selected_term:
		return {**summary, "academic_term": None, "terms": terms, "sections": []}
	sections = frappe.get_all(
		"Student Group",
		filters={
			**section_filters,
			"academic_term": selected_term,
		},
		fields=[
			"name",
			"course",
			"talisma_crn",
			"talisma_section_number",
			"talisma_delivery_method",
			"talisma_meeting_days",
			"talisma_start_time",
			"talisma_end_time",
			"talisma_room",
			"talisma_primary_instructor",
			"max_strength",
		],
		order_by="course, talisma_section_number",
	)
	registered = {
		row.talisma_course_section: row.name
		for row in frappe.get_all(
			"Course Enrollment",
			filters={"program_enrollment": program_enrollment},
			fields=["name", "talisma_course_section", "talisma_completion_status"],
		)
		if row.talisma_course_section and row.talisma_completion_status not in {"Dropped", "Withdrawn"}
	}
	return {
		**summary,
		"academic_term": selected_term,
		"terms": terms,
		"sections": [
			{
				**section,
				"registered": section.name in registered,
				"course_enrollment": registered.get(section.name),
				"enrolled": frappe.db.count(
					"Student Group Student", {"parent": section.name, "active": 1}
				),
			}
			for section in sections
			if section.course in allowed_courses
		],
	}


@frappe.whitelist()
def register_sections(program_enrollment: str, sections: list[str] | str) -> dict:
	"""Register a student into open sections without duplicating course records."""
	_require_demo_site()
	enrollment = frappe.get_doc("Program Enrollment", program_enrollment)
	_authorize_registration(enrollment)
	selected = frappe.parse_json(sections) if isinstance(sections, str) else sections
	selected = list(dict.fromkeys(selected or []))
	if not selected:
		frappe.throw(_("Select at least one course section."))

	from talisma_sis.curriculum import allowed_curriculum_courses
	allowed_courses = allowed_curriculum_courses(enrollment)
	created = []
	linked = []
	waitlisted = []
	for section_name in selected:
		section = frappe.get_doc("Student Group", section_name)
		_validate_section_for_enrollment(section, enrollment, allowed_courses)
		existing_name = frappe.db.get_value(
			"Course Enrollment",
			{
				"program_enrollment": enrollment.name,
				"student": enrollment.student,
				"course": section.course,
				"talisma_completion_status": ("not in", ["Dropped", "Withdrawn"]),
			},
			"name",
		)
		if not existing_name and len([row for row in section.students if row.active]) >= section.max_strength:
			from talisma_sis.class_scheduling import add_to_waitlist
			waitlisted.append(add_to_waitlist(section, enrollment))
			continue
		if existing_name:
			existing_section = frappe.db.get_value(
				"Course Enrollment", existing_name, "talisma_course_section"
			)
			if existing_section and existing_section != section.name:
				frappe.throw(_("The student is already registered in another section of {0}.").format(section.course))
			if not existing_section:
				frappe.db.set_value(
					"Course Enrollment",
					existing_name,
					{
						"talisma_course_section": section.name,
						"talisma_academic_term": section.academic_term,
					},
				)
			linked.append(existing_name)
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Course Enrollment",
					"program_enrollment": enrollment.name,
					"student": enrollment.student,
					"course": section.course,
					"enrollment_date": today(),
					"talisma_course_section": section.name,
				}
			).insert(ignore_permissions=True)
			created.append(doc.name)
		_add_student_to_section(section, enrollment.student)
		from talisma_sis.class_scheduling import sync_enrollment_summary
		sync_enrollment_summary(section.name)

	registered_count = _update_registration_status(enrollment)
	return {
		"program_enrollment": enrollment.name,
		"created": created,
		"linked": linked,
		"waitlisted": waitlisted,
		"registered_count": registered_count,
		"status": _registration_label(registered_count),
	}


@frappe.whitelist()
def register_courses(program_enrollment: str, courses: list[str] | str) -> dict:
	"""Create missing standard Course Enrollment records for allowed courses."""
	_require_demo_site()
	enrollment = frappe.get_doc("Program Enrollment", program_enrollment)
	_authorize_registration(enrollment)

	selected = frappe.parse_json(courses) if isinstance(courses, str) else courses
	selected = list(dict.fromkeys(selected or []))
	if not selected:
		frappe.throw(_("Select at least one course."))

	from talisma_sis.curriculum import allowed_curriculum_courses
	allowed = allowed_curriculum_courses(enrollment)
	invalid = sorted(set(selected) - allowed)
	if invalid:
		frappe.throw(_("Courses are not part of this program: {0}").format(", ".join(invalid)))

	existing = {
		row.course: row.name
		for row in frappe.get_all(
			"Course Enrollment",
			filters={"program_enrollment": enrollment.name, "student": enrollment.student},
			fields=["name", "course", "talisma_completion_status"],
		)
		if row.talisma_completion_status not in {"Dropped", "Withdrawn"}
	}
	if len(set(existing) | set(selected)) > MAX_COURSES_PER_TERM:
		frappe.throw(
			_("A student may register for no more than {0} courses in this demo term.").format(
				MAX_COURSES_PER_TERM
			)
		)

	created = []
	for course in selected:
		if course in existing:
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Course Enrollment",
				"program_enrollment": enrollment.name,
				"student": enrollment.student,
				"course": course,
				"enrollment_date": today(),
			}
		).insert(ignore_permissions=True)
		created.append(doc.name)

	registered_count = _update_registration_status(enrollment)
	return {
		"program_enrollment": enrollment.name,
		"created": created,
		"already_registered": [existing[course] for course in selected if course in existing],
		"registered_count": registered_count,
		"status": _registration_label(registered_count),
	}


@frappe.whitelist()
def change_course_enrollment_status(
	student: str,
	course_enrollment: str,
	action: str,
	effective_date: str | None = None,
	reason: str | None = None,
) -> dict:
	"""Drop or withdraw a registration while retaining its audit record."""
	_require_demo_site()
	doc = frappe.get_doc("Course Enrollment", course_enrollment)
	if doc.student != student:
		frappe.throw(_("This Course Enrollment does not belong to the selected Student."))
	if not frappe.has_permission("Course Enrollment", "write", doc=doc):
		frappe.throw(_("You do not have permission to update this Course Enrollment."), frappe.PermissionError)
	if doc.talisma_completion_status != "In Progress":
		frappe.throw(_("Only an in-progress registration can be dropped or withdrawn."))
	action = (action or "").strip().title()
	if action not in {"Drop", "Withdraw"}:
		frappe.throw(_("Action must be Drop or Withdraw."))
	if not reason:
		frappe.throw(_("A reason is required."))
	status_date = getdate(effective_date or today())
	term = doc.talisma_academic_term or frappe.db.get_value(
		"Program Enrollment", doc.program_enrollment, "academic_term"
	)
	deadlines = frappe.db.get_value(
		"Academic Term",
		term,
		["talisma_add_drop_deadline", "talisma_withdrawal_deadline"],
		as_dict=True,
	) if term else {}
	deadline = deadlines.get("talisma_add_drop_deadline") if action == "Drop" else deadlines.get("talisma_withdrawal_deadline")
	if deadline and status_date > getdate(deadline):
		frappe.throw(
			_("The {0} deadline for {1} was {2}.").format(action.lower(), term, frappe.format_value(deadline, {"fieldtype": "Date"}))
		)
	new_status = "Dropped" if action == "Drop" else "Withdrawn"
	doc.db_set(
		{
			"talisma_completion_status": new_status,
			"talisma_status_date": status_date,
			"talisma_status_reason": reason,
		},
		update_modified=True,
	)
	_remove_student_from_section(doc.talisma_course_section, student)
	enrollment = frappe.get_doc("Program Enrollment", doc.program_enrollment)
	registered_count = _update_registration_status(enrollment)
	return {
		"name": doc.name,
		"status": new_status,
		"status_date": status_date,
		"registered_count": registered_count,
	}


@frappe.whitelist()
def swap_course_section(student: str, course_enrollment: str, new_section: str) -> dict:
	"""Move an in-progress registration to another open section of the same course."""
	_require_demo_site()
	doc = frappe.get_doc("Course Enrollment", course_enrollment)
	if doc.student != student:
		frappe.throw(_("This Course Enrollment does not belong to the selected Student."))
	if not frappe.has_permission("Course Enrollment", "write", doc=doc):
		frappe.throw(_("You do not have permission to update this Course Enrollment."), frappe.PermissionError)
	if doc.talisma_completion_status != "In Progress":
		frappe.throw(_("Only an in-progress registration can change sections."))
	enrollment = frappe.get_doc("Program Enrollment", doc.program_enrollment)
	_authorize_registration(enrollment)
	from talisma_sis.curriculum import allowed_curriculum_courses
	section = frappe.get_doc("Student Group", new_section)
	_validate_section_for_enrollment(section, enrollment, allowed_curriculum_courses(enrollment))
	if section.course != doc.course:
		frappe.throw(_("The new section must be for {0}.").format(frappe.bold(doc.course)))
	old_section = doc.talisma_course_section
	if old_section == new_section:
		return {"name": doc.name, "course_section": new_section, "unchanged": True}
	_remove_student_from_section(old_section, student)
	doc.db_set("talisma_course_section", new_section, update_modified=True)
	_add_student_to_section(section, student)
	return {"name": doc.name, "course_section": new_section, "unchanged": False}


def acceptance_test() -> dict:
	"""Register Avery for Software Engineering twice and prove idempotence."""
	_require_demo_site()
	enrollment = frappe.db.get_value(
		"Program Enrollment",
		{"student": "EDU-STU-2026-00008", "program": "Bachelor of Science in Computer Science"},
		"name",
	)
	if not enrollment:
		frappe.throw(_("Avery's Program Enrollment is required for the Registrar acceptance test."))

	before = frappe.db.count("Course Enrollment", {"program_enrollment": enrollment})
	first = register_courses(enrollment, ["Software Engineering"])
	after_first = frappe.db.count("Course Enrollment", {"program_enrollment": enrollment})
	second = register_courses(enrollment, ["Software Engineering"])
	after_second = frappe.db.count("Course Enrollment", {"program_enrollment": enrollment})
	return {
		"ok": after_first == after_second and after_second >= before,
		"before": before,
		"after_first": after_first,
		"after_second": after_second,
		"first": first,
		"second": second,
	}


def us_section_acceptance_test() -> dict:
	"""Link Avery to CRN 10001 twice and prove section registration idempotence."""
	_require_demo_site()
	enrollment = frappe.db.get_value(
		"Program Enrollment",
		{"student": "EDU-STU-2026-00008", "program": "Bachelor of Science in Computer Science"},
		"name",
	)
	section = frappe.db.get_value("Student Group", {"talisma_crn": "10001"}, "name")
	before = frappe.db.count("Course Enrollment", {"program_enrollment": enrollment})
	first = register_sections(enrollment, [section])
	after_first = frappe.db.count("Course Enrollment", {"program_enrollment": enrollment})
	second = register_sections(enrollment, [section])
	after_second = frappe.db.count("Course Enrollment", {"program_enrollment": enrollment})
	roster_count = frappe.db.count(
		"Student Group Student", {"parent": section, "student": "EDU-STU-2026-00008", "active": 1}
	)
	return {
		"ok": after_first == after_second and roster_count == 1,
		"before": before,
		"after_first": after_first,
		"after_second": after_second,
		"roster_count": roster_count,
		"first": first,
		"second": second,
	}


def _registration_label(course_count: int) -> str:
	return _("Registered ({0} courses)").format(course_count)


def _authorize_registration(enrollment) -> None:
	if not frappe.has_permission("Program Enrollment", "read", doc=enrollment) or not frappe.has_permission(
		"Course Enrollment", "create"
	):
		frappe.throw(_("You do not have permission to update this registration."), frappe.PermissionError)
	if enrollment.docstatus == 2:
		frappe.throw(_("Cancelled Program Enrollments cannot be registered."))


def _validate_section_for_enrollment(section, enrollment, allowed_courses: set[str]) -> None:
	if section.group_based_on != "Course" or section.course not in allowed_courses:
		frappe.throw(_("Section {0} is not part of this program.").format(section.name))
	if section.program != enrollment.program or section.academic_year != enrollment.academic_year:
		frappe.throw(_("Section {0} is not offered for this program and academic year.").format(section.name))
	if section.disabled or section.talisma_section_status not in {"Open", "Full", "Waitlisted"}:
		frappe.throw(_("Section {0} is not open for registration.").format(section.name))


def _add_student_to_section(section, student: str) -> None:
	if any(row.student == student and row.active for row in section.students):
		return
	section.append("students", {"student": student, "active": 1})
	section.save(ignore_permissions=True)


def _remove_student_from_section(section_name: str | None, student: str) -> None:
	if not section_name or not frappe.db.exists("Student Group", section_name):
		return
	section = frappe.get_doc("Student Group", section_name)
	changed = False
	for row in section.students:
		if row.student == student and row.active:
			row.active = 0
			changed = True
	if changed:
		section.save(ignore_permissions=True)
		from talisma_sis.class_scheduling import promote_waitlist
		promote_waitlist(section_name)


def _update_registration_status(enrollment) -> int:
	total = frappe.db.count(
		"Course Enrollment",
		{"program_enrollment": enrollment.name, "student": enrollment.student},
	)
	inactive = frappe.db.count(
		"Course Enrollment",
		{
			"program_enrollment": enrollment.name,
			"student": enrollment.student,
			"talisma_completion_status": ("in", ["Dropped", "Withdrawn"]),
		},
	)
	registered_count = total - inactive
	enrollment.db_set(
		{
			"talisma_registration_status": _registration_label(registered_count),
			"talisma_registration_updated_on": now(),
		},
		update_modified=True,
	)
	return registered_count


def _require_demo_site() -> None:
	if frappe.local.site != DEMO_SITE:
		frappe.throw(_("The demo Registrar workflow is restricted to {0}.").format(DEMO_SITE))
