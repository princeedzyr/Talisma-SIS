"""Catalog-versioned curriculum rules and student degree-audit calculations."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt, getdate, now_datetime, today


DEMO_SITE = "demo.talisma.local"


def configure_curriculum() -> None:
	create_custom_fields(
		{
			"Program": [
				_field(
					"talisma_default_curriculum_version",
					"Default Curriculum Version",
					"Link",
					"talisma_degree",
					options="Talisma Curriculum Version",
					read_only=1,
				),
				_field(
					"talisma_curriculum_requirements_html",
					"Curriculum Requirements",
					"HTML",
					"section_break_courses",
				),
			],
			"Program Enrollment": [
				_field(
					"talisma_curriculum_version",
					"Curriculum Version",
					"Link",
					"program",
					options="Talisma Curriculum Version",
					reqd=1,
					in_list_view=1,
				),
			],
		},
		update=True,
	)
	_configure_program_curriculum_layout()


def _configure_program_curriculum_layout() -> None:
	"""Use the published curriculum as the Program's single course source."""
	for fieldname, prop, value, prop_type in (
		("department", "hidden", 1, "Check"),
		("department", "in_list_view", 0, "Check"),
		("department", "in_standard_filter", 0, "Check"),
		("courses", "hidden", 1, "Check"),
		("section_break_courses", "label", "Curriculum Requirements", "Data"),
	):
		make_property_setter("Program", fieldname, prop, value, prop_type)

	preferred_order = [
		"talisma_program_code",
		"program_abbreviation",
		"talisma_academic_unit",
		"column_break_3",
		"program_name",
		"talisma_degree",
		"talisma_default_curriculum_version",
		"section_break_courses",
		"talisma_curriculum_requirements_html",
	]
	current_order = [field.fieldname for field in frappe.get_meta("Program").fields]
	remaining = [fieldname for fieldname in current_order if fieldname not in preferred_order]
	make_property_setter(
		"Program",
		None,
		"field_order",
		json.dumps(preferred_order + remaining),
		"Data",
		for_doctype=True,
	)
	frappe.clear_cache(doctype="Program")


@frappe.whitelist()
def get_program_curriculum_requirements(program: str) -> dict:
	"""Return the selected curriculum and its requirements for a Program view."""
	program_doc = frappe.get_doc("Program", program)
	program_doc.check_permission("read")
	version_name = program_doc.get("talisma_default_curriculum_version")
	if not version_name:
		return {"version": None, "requirements": []}

	version = frappe.get_doc("Talisma Curriculum Version", version_name)
	version.check_permission("read")
	requirements = sorted(
		(
			{
				"sequence": row.sequence,
				"requirement_code": row.requirement_code,
				"requirement_name": row.requirement_name,
				"requirement_type": row.requirement_type,
				"course": row.course,
				"active": bool(row.active),
			}
			for row in version.requirements
		),
		key=lambda row: (row["sequence"] or 0, row["requirement_code"] or ""),
	)
	return {
		"version": {
			"name": version.name,
			"version_label": version.version_label,
			"catalog_year": version.catalog_year,
			"status": version.status,
		},
		"requirements": requirements,
	}


def _field(fieldname, label, fieldtype, insert_after="", options="", **values):
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"insert_after": insert_after,
		"options": options,
		**values,
	}


def validate_curriculum_version(doc, method=None) -> None:
	if not _is_demo():
		return
	if doc.effective_to and getdate(doc.effective_to) < getdate(doc.effective_from):
		frappe.throw(_("Effective To cannot be before Effective From."))
	degree = frappe.db.get_value("Program", doc.program, "talisma_degree")
	if degree and doc.degree != degree:
		frappe.throw(_("The curriculum Degree must match the Program degree {0}.").format(frappe.bold(degree)))
	if flt(doc.minimum_total_credits) <= 0:
		frappe.throw(_("Minimum Total Credits must be greater than zero."))
	if flt(doc.minimum_residency_credits) > flt(doc.minimum_total_credits):
		frappe.throw(_("Minimum Residency Credits cannot exceed Minimum Total Credits."))
	codes = set()
	courses = set()
	active_requirements = 0
	for row in doc.requirements:
		if not row.active:
			continue
		active_requirements += 1
		code = (row.requirement_code or "").strip().upper()
		if code in codes:
			frappe.throw(_("Requirement Code {0} is duplicated.").format(frappe.bold(code)))
		codes.add(code)
		if row.requirement_type == "Required Course":
			if not row.course:
				frappe.throw(_("Course is required for {0}.").format(frappe.bold(code)))
			if row.course in courses:
				frappe.throw(_("Required Course {0} appears more than once.").format(frappe.bold(row.course)))
			courses.add(row.course)
		elif row.requirement_type == "Course Group":
			if not row.course_category or int(row.minimum_courses or 0) < 1:
				frappe.throw(_("Course Group {0} needs a category and minimum course count.").format(frappe.bold(code)))
		elif row.requirement_type == "Minimum Credits" and flt(row.minimum_credits) <= 0:
			frappe.throw(_("Minimum Credits must be greater than zero for {0}.").format(frappe.bold(code)))
	if doc.status == "Published":
		if not active_requirements:
			frappe.throw(_("A published curriculum must contain at least one active requirement."))
		duplicate = frappe.db.get_value(
			"Talisma Curriculum Version",
			{
				"program": doc.program,
				"catalog_year": doc.catalog_year,
				"status": "Published",
				"name": ("!=", doc.name or ""),
			},
			"name",
		)
		if duplicate:
			frappe.throw(_("Published curriculum {0} already covers this Program and catalog year.").format(frappe.bold(duplicate)))
		doc.published_on = doc.published_on or now_datetime()
		doc.published_by = doc.published_by or frappe.session.user


