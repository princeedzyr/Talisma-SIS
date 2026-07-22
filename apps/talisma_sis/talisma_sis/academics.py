"""US higher-education academic hierarchy built on ERPNext Education masters."""

from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt, getdate


DEMO_SITE = "demo.talisma.local"
COURSE_TYPES = "Core\nElective\nLaboratory\nSeminar\nInternship\nCapstone\nIndependent Study"
DEFAULT_GRADE_NAMES = {
	"A+": "Excellent",
	"A": "Excellent",
	"A-": "Excellent",
	"B+": "Very Good",
	"B": "Good",
	"B-": "Good",
	"C+": "Satisfactory",
	"C": "Satisfactory",
	"C-": "Satisfactory",
	"D": "Pass",
	"F": "Fail",
	"I": "Incomplete",
	"W": "Withdrawn",
}
DEFAULT_GRADE_POINTS = {
	"A+": 4.0,
	"A": 4.0,
	"A-": 3.7,
	"B+": 3.3,
	"B": 3.0,
	"B-": 2.7,
	"C+": 2.3,
	"C": 2.0,
	"C-": 1.7,
	"D": 1.0,
	"F": 0.0,
}


def configure_academics() -> None:
	"""Add relationship and policy fields without replacing Education DocTypes."""
	configure_academic_year()
	create_custom_fields(
		{
			"Degree": [
				_field(
					"talisma_degree_column_2",
					"",
					"Column Break",
					insert_after="degree_code",
				),
			],
			"Program": [
				_field("talisma_program_code", "Program Code", "Data", insert_after="program_name", reqd=1, unique=1, in_list_view=1),
				_field("talisma_degree", "Degree", "Link", "Degree", "program_abbreviation", reqd=1, in_list_view=1),
			],
			"Program Course": [
				_field("talisma_course_code", "Course Code", "Data", insert_after="course", read_only=1, fetch_from="course.talisma_course_code", in_list_view=1),
				_field("talisma_credit_hours", "Credits", "Float", insert_after="course_name", read_only=1, fetch_from="course.talisma_credit_hours", in_list_view=1),
				_field("talisma_course_type", "Course Type", "Data", insert_after="talisma_credit_hours", read_only=1, fetch_from="course.talisma_course_type", in_list_view=1),
				_field("talisma_academic_term", "Academic Term", "Link", "Academic Term", "talisma_course_type", read_only=1, fetch_from="course.talisma_effective_term", in_list_view=1),
			],
			"Course": [
				_field("talisma_course_code", "Course Code", "Data", insert_after="course_name", reqd=1, unique=1, in_list_view=1),
				_field("talisma_course_name", "Course Name", "Data", insert_after="talisma_course_code", reqd=1, unique=1, in_list_view=1),
				_field("talisma_program", "Program", "Link", "Program", "talisma_academic_unit", in_list_view=1),
				_field("talisma_course_type", "Course Type", "Select", COURSE_TYPES, "talisma_course_level", reqd=1),
				_field("talisma_hours", "Hours", "Float", insert_after="talisma_credit_hours", reqd=1, precision="1"),
				_field("talisma_course_details_section", "Course Details", "Section Break", insert_after="course_name"),
				_field("talisma_course_details_column_2", "", "Column Break", insert_after="talisma_credit_hours"),
				_field("talisma_course_details_column_3", "", "Column Break", insert_after="talisma_course_level"),
				_field("talisma_retake_section", "Retake Configuration", "Section Break", insert_after="talisma_repeatable"),
				_field("talisma_retake_values_section", "", "Section Break", insert_after="talisma_repeatable"),
				_field("talisma_max_retake_attempts", "Maximum Retake Attempts", "Int", insert_after="talisma_retake_values_section", default=1),
				_field("talisma_gpa_attempt_policy", "GPA Attempt Policy", "Select", "Highest Grade Counts\nLatest Grade Counts\nAverage Grade Counts", "talisma_retake_column_2", default="Highest Grade Counts"),
				_field("talisma_prerequisites_section", "Prerequisites", "Section Break", insert_after="talisma_gpa_attempt_policy"),
				_field("talisma_prerequisites", "Prerequisites", "Table", "Talisma Course Prerequisite", "talisma_prerequisites_section"),
			],
			"Course Topic": [
				_field("talisma_unit_number", "Unit Number", "Int", insert_after="topic", reqd=1, in_list_view=1),
			],
			"Course Enrollment": [
				_field("talisma_attempt_number", "Attempt Number", "Int", insert_after="enrollment_date", read_only=1, in_list_view=1),
				_field("talisma_academic_term", "Academic Term", "Link", "Academic Term", "talisma_attempt_number", read_only=1),
				_field("talisma_grade_earned", "Grade Earned", "Data", insert_after="talisma_academic_term", read_only=1),
				_field("talisma_grade_points", "Grade Points", "Float", insert_after="talisma_grade_earned", read_only=1),
				_field("talisma_completion_status", "Completion Status", "Select", "In Progress\nCompleted\nDropped\nWithdrawn\nFailed", "talisma_grade_points", read_only=1, default="In Progress"),
				_field("talisma_status_date", "Status Date", "Date", insert_after="talisma_completion_status", read_only=1),
				_field("talisma_status_reason", "Status Reason", "Small Text", insert_after="talisma_status_date", read_only=1),
			],
		},
		update=False,
	)
	_backfill_course_names()
	_backfill_course_hours()
	_backfill_prerequisite_course_codes()
	_configure_degree_layout()
	_configure_course_layout()
	configure_grading_scales()
	completion_field = frappe.db.get_value(
		"Custom Field",
		{"dt": "Course Enrollment", "fieldname": "talisma_completion_status"},
		"name",
	)
	if completion_field:
		frappe.db.set_value(
			"Custom Field",
			completion_field,
			"options",
			"In Progress\nCompleted\nDropped\nWithdrawn\nFailed",
			update_modified=False,
		)
		frappe.clear_cache(doctype="Course Enrollment")
	for doctype, fieldname, prop, value, prop_type in (
		("Program", "program_abbreviation", "reqd", 1, "Check"),
		("Course", "talisma_credit_hours", "label", "Credits", "Data"),
		("Course", "talisma_credit_hours", "reqd", 1, "Check"),
		("Course", "talisma_effective_term", "label", "Academic Term", "Data"),
		("Course", "talisma_effective_term", "reqd", 0, "Check"),
		("Course", "talisma_repeatable", "label", "Retake Course", "Data"),
		("Course", "default_grading_scale", "label", "Grade Scale", "Data"),
		("Course", "topics", "label", "Topics", "Data"),
		("Course", "talisma_max_retake_attempts", "mandatory_depends_on", "eval:doc.talisma_repeatable == 1", "Data"),
		("Course", "talisma_max_retake_attempts", "depends_on", "", "Data"),
		("Course", "talisma_max_retake_attempts", "read_only_depends_on", "eval:!doc.talisma_repeatable", "Data"),
		("Course", "talisma_gpa_attempt_policy", "label", "GPA Attempt Policy", "Data"),
		("Course", "talisma_gpa_attempt_policy", "options", "Highest Grade Counts\nLatest Grade Counts\nAverage Grade Counts", "Text"),
		("Course", "talisma_gpa_attempt_policy", "default", "Highest Grade Counts", "Data"),
		("Course", "talisma_gpa_attempt_policy", "depends_on", "", "Data"),
		("Course", "talisma_gpa_attempt_policy", "read_only_depends_on", "eval:!doc.talisma_repeatable", "Data"),
		("Course", "talisma_gpa_attempt_policy", "mandatory_depends_on", "eval:doc.talisma_repeatable == 1", "Data"),
		("Program Course", "talisma_credit_hours", "label", "Credits", "Data"),
		("Course Topic", "topic", "insert_after", "talisma_unit_number", "Data"),
	):
		make_property_setter(doctype, fieldname, prop, value, prop_type)
	_seed_degrees_and_backfill()


