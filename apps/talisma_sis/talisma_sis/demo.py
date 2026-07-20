"""Idempotent setup for the isolated Talisma SIS client demonstration site."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate


DEMO_SITE = "demo.talisma.local"


def setup() -> dict[str, int]:
	"""Create the synthetic demo dataset on the dedicated demo site only."""
	if frappe.local.site != DEMO_SITE:
		frappe.throw(f"Demo setup is restricted to {DEMO_SITE}.")

	_required_apps()
	_create_integration_fields()
	foundation = _create_institutional_foundation()
	calendar = _create_academic_calendar()
	_create_education_catalog(foundation["academic_unit"])
	_create_people_and_enrollments(foundation["campus"], calendar)
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	_create_demo_workspaces()
	frappe.db.commit()

	return {
		"institutions": frappe.db.count("Talisma Institution"),
		"campuses": frappe.db.count("Talisma Campus"),
		"academic_units": frappe.db.count("Talisma Academic Unit"),
		"programs": frappe.db.count("Program"),
		"courses": frappe.db.count("Course"),
		"instructors": frappe.db.count("Instructor"),
		"applicants": frappe.db.count("Student Applicant"),
		"students": frappe.db.count("Student"),
		"program_enrollments": frappe.db.count("Program Enrollment"),
		"course_enrollments": frappe.db.count("Course Enrollment"),
		"demo_workspaces": frappe.db.count(
			"Workspace",
			{"label": ["in", ["Talisma Admissions", "Talisma Registrar"]]},
		),
	}


def _required_apps() -> None:
	missing = {"erpnext", "education", "talisma_sis"} - set(frappe.get_installed_apps())
	if missing:
		frappe.throw(f"Install required apps before demo setup: {', '.join(sorted(missing))}")


def _create_integration_fields() -> None:
	create_custom_fields(
		{
			"Student Applicant": [
				_field("talisma_campus", "Campus", "Link", "Talisma Campus", "program"),
			],
			"Student": [
				_field("talisma_home_campus", "Home Campus", "Link", "Talisma Campus", "student_email_id"),
			],
			"Program": [
				_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "program_name"),
			],
			"Course": [
				_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "course_name"),
			],
			"Instructor": [
				_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "instructor_name"),
			],
			"Program Enrollment": [
				_field("talisma_campus", "Campus", "Link", "Talisma Campus", "program"),
			],
		}
	)


def _field(fieldname: str, label: str, fieldtype: str, options: str, insert_after: str) -> dict:
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"options": options,
		"insert_after": insert_after,
		"translatable": 0,
	}


def _create_institutional_foundation() -> dict[str, str]:
	institution = _ensure(
		"Talisma Institution",
		None,
		filters={"institution_code": "TSU"},
		institution_code="TSU",
		institution_name="Talisma State University",
		status="Active",
		valid_from="2020-01-01",
		default_timezone="America/New_York",
	)
	_ensure(
		"Address Template",
		"United States",
		country="United States",
		is_default=1,
		template="{{ address_line1 }}<br>{{ city }}, {{ state }} {{ pincode }}<br>{{ country }}",
	)
	address = _ensure(
		"Address",
		None,
		filters={"address_title": "Talisma State University", "address_line1": "100 University Avenue"},
		address_title="Talisma State University",
		address_type="Office",
		address_line1="100 University Avenue",
		city="Boston",
		state="Massachusetts",
		country="United States",
		pincode="02115",
	)
	campus = _ensure(
		"Talisma Campus",
		None,
		filters={"institution": institution, "campus_code": "MAIN"},
		institution=institution,
		campus_code="MAIN",
		campus_name="Main Campus",
		campus_type="Main",
		status="Active",
		valid_from="2020-01-01",
		timezone="America/New_York",
		address=address,
	)
	college_type = _ensure(
		"Talisma Academic Unit Type", None, filters={"type_code": "COLLEGE"}, type_code="COLLEGE", type_name="College"
	)
	school_type = _ensure(
		"Talisma Academic Unit Type", None, filters={"type_code": "SCHOOL"}, type_code="SCHOOL", type_name="School"
	)
	_ensure(
		"Talisma Academic Unit",
		None,
		filters={"institution": institution, "unit_code": "CAS"},
		institution=institution,
		unit_code="CAS",
		unit_name="College of Arts and Sciences",
		unit_type=college_type,
		status="Active",
		valid_from="2020-01-01",
	)
	academic_unit = _ensure(
		"Talisma Academic Unit",
		None,
		filters={"institution": institution, "unit_code": "COMP"},
		institution=institution,
		unit_code="COMP",
		unit_name="School of Computing",
		unit_type=school_type,
		status="Active",
		valid_from="2020-01-01",
	)
	return {"institution": institution, "campus": campus, "academic_unit": academic_unit}


def _create_academic_calendar() -> dict[str, str]:
	academic_year = _ensure(
		"Academic Year",
		"2026-2027",
		academic_year_name="2026-2027",
		year_start_date="2026-08-01",
		year_end_date="2027-07-31",
	)
	academic_term = _ensure(
		"Academic Term",
		None,
		filters={"academic_year": academic_year, "term_name": "Fall 2026"},
		academic_year=academic_year,
		term_name="Fall 2026",
		term_start_date="2026-08-24",
		term_end_date="2026-12-18",
	)
	return {"academic_year": academic_year, "academic_term": academic_term}


def _create_education_catalog(academic_unit: str) -> None:
	for name, abbreviation in (("Bachelor of Science in Computer Science", "BSCS"), ("Master of Science in Data Science", "MSDS")):
		_ensure("Program", name, program_name=name, program_abbreviation=abbreviation, talisma_academic_unit=academic_unit)

	for code, title in (
		("CS-101", "Introduction to Computer Science"),
		("CS-201", "Data Structures"),
		("CS-220", "Database Systems"),
		("CS-310", "Software Engineering"),
		("DS-501", "Foundations of Data Science"),
		("DS-520", "Applied Machine Learning"),
	):
		_ensure("Course", title, course_name=title, course_code=code, talisma_academic_unit=academic_unit)

	for name in ("Dr. Maya Chen", "Professor Daniel Brooks", "Dr. Elena Rodriguez"):
		_ensure("Instructor", None, filters={"instructor_name": name}, instructor_name=name, talisma_academic_unit=academic_unit)


def _create_people_and_enrollments(campus: str, calendar: dict[str, str]) -> None:
	program = "Bachelor of Science in Computer Science"
	academic_year = calendar["academic_year"]
	academic_term = calendar["academic_term"]
	for first, last, status in (("Avery", "Johnson", "Applied"), ("Jordan", "Lee", "Approved"), ("Taylor", "Morgan", "Admitted")):
		_ensure(
			"Student Applicant",
			None,
			filters={"student_email_id": f"{first.lower()}.{last.lower()}@example.edu"},
			first_name=first,
			last_name=last,
			student_email_id=f"{first.lower()}.{last.lower()}@example.edu",
			program=program,
			academic_year=academic_year,
			academic_term=academic_term,
			application_date=getdate("2026-02-15"),
			application_status=status,
			talisma_campus=campus,
		)

	students = (
		("Alex", "Carter"), ("Priya", "Shah"), ("Noah", "Williams"),
		("Sofia", "Martinez"), ("Ethan", "Brown"), ("Mia", "Davis"),
	)
	courses = ("Introduction to Computer Science", "Data Structures", "Database Systems")
	for first, last in students:
		email = f"{first.lower()}.{last.lower()}@example.edu"
		student = _ensure(
			"Student",
			None,
			filters={"student_email_id": email},
			first_name=first,
			last_name=last,
			student_email_id=email,
			talisma_home_campus=campus,
		)
		enrollment = _ensure(
			"Program Enrollment",
			None,
			filters={"student": student, "program": program, "academic_year": academic_year},
			student=student,
			student_name=f"{first} {last}",
			program=program,
			academic_year=academic_year,
			academic_term=academic_term,
			enrollment_date="2026-08-10",
			talisma_campus=campus,
		)
		for course in courses:
			_ensure(
				"Course Enrollment",
				None,
				filters={"program_enrollment": enrollment, "course": course},
				program_enrollment=enrollment,
				student=student,
				course=course,
				enrollment_date="2026-08-10",
			)


def _create_demo_workspaces() -> None:
	_create_workspace(
		'Talisma Admissions',
		'users',
		[
			('Applicants', 'Student Applicant', 'Blue'),
			('Admission Cycles', 'Student Admission', 'Orange'),
			('Programs', 'Program', 'Green'),
			('Students', 'Student', 'Grey'),
		],
	)
	_create_workspace(
		'Talisma Registrar',
		'list',
		[
			('Student Records', 'Student', 'Blue'),
			('Program Enrollments', 'Program Enrollment', 'Green'),
			('Course Enrollments', 'Course Enrollment', 'Orange'),
			('Assessment Results', 'Assessment Result', 'Purple'),
		],
	)


def _create_workspace(label: str, icon: str, shortcuts: list[tuple[str, str, str]]) -> None:
	content = [{
		'id': f'{label}-header',
		'type': 'header',
		'data': {'text': f'<span class=h4><b>{label}</b></span>', 'col': 12},
	}]
	for index, (shortcut_label, _, _) in enumerate(shortcuts):
		content.append({
			'id': f'{label}-{index}',
			'type': 'shortcut',
			'data': {'shortcut_name': shortcut_label, 'col': 3},
		})

	values = {
		'label': label,
		'title': label,
		'module': 'Talisma SIS',
		'icon': icon,
		'public': 1,
		'is_hidden': 0,
		'content': frappe.as_json(content),
		'shortcuts': [
			{'label': item[0], 'link_to': item[1], 'type': 'DocType', 'color': item[2]}
			for item in shortcuts
		],
	}
	existing = frappe.db.exists('Workspace', label)
	if existing:
		doc = frappe.get_doc('Workspace', existing)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({'doctype': 'Workspace', **values}).insert(ignore_permissions=True)


def _ensure(doctype: str, name: str | None, filters: dict | None = None, **values) -> str:
	filters = filters or ({"name": name} if name else values)
	existing = frappe.db.get_value(doctype, filters, "name")
	if existing:
		return existing

	doc = frappe.get_doc({"doctype": doctype, **values})
	if name:
		doc.name = name
	return doc.insert(ignore_permissions=True).name