def sync_program_curriculum(doc, method=None) -> None:
	if not _is_demo() or not doc.program:
		return
	current = resolve_curriculum_version(doc.program, doc.catalog_year)
	frappe.db.set_value(
		"Program",
		doc.program,
		"talisma_default_curriculum_version",
		current,
		update_modified=False,
	)


def validate_program_enrollment(doc, method=None) -> None:
	if not _is_demo() or not doc.program:
		return
	if not doc.talisma_curriculum_version:
		catalog_year = frappe.db.get_value("Student", doc.student, "talisma_catalog_year")
		doc.talisma_curriculum_version = resolve_curriculum_version(doc.program, catalog_year)
	_validate_assignment(doc.program, doc.talisma_curriculum_version)


def validate_student_program_assignment(doc) -> None:
	if not doc.program_version:
		doc.program_version = resolve_curriculum_version(doc.program, doc.catalog_year)
	_validate_assignment(doc.program, doc.program_version, doc.catalog_year)


def _validate_assignment(program: str, version: str | None, catalog_year: str | None = None) -> None:
	if not version:
		frappe.throw(_("A published Curriculum Version is required for Program {0}.").format(frappe.bold(program)))
	values = frappe.db.get_value(
		"Talisma Curriculum Version", version, ["program", "catalog_year", "status"], as_dict=True
	)
	if not values or values.program != program:
		frappe.throw(_("Curriculum Version {0} does not belong to Program {1}.").format(frappe.bold(version), frappe.bold(program)))
	if values.status != "Published":
		frappe.throw(_("Curriculum Version {0} is not published.").format(frappe.bold(version)))
	if catalog_year and values.catalog_year != catalog_year:
		frappe.throw(
			_("Curriculum Version {0} belongs to catalog year {1}, not {2}.").format(
				frappe.bold(version), values.catalog_year, catalog_year
			)
		)


def resolve_curriculum_version(program: str, catalog_year: str | None = None) -> str | None:
	filters = {"program": program, "status": "Published"}
	if catalog_year:
		filters["catalog_year"] = catalog_year
	version = frappe.db.get_value(
		"Talisma Curriculum Version", filters, "name", order_by="effective_from desc, creation desc"
	)
	if version or not catalog_year:
		return version
	return frappe.db.get_value(
		"Talisma Curriculum Version",
		{"program": program, "status": "Published"},
		"name",
		order_by="effective_from desc, creation desc",
	)


def allowed_curriculum_courses(program_enrollment) -> set[str]:
	version = program_enrollment.get("talisma_curriculum_version") or resolve_curriculum_version(
		program_enrollment.program,
		frappe.db.get_value("Student", program_enrollment.student, "talisma_catalog_year"),
	)
	if not version:
		return set(
			frappe.get_all(
				"Program Course",
				filters={"parent": program_enrollment.program, "parenttype": "Program"},
				pluck="course",
			)
		)
	courses = set()
	for row in frappe.get_all(
		"Talisma Curriculum Requirement",
		filters={"parent": version, "parenttype": "Talisma Curriculum Version", "active": 1},
		fields=["requirement_type", "course", "course_category"],
	):
		if row.requirement_type == "Required Course" and row.course:
			courses.add(row.course)
		elif row.requirement_type == "Course Group" and row.course_category:
			courses.update(
				frappe.get_all(
					"Program Course",
					filters={"parent": row.course_category, "parenttype": "Course Category"},
					pluck="course",
				)
			)
	return courses