def _configure_course_layout() -> None:
	"""Keep the Course master focused on identity and credit configuration."""
	visible_layout = [
		"talisma_course_information_section",
		"talisma_course_code",
		"column_break_tflc",
		"talisma_course_name",
		"talisma_course_details_section",
		"talisma_credit_hours",
		"talisma_course_level",
		"talisma_course_details_column_2",
		"talisma_hours",
		"talisma_course_type",
		"talisma_retake_section",
		"talisma_repeatable",
		"talisma_retake_values_section",
		"talisma_max_retake_attempts",
		"talisma_retake_column_2",
		"talisma_gpa_attempt_policy",
		"talisma_prerequisites_section",
		"talisma_prerequisites",
	]
	hidden_fields = [
		"talisma_academic_unit",
		"talisma_program",
		"department",
		"hero_image",
		"default_grading_scale",
		"talisma_subject_code",
		"talisma_catalog_number",
		"talisma_course_configuration_section",
		"talisma_grading_basis",
		"talisma_effective_term",
		"talisma_course_configuration_column_2",
		"description",
		"talisma_course_details_column_3",
		"section_break_6",
		"topics",
	]

	current_order = [field.fieldname for field in frappe.get_meta("Course").fields]
	remaining = [
		fieldname
		for fieldname in current_order
		if fieldname not in visible_layout and fieldname not in hidden_fields and fieldname != "course_name"
	]
	make_property_setter(
		"Course",
		None,
		"field_order",
		json.dumps(visible_layout + ["course_name"] + hidden_fields + remaining),
		"Data",
		for_doctype=True,
	)
	for fieldname in hidden_fields:
		make_property_setter("Course", fieldname, "reqd", 0, "Check")
		make_property_setter("Course", fieldname, "hidden", 1, "Check")
	for fieldname in visible_layout:
		make_property_setter("Course", fieldname, "hidden", 0, "Check")

	frappe.clear_cache(doctype="Course")


def _backfill_course_names() -> None:
	"""Populate the editable display field from the standard Course naming field."""
	if not frappe.get_meta("Course").has_field("talisma_course_name"):
		return
	for course in frappe.get_all("Course", fields=["name", "course_name", "talisma_course_name"]):
		if not course.talisma_course_name:
			frappe.db.set_value(
				"Course",
				course.name,
				"talisma_course_name",
				course.course_name or course.name,
				update_modified=False,
			)


def _backfill_course_hours() -> None:
	"""Initialize Hours from existing Credits without changing legacy credit values."""
	if not frappe.get_meta("Course").has_field("talisma_hours"):
		return
	for course in frappe.get_all(
		"Course",
		fields=["name", "talisma_credit_hours", "talisma_hours", "talisma_gpa_attempt_policy"],
	):
		values = {}
		if not flt(course.talisma_hours) and flt(course.talisma_credit_hours):
			values["talisma_hours"] = course.talisma_credit_hours
		if not course.talisma_gpa_attempt_policy:
			values["talisma_gpa_attempt_policy"] = "Highest Grade Counts"
		if values:
			frappe.db.set_value(
				"Course",
				course.name,
				values,
				update_modified=False,
			)


def _backfill_prerequisite_course_codes() -> None:
	"""Populate the display-only code for prerequisite rows created before this column existed."""
	if not frappe.get_meta("Talisma Course Prerequisite").has_field("course_code"):
		return
	for row in frappe.get_all(
		"Talisma Course Prerequisite",
		fields=["name", "course", "course_code"],
	):
		if row.course and not row.course_code:
			frappe.db.set_value(
				"Talisma Course Prerequisite",
				row.name,
				"course_code",
				frappe.db.get_value("Course", row.course, "talisma_course_code"),
				update_modified=False,
			)


