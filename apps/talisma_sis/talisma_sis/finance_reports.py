"""Script-report adapters for the university-facing Student Finance workspace."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from talisma_sis.finance import get_student_account


def billing_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Billing Statement", "name", "Link", "Sales Invoice", 180),
		_col("Student", "student", "Link", "Student", 160),
		_col("Student Name", "student_name", width=180),
		_col("Program", "program", "Link", "Program", 190),
		_col("Academic Year", "academic_year", "Link", "Academic Year", 130),
		_col("Academic Term", "academic_term", "Link", "Academic Term", 150),
		_col("Posting Date", "posting_date", "Date", width=110),
		_col("Due Date", "due_date", "Date", width=110),
		_col("Billing Status", "status", width=120),
		_col("Billed Amount", "grand_total", "Currency", "currency", 130),
		_col("Outstanding Balance", "outstanding_amount", "Currency", "currency", 150),
		_col("Currency", "currency", width=80),
	]
	return columns, _billing_rows(filters, outstanding_only=False)


def outstanding_report(filters=None):
	filters = frappe._dict(filters or {})
	columns, rows = billing_report(filters)
	return columns, [row for row in rows if flt(row.outstanding_amount) > 0]


def payment_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Payment Date", "payment_date", "Date", width=110),
		_col("Student", "student", "Link", "Student", 160),
		_col("Student Name", "student_name", width=180),
		_col("Payment Method", "payment_method", width=130),
		_col("Reference Number", "reference_number", width=150),
		_col("Amount Paid", "amount_paid", "Currency", "currency", 130),
		_col("Receipt Number", "receipt_number", "Link", "Payment Entry", 180),
		_col("Status", "status", width=100),
		_col("Currency", "currency", width=80),
	]
	rows = []
	for student in _students_with_billing(filters):
		account = get_student_account(student.name)
		for payment in account.get("student_payments", []):
			if payment.get("payment_type") == "Pay" or not _date_match(payment.get("payment_date"), filters):
				continue
			rows.append({**payment, "student": student.name, "student_name": student.student_name})
	rows.sort(key=lambda row: (row["payment_date"], row["receipt_number"]), reverse=True)
	return columns, rows


def account_statement(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Date", "date", "Date", width=110),
		_col("Description", "description", width=260),
		_col("Activity", "activity_type", width=140),
		_col("Charge", "charge", "Currency", "currency", 120),
		_col("Credit", "credit", "Currency", "currency", 120),
		_col("Balance", "balance", "Currency", "currency", 130),
		_col("Source", "source", width=180),
		_col("Currency", "currency", width=80),
	]
	if not filters.student:
		frappe.throw(_("Student is required for a Student Account Statement."))
	account = get_student_account(filters.student)
	rows = [row for row in account.get("account_activity", []) if _date_match(row.get("date"), filters)]
	return columns, rows


def scholarship_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Date", "posting_date", "Date", width=110),
		_col("Student", "student", "Link", "Student", 160),
		_col("Student Name", "student_name", width=180),
		_col("Billing Statement", "billing_statement", "Link", "Sales Invoice", 180),
		_col("Fee Category", "fee_category", width=160),
		_col("Description", "description", width=200),
		_col("Amount", "amount", "Currency", "currency", 120),
		_col("Source", "source", width=150),
		_col("Currency", "currency", width=80),
	]
	rows = []
	for student in _students_with_billing(filters):
		account = get_student_account(student.name)
		for scholarship in account.get("scholarships", []):
			if _date_match(scholarship.get("posting_date"), filters):
				rows.append({**scholarship, "student": student.name, "student_name": student.student_name})
	rows.sort(key=lambda row: (row["posting_date"], row["billing_statement"]), reverse=True)
	return columns, rows


def refund_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Date", "posting_date", "Date", width=110),
		_col("Student", "student", "Link", "Student", 160),
		_col("Student Name", "student_name", width=180),
		_col("Refund", "name", "Link", "Sales Invoice", 180),
		_col("Original Billing Statement", "return_against", "Link", "Sales Invoice", 190),
		_col("Amount", "amount", "Currency", "currency", 120),
		_col("Status", "status", width=110),
		_col("Currency", "currency", width=80),
	]
	rows = []
	for student in _students_with_billing(filters):
		account = get_student_account(student.name)
		for refund in account.get("refunds", []):
			if _date_match(refund.get("posting_date"), filters):
				rows.append({**refund, "student": student.name, "student_name": student.student_name})
	rows.sort(key=lambda row: (row["posting_date"], row["name"]), reverse=True)
	return columns, rows


def program_collection_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		_col("Program", "program", "Link", "Program", 220),
		_col("Billed Charges", "billed_charges", "Currency", "currency", 140),
		_col("Student Payments", "payments", "Currency", "currency", 140),
		_col("Refunds", "refunds", "Currency", "currency", 120),
		_col("Outstanding Balance", "outstanding_balance", "Currency", "currency", 150),
		_col("Currency", "currency", width=80),
	]
	groups = defaultdict(lambda: frappe._dict(
		billed_charges=0.0, payments=0.0, refunds=0.0, outstanding_balance=0.0, currency=None,
	))
	billing_rows = _billing_rows(filters, outstanding_only=False, include_returns=True)
	for row in billing_rows:
		program = row.program or _("Unassigned Program")
		group = groups[program]
		group.currency = group.currency or row.currency
		if row.is_return:
			group.refunds += abs(flt(row.grand_total))
		else:
			group.billed_charges += flt(row.grand_total)
		group.outstanding_balance += flt(row.outstanding_amount)
	for student in _students_with_billing(filters):
		account = get_student_account(student.name)
		statement_program = {
			row["name"]: row.get("program") or _("Unassigned Program")
			for row in account.get("billing_statements", [])
		}
		for payment in account.get("student_payments", []):
			if payment.get("payment_type") == "Pay" or not _date_match(payment.get("payment_date"), filters):
				continue
			programs = {statement_program.get(name) for name in payment.get("billing_statements", [])}
			programs.discard(None)
			if len(programs) == 1:
				groups[programs.pop()].payments += flt(payment.get("amount_paid"))
	rows = [{"program": program, **values} for program, values in groups.items()]
	rows.sort(key=lambda row: row["billed_charges"], reverse=True)
	return columns, rows


def waiver_report(filters=None):
	columns = [
		_col("Date", "posting_date", "Date", width=110),
		_col("Student", "student", "Link", "Student", 160),
		_col("Billing Statement", "billing_statement", "Link", "Sales Invoice", 180),
		_col("Description", "description", width=220),
		_col("Amount", "amount", "Currency", "currency", 120),
	]
	return columns, []


def _billing_rows(filters, outstanding_only=False, include_returns=False):
	db_filters = {"docstatus": 1}
	if filters.student:
		db_filters["student"] = filters.student
	if not include_returns:
		db_filters["is_return"] = 0
	if outstanding_only:
		db_filters["outstanding_amount"] = (">", 0)
	if filters.get("status"):
		db_filters["status"] = filters.status
	if filters.get("from_date") and filters.get("to_date"):
		db_filters["posting_date"] = ("between", [filters.from_date, filters.to_date])
	elif filters.get("from_date"):
		db_filters["posting_date"] = (">=", filters.from_date)
	elif filters.get("to_date"):
		db_filters["posting_date"] = ("<=", filters.to_date)
	rows = frappe.get_list(
		"Sales Invoice",
		filters=db_filters,
		fields=[
			"name", "student", "student_name", "posting_date", "due_date", "status", "currency",
			"grand_total", "outstanding_amount", "fee_schedule", "is_return", "return_against",
		],
		order_by="posting_date desc, creation desc",
	)
	schedule_names = sorted({row.fee_schedule for row in rows if row.fee_schedule})
	schedules = {
		row.name: row
		for row in frappe.get_all(
			"Fee Schedule",
			filters={"name": ("in", schedule_names)},
			fields=["name", "program", "academic_year", "academic_term"],
		)
	} if schedule_names else {}
	result = []
	for row in rows:
		schedule = schedules.get(row.fee_schedule, frappe._dict())
		row.update({
			"program": schedule.program,
			"academic_year": schedule.academic_year,
			"academic_term": schedule.academic_term,
		})
		if filters.get("program") and row.program != filters.program:
			continue
		if filters.get("academic_year") and row.academic_year != filters.academic_year:
			continue
		result.append(row)
	return result


def _students_with_billing(filters):
	invoice_filters = {"docstatus": 1, "student": ("is", "set")}
	if filters.get("student"):
		invoice_filters["student"] = filters.student
	names = frappe.get_list("Sales Invoice", filters=invoice_filters, pluck="student", distinct=True)
	if not names:
		return []
	return frappe.get_list(
		"Student",
		filters={"name": ("in", names)},
		fields=["name", "student_name"],
		order_by="student_name",
	)


def _date_match(value, filters) -> bool:
	if not value:
		return True
	value = getdate(value)
	return not (
		(filters.get("from_date") and value < getdate(filters.from_date))
		or (filters.get("to_date") and value > getdate(filters.to_date))
	)


def _col(label, fieldname, fieldtype="Data", options=None, width=120):
	return {
		"label": _(label),
		"fieldname": fieldname,
		"fieldtype": fieldtype,
		"options": options,
		"width": width,
	}