@frappe.whitelist()
def get_degree_audit(student: str, academic_program: str | None = None) -> dict:
	student_doc = frappe.get_doc("Student", student)
	if not frappe.has_permission("Student", "read", doc=student_doc):
		frappe.throw(_("You do not have permission to view this degree audit."), frappe.PermissionError)
	assignment_name = academic_program or frappe.db.get_value(
		"Talisma Student Academic Program",
		{"student": student, "primary_program": 1, "status": "Active"},
		"name",
		order_by="effective_from desc, creation desc",
	)
	if not assignment_name:
		return {"available": False, "message": _("No active primary academic program is assigned.")}
	assignment = frappe.get_doc("Talisma Student Academic Program", assignment_name)
	version_name = assignment.program_version or resolve_curriculum_version(assignment.program, assignment.catalog_year)
	if not version_name:
		return {"available": False, "message": _("No published curriculum matches this student program.")}
	version = frappe.get_doc("Talisma Curriculum Version", version_name)
	attempts = _course_attempts(student)
	course_names = set(attempts)
	for requirement in version.requirements:
		if requirement.course:
			course_names.add(requirement.course)
	course_rows = frappe.get_all(
		"Course",
		filters={"name": ("in", list(course_names))},
		fields=["name", "talisma_credit_hours"],
	) if course_names else []
	credits = {
		row.name: flt(row.talisma_credit_hours)
		for row in course_rows
	}
	completed_courses = {
		course for course, attempt in attempts.items() if _attempt_completed(attempt, None)
	}
	completed_credits = sum(credits.get(course, 0) for course in completed_courses)
	in_progress_credits = sum(
		credits.get(course, 0)
		for course, attempt in attempts.items()
		if attempt.talisma_completion_status == "In Progress"
	)
	requirements = [
		_audit_requirement(row, attempts, credits, completed_credits)
		for row in version.requirements
		if row.active
	]
	all_complete = bool(requirements) and all(row["status"] == "Completed" for row in requirements)
	graduation_holds = [
		row for row in __import__("talisma_sis.student_records", fromlist=["active_holds"]).active_holds(student)
		if row.blocks_graduation
	]
	minimum_credits = flt(version.minimum_total_credits)
	progress = min(100, (completed_credits / minimum_credits * 100) if minimum_credits else 0)
	return {
		"available": True,
		"student_program": assignment.name,
		"program": assignment.program,
		"degree": assignment.degree,
		"catalog_year": assignment.catalog_year,
		"curriculum_version": version.name,
		"version_label": version.version_label,
		"summary": {
			"minimum_credits": minimum_credits,
			"completed_credits": completed_credits,
			"in_progress_credits": in_progress_credits,
			"remaining_credits": max(0, minimum_credits - completed_credits),
			"completed_requirements": sum(row["status"] == "Completed" for row in requirements),
			"total_requirements": len(requirements),
			"progress_percent": round(progress, 1),
			"graduation_eligible": all_complete and completed_credits >= minimum_credits and not graduation_holds,
			"graduation_holds": len(graduation_holds),
		},
		"requirements": requirements,
	}


def _course_attempts(student: str) -> dict:
	rows = frappe.get_all(
		"Course Enrollment",
		filters={"student": student},
		fields=["name", "course", "talisma_attempt_number", "talisma_academic_term", "talisma_grade_earned", "talisma_grade_points", "talisma_completion_status"],
		order_by="course, talisma_attempt_number, creation",
	)
	attempts = {}
	for row in rows:
		current = attempts.get(row.course)
		if not current or _attempt_completed(row, None) or not _attempt_completed(current, None):
			attempts[row.course] = row
	return attempts


def _audit_requirement(row, attempts: dict, credits: dict, completed_credits: float) -> dict:
	base = {
		"code": row.requirement_code,
		"name": row.requirement_name,
		"type": row.requirement_type,
		"course": row.course,
		"course_category": row.course_category,
		"minimum_grade": row.minimum_grade,
		"minimum_courses": int(row.minimum_courses or 0),
		"minimum_credits": flt(row.minimum_credits),
	}
	if row.requirement_type == "Required Course":
		attempt = attempts.get(row.course)
		status = "Completed" if _attempt_completed(attempt, row.minimum_grade) else (
			"In Progress" if attempt and attempt.talisma_completion_status == "In Progress" else "Not Started"
		)
		return {**base, "status": status, "earned_credits": credits.get(row.course, 0) if status == "Completed" else 0, "grade": attempt.talisma_grade_earned if attempt else None}
	if row.requirement_type == "Course Group":
		group_courses = set(frappe.get_all(
			"Program Course",
			filters={"parent": row.course_category, "parenttype": "Course Category"},
			pluck="course",
		))
		completed = [course for course in group_courses if _attempt_completed(attempts.get(course), row.minimum_grade)]
		in_progress = [course for course in group_courses if attempts.get(course) and attempts[course].talisma_completion_status == "In Progress"]
		earned = sum(credits.get(course, 0) for course in completed)
		meets_courses = len(completed) >= int(row.minimum_courses or 0)
		meets_credits = not flt(row.minimum_credits) or earned >= flt(row.minimum_credits)
		status = "Completed" if meets_courses and meets_credits else ("In Progress" if in_progress or completed else "Not Started")
		return {**base, "status": status, "earned_credits": earned, "completed_courses": len(completed)}
	status = "Completed" if completed_credits >= flt(row.minimum_credits) else ("In Progress" if completed_credits else "Not Started")
	return {**base, "status": status, "earned_credits": completed_credits}