def _configure_degree_layout() -> None:
	"""Display Degree Code and Degree Name together on the first row."""
	layout = [
		"degree_code",
		"talisma_degree_column_2",
		"degree_name",
		"programs_section",
		"programs_html",
	]
	current_order = [field.fieldname for field in frappe.get_meta("Degree").fields]
	remaining = [fieldname for fieldname in current_order if fieldname not in layout]
	make_property_setter(
		"Degree",
		None,
		"field_order",
		json.dumps(layout + remaining),
		"Data",
		for_doctype=True,
	)
	frappe.clear_cache(doctype="Degree")


def configure_academic_year() -> None:
	"""Add an editable institutional code and compact two-column layout."""
	create_custom_fields(
		{
			"Academic Year": [
				_field(
					"talisma_academic_year_section",
					"",
					"Section Break",
					insert_after="academic_year_name",
				),
				_field(
					"talisma_academic_year_code",
					"Academic Year Code",
					"Data",
					insert_after="academic_year_name",
					unique=1,
					in_list_view=1,
					in_standard_filter=1,
				),
				_field(
					"talisma_academic_year_column_2",
					"",
					"Column Break",
					insert_after="year_start_date",
				),
			],
		},
		update=True,
	)
	_backfill_academic_year_codes()
	make_property_setter(
		"Academic Year", "talisma_academic_year_code", "reqd", 1, "Check"
	)
	make_property_setter(
		"Academic Year", "talisma_academic_year_code", "unique", 1, "Check"
	)
	make_property_setter(
		"Academic Year",
		None,
		"title_field",
		"academic_year_name",
		"Data",
		for_doctype=True,
	)

	layout = [
		"talisma_academic_year_section",
		"academic_year_name",
		"year_start_date",
		"talisma_academic_year_column_2",
		"talisma_academic_year_code",
		"year_end_date",
	]
	current_order = [field.fieldname for field in frappe.get_meta("Academic Year").fields]
	remaining = [fieldname for fieldname in current_order if fieldname not in layout]
	make_property_setter(
		"Academic Year",
		None,
		"field_order",
		json.dumps(layout + remaining),
		"Data",
		for_doctype=True,
	)
	_configure_academic_year_list_view()
	frappe.clear_cache(doctype="Academic Year")


def _configure_academic_year_list_view() -> None:
	"""Keep the institutional name first and arrange the remaining list columns."""
	fields = json.dumps(
		[
			{"fieldname": "talisma_academic_year_code", "label": "Academic Year Code"},
			{"fieldname": "year_start_date", "label": "Year Start Date"},
			{"fieldname": "year_end_date", "label": "Year End Date"},
		]
	)
	if frappe.db.exists("List View Settings", "Academic Year"):
		frappe.db.set_value("List View Settings", "Academic Year", "fields", fields)
		return

	doc = frappe.new_doc("List View Settings")
	doc.name = "Academic Year"
	doc.fields = fields
	doc.insert(ignore_permissions=True)


def prepare_academic_year(doc, method=None) -> None:
	"""Generate the code only when it has not been manually supplied."""
	if doc.meta.has_field("talisma_academic_year_code") and not doc.talisma_academic_year_code:
		doc.talisma_academic_year_code = _default_academic_year_code(doc)


def validate_academic_year(doc, method=None) -> None:
	if doc.year_start_date and doc.year_end_date:
		if getdate(doc.year_start_date) >= getdate(doc.year_end_date):
			frappe.throw(_("Year Start Date must be earlier than Year End Date."))

	if not doc.meta.has_field("talisma_academic_year_code"):
		return
	code = (doc.talisma_academic_year_code or "").strip()
	if not code:
		frappe.throw(_("Academic Year Code is required."))
	doc.talisma_academic_year_code = code
	duplicate = frappe.db.exists(
		"Academic Year",
		{
			"talisma_academic_year_code": code,
			"name": ["!=", doc.name or ""],
		},
	)
	if duplicate:
		frappe.throw(
			_("Academic Year Code {0} is already assigned to {1}.").format(
				frappe.bold(code), frappe.bold(duplicate)
			)
		)


def _backfill_academic_year_codes() -> None:
	used_codes = {
		code
		for code in frappe.get_all(
			"Academic Year",
			filters={"talisma_academic_year_code": ["is", "set"]},
			pluck="talisma_academic_year_code",
		)
		if code
	}
	for row in frappe.get_all(
		"Academic Year",
		filters={"talisma_academic_year_code": ["is", "not set"]},
		fields=["name", "academic_year_name", "year_start_date"],
		order_by="year_start_date asc, name asc",
	):
		base = _default_academic_year_code(row)
		candidate = base
		suffix = 2
		while candidate in used_codes:
			candidate = f"{base}-{suffix}"
			suffix += 1
		frappe.db.set_value(
			"Academic Year",
			row.name,
			"talisma_academic_year_code",
			candidate,
			update_modified=False,
		)
		used_codes.add(candidate)


def _default_academic_year_code(doc) -> str:
	if doc.get("year_start_date"):
		return f"AY{getdate(doc.year_start_date).year}"
	match = re.search(r"\b(\d{4})\b", doc.get("academic_year_name") or doc.get("name") or "")
	if match:
		return f"AY{match.group(1)}"
	frappe.throw(_("Enter Year Start Date to generate Academic Year Code."))


