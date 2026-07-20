"""Reports for the extended Education Admission Intake configuration."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt


def admission_intake_report(filters=None):
	columns = _intake_columns()
	return columns, _intake_rows(frappe._dict(filters or {}))


def open_admission_intakes(filters=None):
	filters = frappe._dict(filters or {})
	filters.status = "Open"
	return _intake_columns(), _intake_rows(filters)


def closed_admission_intakes(filters=None):
	filters = frappe._dict(filters or {})
	filters.status = ("in", ["Closed", "Cancelled", "Archived"])
	return _intake_columns(), _intake_rows(filters)


def program_capacity_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Admission Intake", "admission_intake", "Link", "Student Admission", 180),
		_col("Status", "intake_status", width=100),
		_col("Academic Year", "academic_year", "Link", "Academic Year", 130),
		_col("Academic Term", "academic_term", "Link", "Academic Term", 150),
		_col("Program", "program", "Link", "Program", 210),
		_col("Degree", "degree", "Link", "Degree", 170),
		_col("Academic Unit", "academic_unit", "Link", "Talisma Academic Unit", 170),
		_col("Capacity", "intake_capacity", "Int", width=90),
		_col("Seats Filled", "seats_filled", "Int", width=100),
		_col("Seats Available", "seats_available", "Int", width=110),
		_col("Program Status", "program_status", width=110),
		_col("Application Fee", "application_fee", "Currency", width=120),
	]
	return columns, _program_rows(filters)


def seat_availability_report(filters=None):
	filters = frappe._dict(filters or {})
	filters.only_available = True
	return program_capacity_report(filters)


def program_wise_applications(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Admission Intake", "admission_intake", "Link", "Student Admission", 180),
		_col("Program", "program", "Link", "Program", 220),
		_col("Total Applications", "total_applications", "Int", width=120),
		_col("Draft", "draft", "Int", width=70),
		_col("Submitted", "submitted", "Int", width=90),
		_col("Under Review", "under_review", "Int", width=100),
		_col("Decision Pending", "decision_pending", "Int", width=115),
		_col("Approved", "approved", "Int", width=85),
		_col("Waitlisted", "waitlisted", "Int", width=85),
		_col("Admitted", "admitted", "Int", width=85),
		_col("Rejected", "rejected", "Int", width=85),
		_col("Withdrawn", "withdrawn", "Int", width=90),
		_col("Capacity", "intake_capacity", "Int", width=90),
		_col("Seats Available", "seats_available", "Int", width=110),
	]
	groups = defaultdict(lambda: frappe._dict(
		draft=0, submitted=0, under_review=0, decision_pending=0,
		approved=0, waitlisted=0, admitted=0, rejected=0, withdrawn=0,
	))
	applicant_filters = {"docstatus": ("<", 2), "student_admission": ("is", "set")}
	if filters.get("admission_intake"):
		applicant_filters["student_admission"] = filters.admission_intake
	if filters.get("program"):
		applicant_filters["program"] = filters.program
	for row in frappe.get_list(
		"Student Applicant",
		filters=applicant_filters,
		fields=["student_admission", "program", "application_status", "talisma_application_stage"],
	):
		stage = row.talisma_application_stage or {
			"Applied": "Submitted", "Approved": "Approved", "Rejected": "Rejected", "Admitted": "Admitted",
		}.get(row.application_status, "Draft")
		status = stage.lower().replace(" ", "_")
		if status in groups[(row.student_admission, row.program)]:
			groups[(row.student_admission, row.program)][status] += 1
	capacity = {
		(row.admission_intake, row.program): row
		for row in _program_rows(filters)
	}
	keys = sorted(set(groups) | set(capacity))
	data = []
	for key in keys:
		counts = groups[key]
		program = capacity.get(key, frappe._dict())
		data.append({
			"admission_intake": key[0],
			"program": key[1],
			"total_applications": sum(counts.values()),
			**counts,
			"intake_capacity": program.intake_capacity,
			"seats_available": program.seats_available,
		})
	return columns, data


def _intake_rows(filters):
	db_filters = {}
	if filters.get("academic_year"):
		db_filters["academic_year"] = filters.academic_year
	if filters.get("academic_term"):
		db_filters["talisma_academic_term"] = filters.academic_term
	if filters.get("status"):
		db_filters["talisma_status"] = filters.status
	intakes = frappe.get_list(
		"Student Admission",
		filters=db_filters,
		fields=[
			"name", "title", "academic_year", "talisma_academic_term", "talisma_campus",
			"talisma_status", "admission_start_date", "admission_end_date",
			"talisma_decision_release_date", "talisma_enrollment_confirmation_deadline",
		],
		order_by="admission_start_date desc",
	)
	program_rows = _program_rows(filters)
	by_intake = defaultdict(list)
	for row in program_rows:
		by_intake[row.admission_intake].append(row)
	data = []
	for row in intakes:
		programs = by_intake[row.name]
		data.append({
			"admission_intake": row.name,
			"admission_intake_name": row.title,
			"academic_year": row.academic_year,
			"academic_term": row.talisma_academic_term,
			"campus": row.talisma_campus,
			"status": row.talisma_status,
			"application_start_date": row.admission_start_date,
			"application_end_date": row.admission_end_date,
			"decision_release_date": row.talisma_decision_release_date,
			"confirmation_deadline": row.talisma_enrollment_confirmation_deadline,
			"program_count": len(programs),
			"intake_capacity": sum(cint(program.intake_capacity) for program in programs),
			"seats_filled": sum(cint(program.seats_filled) for program in programs),
			"seats_available": sum(cint(program.seats_available) for program in programs),
		})
	return data


def _program_rows(filters):
	parent_filters = {}
	if filters.get("admission_intake"):
		parent_filters["name"] = filters.admission_intake
	if filters.get("academic_year"):
		parent_filters["academic_year"] = filters.academic_year
	if filters.get("academic_term"):
		parent_filters["talisma_academic_term"] = filters.academic_term
	if filters.get("status") and not isinstance(filters.status, tuple):
		parent_filters["talisma_status"] = filters.status
	parents = frappe.get_list(
		"Student Admission",
		filters=parent_filters,
		fields=["name", "academic_year", "talisma_academic_term", "talisma_status"],
	)
	parent_map = {row.name: row for row in parents}
	if not parent_map:
		return []
	child_filters = {"parent": ("in", list(parent_map)), "parenttype": "Student Admission"}
	if filters.get("program"):
		child_filters["program"] = filters.program
	if filters.get("program_status"):
		child_filters["talisma_status"] = filters.program_status
	rows = frappe.get_all(
		"Student Admission Program",
		filters=child_filters,
		fields=[
			"parent", "program", "talisma_degree", "talisma_academic_unit", "application_fee",
			"talisma_intake_capacity", "talisma_seats_filled", "talisma_seats_available", "talisma_status",
		],
		order_by="parent, idx",
	)
	data = []
	for row in rows:
		if filters.get("only_available") and (row.talisma_status != "Open" or cint(row.talisma_seats_available) <= 0):
			continue
		parent = parent_map[row.parent]
		data.append(frappe._dict(
			admission_intake=row.parent,
			intake_status=parent.talisma_status,
			academic_year=parent.academic_year,
			academic_term=parent.talisma_academic_term,
			program=row.program,
			degree=row.talisma_degree,
			academic_unit=row.talisma_academic_unit,
			application_fee=flt(row.application_fee),
			intake_capacity=cint(row.talisma_intake_capacity),
			seats_filled=cint(row.talisma_seats_filled),
			seats_available=cint(row.talisma_seats_available),
			program_status=row.talisma_status,
		))
	return data


def _intake_columns():
	return [
		_col("Admission Intake", "admission_intake", "Link", "Student Admission", 180),
		_col("Admission Intake Name", "admission_intake_name", width=190),
		_col("Academic Year", "academic_year", "Link", "Academic Year", 130),
		_col("Academic Term", "academic_term", "Link", "Academic Term", 150),
		_col("Campus", "campus", "Link", "Talisma Campus", 150),
		_col("Status", "status", width=100),
		_col("Application Start", "application_start_date", "Date", width=110),
		_col("Application End", "application_end_date", "Date", width=110),
		_col("Decision Release", "decision_release_date", "Date", width=110),
		_col("Confirmation Deadline", "confirmation_deadline", "Date", width=130),
		_col("Programs", "program_count", "Int", width=80),
		_col("Capacity", "intake_capacity", "Int", width=85),
		_col("Seats Filled", "seats_filled", "Int", width=90),
		_col("Seats Available", "seats_available", "Int", width=105),
	]


def _col(label, fieldname, fieldtype="Data", options=None, width=120):
	return {
		"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype,
		"options": options, "width": width,
	}