def _attempt_completed(attempt, minimum_grade: str | None) -> bool:
	if not attempt or attempt.talisma_completion_status != "Completed":
		return False
	if not minimum_grade or not attempt.talisma_grade_earned:
		return True
	grades = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
	return grades.get(str(attempt.talisma_grade_earned).upper(), -1) >= grades.get(str(minimum_grade).upper(), 0)


def seed_demo_curricula() -> None:
	for program in frappe.get_all("Program", fields=["name", "talisma_program_code", "talisma_degree"]):
		courses = frappe.get_all(
			"Program Course",
			filters={"parent": program.name, "parenttype": "Program"},
			fields=["course", "required"],
			order_by="idx",
		)
		if not courses:
			continue
		code = f"{program.talisma_program_code or program.name}-2026"
		doc = frappe.get_doc("Talisma Curriculum Version", code) if frappe.db.exists("Talisma Curriculum Version", code) else frappe.new_doc("Talisma Curriculum Version")
		doc.curriculum_code = code
		doc.program = program.name
		doc.degree = program.talisma_degree
		doc.catalog_year = "2026-2027"
		doc.version_label = "2026 Catalog"
		doc.status = "Published"
		doc.effective_from = "2026-07-01"
		doc.minimum_total_credits = sum(flt(frappe.db.get_value("Course", row.course, "talisma_credit_hours")) for row in courses)
		doc.minimum_residency_credits = doc.minimum_total_credits
		doc.notes = "Demo curriculum version using the authoritative Program course list."
		doc.set("requirements", [])
		for sequence, row in enumerate(courses, 1):
			doc.append("requirements", {
				"sequence": sequence,
				"requirement_code": f"REQ-{sequence:02d}",
				"requirement_name": row.course,
				"requirement_type": "Required Course",
				"course": row.course,
				"minimum_grade": "C",
				"active": 1,
			})
		doc.append("requirements", {
			"sequence": len(courses) + 1,
			"requirement_code": "TOTAL-CREDITS",
			"requirement_name": "Minimum Program Credits",
			"requirement_type": "Minimum Credits",
			"minimum_credits": doc.minimum_total_credits,
			"active": 1,
		})
		doc.save(ignore_permissions=True)
		frappe.db.set_value("Program", program.name, "talisma_default_curriculum_version", doc.name, update_modified=False)

	for enrollment in frappe.get_all("Program Enrollment", fields=["name", "student", "program"]):
		catalog_year = frappe.db.get_value("Student", enrollment.student, "talisma_catalog_year") or "2026-2027"
		version = resolve_curriculum_version(enrollment.program, catalog_year)
		if version:
			frappe.db.set_value("Program Enrollment", enrollment.name, "talisma_curriculum_version", version, update_modified=False)
	for assignment in frappe.get_all("Talisma Student Academic Program", fields=["name", "program", "catalog_year"]):
		version = resolve_curriculum_version(assignment.program, assignment.catalog_year)
		if version:
			frappe.db.set_value("Talisma Student Academic Program", assignment.name, "program_version", version, update_modified=False)


def healthcheck() -> dict:
	programs = frappe.db.count("Program")
	checks = {
		"curriculum_versions": frappe.db.count("Talisma Curriculum Version", {"status": "Published"}) >= programs,
		"curriculum_requirements": frappe.db.count("Talisma Curriculum Requirement", {"active": 1}) > 0,
		"enrollments_versioned": frappe.db.count("Program Enrollment", {"talisma_curriculum_version": ("is", "set")}) == frappe.db.count("Program Enrollment"),
		"student_programs_versioned": frappe.db.count("Talisma Student Academic Program", {"program_version": ("is", "set")}) == frappe.db.count("Talisma Student Academic Program"),
	}
	student = frappe.db.get_value("Student", {"first_name": "Prince"}, "name")
	audit = get_degree_audit(student) if student else {"available": False}
	checks["degree_audit_available"] = bool(audit.get("available") and audit.get("requirements"))
	return {"ok": all(checks.values()), "checks": checks, "audit": audit}


def _is_demo() -> bool:
	return frappe.local.site == DEMO_SITE