def configure_grading_scales() -> None:
	"""Extend Education's grading policy records without replacing its DocTypes."""
	create_custom_fields(
		{
			"Grading Scale Interval": [
				_field(
					"talisma_maximum_score",
					"Maximum Score",
					"Percent",
					insert_after="threshold",
					reqd=1,
					precision="2",
					in_list_view=1,
				),
				_field(
					"talisma_grade_points",
					"Grade Points",
					"Float",
					insert_after="talisma_maximum_score",
					reqd=1,
					precision="2",
					in_list_view=1,
				),
			],
		},
		update=True,
	)
	for doctype, fieldname, prop, value, prop_type in (
		("Grading Scale", "grading_scale_name", "label", "Grade Scale Name", "Data"),
		("Grading Scale", "description", "insert_after", "grading_scale_name", "Data"),
		("Grading Scale", "grading_intervals_section", "label", "Grade Definitions", "Data"),
		("Grading Scale", "grading_intervals_section", "insert_after", "description", "Data"),
		("Grading Scale", "intervals", "label", "Grade Definitions", "Data"),
		("Grading Scale Interval", "grade_code", "label", "Letter Grade", "Data"),
		("Grading Scale Interval", "grade_description", "label", "Name", "Data"),
		("Grading Scale Interval", "grade_description", "fieldtype", "Data", "Select"),
		("Grading Scale Interval", "grade_description", "reqd", 1, "Check"),
		("Grading Scale Interval", "grade_description", "insert_after", "grade_code", "Data"),
		("Grading Scale Interval", "threshold", "label", "Minimum Score", "Data"),
		("Grading Scale Interval", "threshold", "precision", "2", "Data"),
		("Grading Scale Interval", "threshold", "insert_after", "grade_description", "Data"),
	):
		make_property_setter(doctype, fieldname, prop, value, prop_type)
	_backfill_grading_scale_definitions()
	frappe.clear_cache(doctype="Grading Scale")
	frappe.clear_cache(doctype="Grading Scale Interval")


def validate_grading_scale(doc, method=None) -> None:
	"""Validate and consistently order US higher-education grade definitions."""
	seen_grades = {}
	rows = list(doc.intervals or [])
	for row in rows:
		row_number = row.idx or rows.index(row) + 1
		letter_grade = (row.grade_code or "").strip()
		grade_name = (row.grade_description or "").strip()
		if not letter_grade:
			frappe.throw(_("Row {0}: Letter Grade is required.").format(row_number))
		if not grade_name:
			frappe.throw(_("Row {0}: Name is required for grade {1}.").format(row_number, letter_grade))
		grade_key = letter_grade.casefold()
		if grade_key in seen_grades:
			frappe.throw(
				_("Letter Grade {0} appears more than once in this Grade Scale (rows {1} and {2}).").format(
					letter_grade, seen_grades[grade_key], row_number
				)
			)
		seen_grades[grade_key] = row_number
		if row.talisma_maximum_score in (None, ""):
			frappe.throw(_("Row {0}: Maximum Score is required for grade {1}.").format(row_number, letter_grade))
		if row.talisma_grade_points in (None, ""):
			frappe.throw(_("Row {0}: Grade Points are required for grade {1}.").format(row_number, letter_grade))

		minimum_score = flt(row.threshold, 2)
		maximum_score = flt(row.talisma_maximum_score, 2)
		grade_points = flt(row.talisma_grade_points, 2)
		if minimum_score < 0 or minimum_score > 100 or maximum_score < 0 or maximum_score > 100:
			frappe.throw(_("Row {0}: scores for grade {1} must be between 0 and 100.").format(row_number, letter_grade))
		if minimum_score > maximum_score:
			frappe.throw(
				_("Row {0}: Minimum Score cannot be greater than Maximum Score for grade {1}.").format(
					row_number, letter_grade
				)
			)
		if grade_points < 0:
			frappe.throw(_("Row {0}: Grade Points cannot be negative for grade {1}.").format(row_number, letter_grade))
		row.grade_code = letter_grade
		row.grade_description = grade_name

	rows.sort(key=lambda row: flt(row.threshold), reverse=True)
	for index, row in enumerate(rows, start=1):
		row.idx = index
	for higher, lower in zip(rows, rows[1:]):
		if flt(lower.talisma_maximum_score, 2) >= flt(higher.threshold, 2):
			frappe.throw(
				_("Score ranges overlap: {0} ({1}–{2}) and {3} ({4}–{5}).").format(
					higher.grade_code,
					flt(higher.threshold, 2),
					flt(higher.talisma_maximum_score, 2),
					lower.grade_code,
					flt(lower.threshold, 2),
					flt(lower.talisma_maximum_score, 2),
				)
			)
	doc.set("intervals", rows)


def _backfill_grading_scale_definitions() -> None:
	for scale_name in frappe.get_all("Grading Scale", pluck="name"):
		rows = frappe.get_all(
			"Grading Scale Interval",
			filters={"parent": scale_name, "parenttype": "Grading Scale"},
			fields=["name", "grade_code", "grade_description", "threshold", "talisma_maximum_score", "talisma_grade_points"],
			order_by="threshold desc, idx asc",
		)
		for index, row in enumerate(rows):
			grade = (row.grade_code or "").strip()
			maximum = 100.0 if index == 0 else max(0.0, flt(rows[index - 1].threshold, 2) - 0.01)
			current_name = (row.grade_description or "").strip()
			if not current_name or "%" in current_name or "–" in current_name or " - " in current_name:
				current_name = DEFAULT_GRADE_NAMES.get(grade.upper(), grade)
			points = row.talisma_grade_points
			if points in (None, ""):
				points = DEFAULT_GRADE_POINTS.get(grade.upper(), 0.0)
			frappe.db.set_value(
				"Grading Scale Interval",
				row.name,
				{
					"grade_description": current_name,
					"talisma_maximum_score": row.talisma_maximum_score if row.talisma_maximum_score not in (None, "") else maximum,
					"talisma_grade_points": points,
					"idx": index + 1,
				},
				update_modified=False,
			)


def _field(fieldname, label, fieldtype, options="", insert_after="", **values):
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"options": options,
		"insert_after": insert_after,
		**values,
	}


def _seed_degrees_and_backfill() -> None:
	for degree_name, degree_code in (
		("Bachelor of Science", "BS"),
		("Master of Science", "MS"),
	):
		if not frappe.db.exists("Degree", degree_name):
			frappe.get_doc({
				"doctype": "Degree",
				"degree_name": degree_name,
				"degree_code": degree_code,
			}).insert(ignore_permissions=True)

	for program in frappe.get_all("Program", fields=["name", "program_abbreviation"]):
		degree = "Master of Science" if program.name.lower().startswith("master") else "Bachelor of Science"
		code = program.program_abbreviation or _abbreviation(program.name)
		frappe.db.set_value(
			"Program",
			program.name,
			{"talisma_program_code": code, "talisma_degree": degree},
			update_modified=False,
		)

	program_by_course = {
		row.course: row.parent
		for row in frappe.get_all(
			"Program Course",
			filters={"parenttype": "Program"},
			fields=["parent", "course"],
			order_by="idx",
		)
	}
	for course in frappe.get_all(
		"Course",
		fields=["name", "talisma_subject_code", "talisma_catalog_number", "talisma_repeatable"],
	):
		code = "-".join(filter(None, (course.talisma_subject_code, course.talisma_catalog_number)))
		frappe.db.set_value(
			"Course",
			course.name,
			{
				"talisma_course_code": code or _abbreviation(course.name),
				"talisma_program": program_by_course.get(course.name),
				"talisma_course_type": "Core",
				"talisma_max_retake_attempts": 3 if course.talisma_repeatable else 1,
			},
			update_modified=False,
		)

	for grade, points in {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}.items():
		for row in frappe.get_all("Grading Scale Interval", filters={"grade_code": grade}, pluck="name"):
			frappe.db.set_value("Grading Scale Interval", row, "talisma_grade_points", points, update_modified=False)
	_backfill_course_attempts()


def _backfill_course_attempts() -> None:
	enrollments = frappe.get_all(
		"Course Enrollment",
		fields=["name", "student", "course", "enrollment_date", "creation"],
		order_by="student, course, enrollment_date, creation",
	)
	attempts = {}
	for row in enrollments:
		key = (row.student, row.course)
		attempts[key] = attempts.get(key, 0) + 1
		term = frappe.db.get_value("Course", row.course, "talisma_effective_term")
		frappe.db.set_value(
			"Course Enrollment",
			row.name,
			{
				"talisma_attempt_number": attempts[key],
				"talisma_academic_term": term,
				"talisma_completion_status": "In Progress",
			},
			update_modified=False,
		)
	for result in frappe.get_all(
		"Assessment Result",
		filters={"docstatus": 1},
		fields=["student", "course", "grade", "grading_scale"],
		order_by="modified",
	):
		enrollment = frappe.db.get_value(
			"Course Enrollment",
			{"student": result.student, "course": result.course},
			"name",
			order_by="talisma_attempt_number desc, enrollment_date desc, creation desc",
		)
		if enrollment:
			points = _grade_points(result.grading_scale, result.grade)
			frappe.db.set_value(
				"Course Enrollment",
				enrollment,
				{
					"talisma_grade_earned": result.grade,
					"talisma_grade_points": points,
					"talisma_completion_status": "Failed" if points == 0 else "Completed",
				},
				update_modified=False,
			)


def seed_demo_course_categories() -> None:
	for program, code, description in (
		("Bachelor of Science in Computer Science", "BSCS-CORE", "Computer Science Core"),
		("Master of Science in Data Science", "MSDS-CORE", "Data Science Core"),
	):
		if not frappe.db.exists("Program", program):
			continue
		doc = frappe.get_doc("Course Category", code) if frappe.db.exists("Course Category", code) else frappe.new_doc("Course Category")
		doc.code = code
		doc.program = program
		doc.description = description
		doc.set("courses", [])
		for row in frappe.get_all(
			"Program Course",
			filters={"parent": program, "parenttype": "Program"},
			fields=["course"],
			order_by="idx",
		):
			doc.append("courses", {"course": row.course})
		doc.save(ignore_permissions=True)
	_seed_demo_course_details()


def _seed_demo_course_details() -> None:
	prerequisites = {
		"Data Structures": [("Introduction to Computer Science", "C")],
		"Database Systems": [("Introduction to Computer Science", "C")],
		"Software Engineering": [("Data Structures", "C")],
		"Applied Machine Learning": [("Foundations of Data Science", "B")],
	}
	for course_name, rows in prerequisites.items():
		if not frappe.db.exists("Course", course_name):
			continue
		course = frappe.get_doc("Course", course_name)
		course.set("talisma_prerequisites", [])
		for prerequisite, minimum_grade in rows:
			course.append("talisma_prerequisites", {
				"course": prerequisite,
				"minimum_required_grade": minimum_grade,
				"mandatory": 1,
			})
		course.save(ignore_permissions=True)

	intro_course = "Introduction to Computer Science"
	if not frappe.db.exists("Course", intro_course):
		return
	topics = (
		(1, "Introduction to Programming"),
		(2, "Variables and Data Types"),
		(3, "Conditional Statements"),
		(4, "Loops"),
		(5, "Functions"),
	)
	for _, topic_name in topics:
		if not frappe.db.exists("Topic", topic_name):
			frappe.get_doc({"doctype": "Topic", "topic_name": topic_name}).insert(ignore_permissions=True)
	course = frappe.get_doc("Course", intro_course)
	course.set("topics", [])
	for unit_number, topic_name in topics:
		course.append("topics", {"talisma_unit_number": unit_number, "topic": topic_name})
	course.save(ignore_permissions=True)


def validate_program(doc, method=None) -> None:
	if not _is_demo():
		return
	if not doc.talisma_program_code or not doc.program_abbreviation or not doc.talisma_degree:
		frappe.throw(_("Program Code, Program Abbreviation, and Degree are required."))
	_validate_unique_rows(doc.courses, "course", _("A Course can appear only once in a Program."))


def prepare_course_name(doc, method=None) -> None:
	"""Keep the editable Course Name and standard naming field synchronized."""
	if not _is_demo() or not doc.meta.has_field("talisma_course_name"):
		return
	if doc.talisma_course_name:
		doc.course_name = doc.talisma_course_name.strip()
	elif doc.course_name:
		doc.talisma_course_name = doc.course_name.strip()


def validate_course(doc, method=None) -> None:
	if not _is_demo():
		return
	if not all((doc.talisma_course_code, doc.talisma_course_name, doc.talisma_course_type)):
		frappe.throw(_("Course Code, Course Name, and Course Type are required."))
	if flt(doc.talisma_credit_hours) <= 0:
		frappe.throw(_("Credits must be greater than zero."))
	if flt(doc.talisma_hours) <= 0:
		frappe.throw(_("Hours must be greater than zero."))
	if doc.talisma_repeatable and (doc.talisma_max_retake_attempts or 0) < 2:
		frappe.throw(_("Maximum Retake Attempts must be at least 2 when Retake Course is enabled."))
	if doc.talisma_repeatable and not doc.talisma_gpa_attempt_policy:
		frappe.throw(_("GPA Attempt Policy is required when Retake Course is enabled."))
	if not doc.talisma_repeatable:
		doc.talisma_max_retake_attempts = 1
	_validate_unique_rows(doc.talisma_prerequisites, "course", _("A prerequisite Course can appear only once."))
	for row in doc.talisma_prerequisites:
		if row.course == doc.name:
			frappe.throw(_("A Course cannot be its own prerequisite."))


def validate_course_category(doc, method=None) -> None:
	if not _is_demo():
		return
	_validate_unique_rows(doc.courses, "course", _("A Course can appear only once in a Course Category."))
	invalid = [
		row.course
		for row in doc.courses
		if frappe.db.get_value("Course", row.course, "talisma_program") != doc.program
	]
	if invalid:
		frappe.throw(
			_("These Courses do not belong to Program {0}: {1}").format(
				frappe.bold(doc.program), ", ".join(invalid)
			)
		)


def validate_course_enrollment(doc, method=None) -> None:
	if not _is_demo() or not doc.student or not doc.course:
		return
	from talisma_sis.student_records import active_holds

	registration_holds = [row for row in active_holds(doc.student) if row.blocks_registration]
	if registration_holds:
		frappe.throw(
			_("Registration blocked by active Student Hold(s): {0}").format(
				", ".join(f"{row.hold_type}: {row.reason}" for row in registration_holds)
			),
			title=_("Registration Hold"),
		)
	course = frappe.db.get_value(
		"Course",
		doc.course,
		["talisma_repeatable", "talisma_max_retake_attempts", "talisma_effective_term"],
		as_dict=True,
	) or {}
	previous = frappe.get_all(
		"Course Enrollment",
		filters={"student": doc.student, "course": doc.course, "name": ("!=", doc.name or "")},
		pluck="name",
	)
	final_results = frappe.get_all(
		"Assessment Result",
		filters={"student": doc.student, "course": doc.course, "docstatus": 1},
		pluck="name",
	)
	if not course.get("talisma_repeatable") and final_results:
		frappe.throw(
			_("Registration blocked: {0} has already been completed and is not configured for retakes.").format(
				frappe.bold(doc.course)
			)
		)
	max_attempts = int(course.get("talisma_max_retake_attempts") or 1)
	if course.get("talisma_repeatable") and len(previous) >= max_attempts:
		frappe.throw(
			_("Registration blocked: the maximum of {0} attempts for {1} has been reached.").format(
				max_attempts, frappe.bold(doc.course)
			)
		)
	_validate_prerequisites(doc.student, doc.course)
	doc.talisma_attempt_number = len(previous) + 1
	doc.talisma_academic_term = _course_enrollment_term(doc) or course.get("talisma_effective_term")
	doc.talisma_completion_status = doc.talisma_completion_status or "In Progress"


def sync_assessment_attempt(doc, method=None) -> None:
	if not _is_demo() or not doc.student or not doc.course:
		return
	enrollment = frappe.db.get_value(
		"Course Enrollment",
		{"student": doc.student, "course": doc.course},
		"name",
		order_by="talisma_attempt_number desc, enrollment_date desc, creation desc",
	)
	if not enrollment:
		return
	points = _grade_points(doc.grading_scale, doc.grade)
	frappe.db.set_value(
		"Course Enrollment",
		enrollment,
		{
			"talisma_grade_earned": doc.grade,
			"talisma_grade_points": points,
			"talisma_completion_status": "Failed" if points == 0 else "Completed",
		},
		update_modified=False,
	)
	refresh_academic_standing(doc.student)


def clear_assessment_attempt(doc, method=None) -> None:
	if not _is_demo() or not doc.student or not doc.course:
		return
	enrollment = frappe.db.get_value(
		"Course Enrollment",
		{"student": doc.student, "course": doc.course},
		"name",
		order_by="talisma_attempt_number desc, enrollment_date desc, creation desc",
	)
	if enrollment:
		frappe.db.set_value(
			"Course Enrollment",
			enrollment,
			{"talisma_grade_earned": None, "talisma_grade_points": None, "talisma_completion_status": "In Progress"},
			update_modified=False,
		)
		refresh_academic_standing(doc.student)


def refresh_academic_standing_for_enrollment(doc, method=None) -> None:
	"""Keep derived standing history synchronized with registration changes."""
	if _is_demo() and doc.student:
		refresh_academic_standing(doc.student)


def refresh_academic_standing_for_course(doc, method=None) -> None:
	"""Reapply a changed retake policy to students enrolled in this Course."""
	if not _is_demo() or not doc.name:
		return
	students = set(frappe.get_all(
		"Course Enrollment",
		filters={"course": doc.name, "docstatus": ("!=", 2)},
		pluck="student",
	))
	for student in students:
		refresh_academic_standing(student)


def refresh_academic_standing(student: str) -> list[str]:
	"""Recalculate term and cumulative GPA history from authoritative course attempts."""
	if not _is_demo() or not student or not frappe.db.exists("Student", student):
		return []
	attempts = frappe.get_all(
		"Course Enrollment",
		filters={"student": student, "docstatus": ("!=", 2)},
		fields=[
			"name", "program", "program_enrollment", "course", "talisma_academic_term",
			"talisma_grade_points", "talisma_completion_status", "talisma_attempt_number",
			"enrollment_date", "creation",
		],
	)
	gpa_attempt_names = _gpa_attempt_names(attempts)
	term_attempts: dict[str, list] = {}
	for attempt in attempts:
		term = attempt.talisma_academic_term or _course_enrollment_term(attempt)
		if not term:
			continue
		if attempt.talisma_academic_term != term:
			frappe.db.set_value(
				"Course Enrollment", attempt.name, "talisma_academic_term", term, update_modified=False
			)
		term_attempts.setdefault(term, []).append(attempt)

	# Keep the starting term visible before its first course outcome is posted.
	for row in frappe.get_all(
		"Program Enrollment",
		filters={"student": student, "docstatus": ("!=", 2), "academic_term": ("is", "set")},
		fields=["academic_term"],
	):
		term_attempts.setdefault(row.academic_term, [])

	terms = sorted(term_attempts, key=_academic_term_sort_key)
	cumulative_quality_points = 0.0
	cumulative_attempted_credits = 0.0
	updated = []
	for term in terms:
		term_quality_points = 0.0
		term_attempted_credits = 0.0
		term_earned_credits = 0.0
		program = None
		for attempt in term_attempts[term]:
			program = program or attempt.program
			status = attempt.talisma_completion_status or "In Progress"
			if status not in {"Completed", "Failed"}:
				continue
			if attempt.name not in gpa_attempt_names:
				continue
			credits = flt(frappe.db.get_value("Course", attempt.course, "talisma_credit_hours"))
			points = flt(attempt.talisma_grade_points)
			term_attempted_credits += credits
			term_quality_points += credits * points
			if status == "Completed":
				term_earned_credits += credits
		cumulative_quality_points += term_quality_points
		cumulative_attempted_credits += term_attempted_credits
		term_gpa = term_quality_points / term_attempted_credits if term_attempted_credits else 0
		cumulative_gpa = (
			cumulative_quality_points / cumulative_attempted_credits
			if cumulative_attempted_credits else 0
		)
		program = program or frappe.db.get_value(
			"Program Enrollment",
			{"student": student, "academic_term": term, "docstatus": ("!=", 2)},
			"program",
		)
		values = {
			"program": program,
			"standing": _standing_from_gpa(cumulative_gpa, cumulative_attempted_credits),
			"term_gpa": term_gpa,
			"cumulative_gpa": cumulative_gpa,
			"attempted_credits": term_attempted_credits,
			"earned_credits": term_earned_credits,
			"effective_date": _academic_term_effective_date(term),
			"reason": "Automatically calculated from course outcomes",
		}
		name = frappe.db.get_value(
			"Talisma Student Academic Standing", {"student": student, "academic_term": term}, "name"
		)
		if name:
			frappe.db.set_value("Talisma Student Academic Standing", name, values, update_modified=False)
		else:
			name = frappe.get_doc({
				"doctype": "Talisma Student Academic Standing",
				"student": student,
				"academic_term": term,
				**values,
			}).insert(ignore_permissions=True).name
		updated.append(name)
	return updated


def _gpa_attempt_names(attempts: list) -> set[str]:
	"""Select course attempts that contribute to GPA using each Course's retake policy."""
	terminal = [
		attempt
		for attempt in attempts
		if (attempt.talisma_completion_status or "In Progress") in {"Completed", "Failed"}
	]
	selected = {attempt.name for attempt in terminal}
	by_course: dict[str, list] = {}
	for attempt in terminal:
		by_course.setdefault(attempt.course, []).append(attempt)
	if not by_course:
		return selected

	policies = {
		row.name: row.talisma_gpa_attempt_policy or "Highest Grade Counts"
		for row in frappe.get_all(
			"Course",
			filters={"name": ("in", list(by_course))},
			fields=["name", "talisma_repeatable", "talisma_gpa_attempt_policy"],
		)
		if row.talisma_repeatable
	}
	for course, course_attempts in by_course.items():
		policy = policies.get(course)
		if not policy or policy == "Average Grade Counts" or len(course_attempts) < 2:
			continue
		selected.difference_update(attempt.name for attempt in course_attempts)
		if policy == "Latest Grade Counts":
			winner = max(
				course_attempts,
				key=lambda attempt: (
					int(attempt.talisma_attempt_number or 0),
					getdate(attempt.enrollment_date) if attempt.enrollment_date else getdate("1900-01-01"),
					attempt.creation,
				),
			)
		else:
			winner = max(
				course_attempts,
				key=lambda attempt: (
					flt(attempt.talisma_grade_points),
					int(attempt.talisma_attempt_number or 0),
					attempt.creation,
				),
			)
		selected.add(winner.name)
	return selected


def _course_enrollment_term(doc) -> str | None:
	section = doc.get("talisma_course_section")
	if section:
		term = frappe.db.get_value("Talisma Class Section", section, "academic_term")
		if term:
			return term
	program_enrollment = doc.get("program_enrollment")
	return (
		frappe.db.get_value("Program Enrollment", program_enrollment, "academic_term")
		if program_enrollment else None
	)


def _academic_term_sort_key(term: str):
	dates = frappe.db.get_value(
		"Academic Term", term, ["term_start_date", "term_end_date"], as_dict=True
	) or {}
	return (str(dates.get("term_start_date") or dates.get("term_end_date") or "9999-12-31"), term)


def _academic_term_effective_date(term: str):
	dates = frappe.db.get_value(
		"Academic Term", term, ["term_end_date", "term_start_date"], as_dict=True
	) or {}
	return dates.get("term_end_date") or dates.get("term_start_date") or frappe.utils.today()


def _standing_from_gpa(cumulative_gpa: float, attempted_credits: float) -> str:
	if not attempted_credits or cumulative_gpa >= 2.0:
		return "Good Standing"
	if cumulative_gpa >= 1.5:
		return "Warning"
	if cumulative_gpa >= 1.0:
		return "Probation"
	return "Suspension"


@frappe.whitelist()
def get_degree_programs(degree: str) -> list[dict]:
	if not frappe.has_permission("Program", "read"):
		frappe.throw(_("You do not have permission to view Programs."), frappe.PermissionError)
	return frappe.get_all(
		"Program",
		filters={"talisma_degree": degree},
		fields=["name", "talisma_program_code as program_code", "program_name", "program_abbreviation"],
		order_by="program_name",
	)


@frappe.whitelist()
def check_registration_eligibility(student: str, course: str) -> dict:
	"""Run the same prerequisite and retake validator used by Course Enrollment."""
	doc = frappe.new_doc("Course Enrollment")
	doc.student = student
	doc.course = course
	validate_course_enrollment(doc)
	return {
		"eligible": True,
		"attempt_number": doc.talisma_attempt_number,
		"academic_term": doc.talisma_academic_term,
	}


def healthcheck() -> dict:
	degree_meta = frappe.get_meta("Degree")
	program_meta = frappe.get_meta("Program")
	course_meta = frappe.get_meta("Course")
	category_meta = frappe.get_meta("Course Category")
	checks = {
		"degree_master": bool(degree_meta.get_field("degree_code")),
		"program_degree_link": program_meta.get_field("talisma_degree").options == "Degree",
		"program_courses_reused": program_meta.get_field("courses").options == "Program Course",
		"course_category_program": category_meta.get_field("program").options == "Program",
		"course_category_courses_reused": category_meta.get_field("courses").options == "Program Course",
		"course_program_link": course_meta.get_field("talisma_program").options == "Program",
		"course_prerequisites": course_meta.get_field("talisma_prerequisites").options == "Talisma Course Prerequisite",
		"course_topics_reused": course_meta.get_field("topics").options == "Course Topic",
		"course_retake_policy": bool(course_meta.get_field("talisma_max_retake_attempts")),
		"attempt_history_fields": bool(frappe.get_meta("Course Enrollment").get_field("talisma_attempt_number")),
		"degrees_seeded": frappe.db.count("Degree") >= 2,
		"categories_seeded": frappe.db.count("Course Category") >= 2,
		"prerequisites_seeded": frappe.db.count("Talisma Course Prerequisite") >= 4,
		"topics_seeded": frappe.db.count("Course Topic", {"talisma_unit_number": (">", 0)}) >= 5,
		"programs_linked": frappe.db.count("Program", {"talisma_degree": ("is", "set")}) == frappe.db.count("Program"),
		"courses_linked": frappe.db.count("Course", {"talisma_program": ("is", "set")}) == frappe.db.count("Course"),
	}
	return {"ok": all(checks.values()), "checks": checks}


def _validate_prerequisites(student: str, course_name: str) -> None:
	course = frappe.get_doc("Course", course_name)
	missing = []
	for row in course.talisma_prerequisites:
		if not row.mandatory:
			continue
		results = frappe.get_all(
			"Assessment Result",
			filters={"student": student, "course": row.course, "docstatus": 1},
			fields=["grade", "grading_scale"],
			order_by="modified desc",
		)
		if not results or (
			row.minimum_required_grade
			and not any(_grade_meets(result.grade, row.minimum_required_grade, result.grading_scale) for result in results)
		):
			missing.append(
				f"{row.course_name or row.course}"
				+ (f" ({_('minimum grade')} {row.minimum_required_grade})" if row.minimum_required_grade else "")
			)
	if missing:
		frappe.throw(
			_("Registration blocked. Complete these prerequisite Courses first: {0}").format(
				", ".join(missing)
			),
			title=_("Missing Prerequisites"),
		)


def _grade_meets(earned: str, required: str, grading_scale: str | None) -> bool:
	if not earned:
		return False
	if not grading_scale:
		return earned.casefold() == required.casefold()
	thresholds = {
		row.grade_code.casefold(): flt(row.threshold)
		for row in frappe.get_all(
			"Grading Scale Interval",
			filters={"parent": grading_scale, "parenttype": "Grading Scale"},
			fields=["grade_code", "threshold"],
		)
	}
	return (
		earned.casefold() in thresholds
		and required.casefold() in thresholds
		and thresholds[earned.casefold()] >= thresholds[required.casefold()]
	)


def _grade_points(grading_scale: str | None, grade: str | None) -> float | None:
	if not grading_scale or not grade:
		return None
	return frappe.db.get_value(
		"Grading Scale Interval",
		{"parent": grading_scale, "parenttype": "Grading Scale", "grade_code": grade},
		"talisma_grade_points",
	)


def _validate_unique_rows(rows, fieldname: str, message: str) -> None:
	values = [row.get(fieldname) for row in rows if row.get(fieldname)]
	if len(values) != len(set(values)):
		frappe.throw(message)


def _abbreviation(value: str) -> str:
	return "".join(word[0] for word in value.split() if word).upper()[:12]


def _is_demo() -> bool:
	return frappe.local.site == DEMO_SITE
