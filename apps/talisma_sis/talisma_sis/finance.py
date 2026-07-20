"""Higher-education views over ERPNext's authoritative accounting records."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


def get_student_account(student: str) -> dict:
	"""Build a student account without persisting a parallel balance."""
	student_doc = frappe.get_doc("Student", student)
	if not frappe.has_permission("Student", "read", doc=student_doc):
		frappe.throw(_("You do not have permission to view this student."), frappe.PermissionError)
	if not frappe.has_permission("Sales Invoice", "read"):
		return _restricted_account()

	invoices = frappe.get_list(
		"Sales Invoice",
		filters={"student": student_doc.name, "docstatus": 1},
		fields=[
			"name",
			"posting_date",
			"due_date",
			"status",
			"currency",
			"grand_total",
			"outstanding_amount",
			"fee_schedule",
			"is_return",
			"return_against",
		],
		order_by="posting_date desc, creation desc",
	)
	invoice_names = [row.name for row in invoices]
	items = _invoice_items(invoice_names)
	items_by_invoice = defaultdict(list)
	for item in items:
		items_by_invoice[item.parent].append(item)

	fee_categories = _fee_categories(items)
	schedules = _fee_schedules(invoices)
	billing_statements = []
	components = []
	scholarships = []
	refunds = []
	activity = []
	sequence = 0

	for invoice in invoices:
		schedule = schedules.get(invoice.fee_schedule, frappe._dict())
		invoice_items = items_by_invoice[invoice.name]
		is_refund = bool(invoice.is_return)
		statement_adjustments = 0.0
		statement_net = 0.0
		for item in invoice_items:
			gross = _gross_amount(item)
			net = abs(flt(item.net_amount if item.net_amount is not None else item.amount))
			adjustment = max(gross - net, 0)
			statement_adjustments += adjustment
			statement_net += net
			category = fee_categories.get(item.item_code) or item.item_name or item.item_code
			component = {
				"billing_statement": invoice.name,
				"fee_category": category,
				"description": item.description or item.item_name or category,
				"amount": gross,
				"scholarship_adjustment": adjustment,
				"waiver_adjustment": 0.0,
				"net_charge": net,
				"currency": invoice.currency,
				"is_refund": is_refund,
			}
			components.append(component)
			sequence += 1
			activity.append(_activity_row(
				invoice.posting_date,
				component["description"],
				0 if is_refund else gross,
				net if is_refund else 0,
				"Refund" if is_refund else "Student Charge",
				invoice.name,
				invoice.currency,
				sequence,
			))
			if adjustment and not is_refund:
				scholarship = {
					"billing_statement": invoice.name,
					"posting_date": invoice.posting_date,
					"fee_category": category,
					"description": _("Fee component discount"),
					"amount": adjustment,
					"currency": invoice.currency,
					"source": "Fee Component Discount",
				}
				scholarships.append(scholarship)
				sequence += 1
				activity.append(_activity_row(
					invoice.posting_date,
					_("Scholarship – {0}").format(category),
					0,
					adjustment,
					"Scholarship",
					invoice.name,
					invoice.currency,
					sequence,
				))

		invoice_total = abs(flt(invoice.grand_total))
		residual = invoice_total - statement_net
		if abs(residual) > 0.005:
			sequence += 1
			activity.append(_activity_row(
				invoice.posting_date,
				_("Billing adjustment – {0}").format(invoice.name),
				max(residual, 0) if not is_refund else 0,
				max(residual, 0) if is_refund else max(-residual, 0),
				"Billing Adjustment",
				invoice.name,
				invoice.currency,
				sequence,
			))

		statement = {
			"name": invoice.name,
			"program": schedule.program,
			"academic_year": schedule.academic_year,
			"academic_term": schedule.academic_term,
			"posting_date": invoice.posting_date,
			"due_date": invoice.due_date,
			"billing_status": "Refund" if is_refund else invoice.status,
			"total_charges": 0 if is_refund else sum(
				_gross_amount(item) for item in invoice_items
			) + max(residual, 0),
			"scholarship_adjustment": 0 if is_refund else statement_adjustments,
			"waiver_adjustment": 0.0,
			"net_charge": 0 if is_refund else invoice_total,
			"outstanding_balance": flt(invoice.outstanding_amount),
			"currency": invoice.currency,
			"is_refund": is_refund,
			"return_against": invoice.return_against,
		}
		billing_statements.append(statement)
		if is_refund:
			refunds.append({
				"name": invoice.name,
				"posting_date": invoice.posting_date,
				"return_against": invoice.return_against,
				"amount": invoice_total,
				"outstanding_amount": abs(flt(invoice.outstanding_amount)),
				"status": invoice.status,
				"currency": invoice.currency,
			})

	payments, payment_activity = _student_payments(invoice_names)
	for row in payment_activity:
		sequence += 1
		row["sequence"] = sequence
		activity.append(row)

	journal_activity = _standalone_journal_activity(student_doc)
	for row in journal_activity:
		sequence += 1
		row["sequence"] = sequence
		activity.append(row)

	activity = _running_balance(activity)
	regular_invoices = [row for row in invoices if not row.is_return]
	return_invoices = [row for row in invoices if row.is_return]
	regular_payments = [row for row in payments if row["payment_type"] != "Pay"]
	currency = next((row.currency for row in invoices if row.currency), None)
	legacy_fees = (
		frappe.db.count("Fees", {"student": student_doc.name, "docstatus": ("!=", 2)})
		if frappe.has_permission("Fees", "read")
		else 0
	)
	return {
		"restricted": False,
		"summary": {
			"total_charges": sum(
				flt(row["total_charges"])
				for row in billing_statements
				if not row["is_refund"]
			),
			"total_payments": sum(flt(row["amount_paid"]) for row in regular_payments),
			"total_scholarships": sum(flt(row["amount"]) for row in scholarships),
			"total_waivers": 0.0,
			"total_refunds": sum(abs(flt(row.grand_total)) for row in return_invoices),
			"outstanding_balance": sum(flt(row.outstanding_amount) for row in invoices),
			"last_payment_date": max((row["payment_date"] for row in regular_payments), default=None),
			"next_due_date": min(
				(row.due_date for row in regular_invoices if flt(row.outstanding_amount) > 0 and row.due_date),
				default=None,
			),
			"currency": currency,
		},
		"billing_statements": billing_statements,
		"billing_components": components,
		"student_payments": payments,
		"account_activity": activity,
		"scholarships": scholarships,
		"waivers": [],
		"refunds": refunds,
		"legacy_fees_count": legacy_fees,
	}


def _invoice_items(invoice_names: list[str]) -> list:
	if not invoice_names:
		return []
	return frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ("in", invoice_names), "parenttype": "Sales Invoice"},
		fields=[
			"parent", "item_code", "item_name", "description", "qty", "price_list_rate",
			"rate", "amount", "net_amount", "discount_percentage", "idx",
		],
		order_by="parent, idx",
	)


def _fee_categories(items: list) -> dict[str, str]:
	item_codes = sorted({row.item_code for row in items if row.item_code})
	if not item_codes:
		return {}
	return {
		row.item: row.name
		for row in frappe.get_all(
			"Fee Category",
			filters={"item": ("in", item_codes)},
			fields=["name", "item"],
		)
	}


def _fee_schedules(invoices: list) -> dict:
	names = sorted({row.fee_schedule for row in invoices if row.fee_schedule})
	if not names:
		return {}
	return {
		row.name: row
		for row in frappe.get_all(
			"Fee Schedule",
			filters={"name": ("in", names)},
			fields=["name", "program", "academic_year", "academic_term"],
		)
	}


def _gross_amount(item) -> float:
	listed = abs(flt(item.price_list_rate) * flt(item.qty))
	return listed or abs(flt(item.rate) * flt(item.qty)) or abs(flt(item.amount))


def _student_payments(invoice_names: list[str]) -> tuple[list[dict], list[dict]]:
	if not invoice_names or not frappe.has_permission("Payment Entry", "read"):
		return [], []
	references = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": ("in", invoice_names),
			"docstatus": 1,
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	entry_names = sorted({row.parent for row in references})
	if not entry_names:
		return [], []
	entries = {
		row.name: row
		for row in frappe.get_list(
			"Payment Entry",
			filters={"name": ("in", entry_names), "docstatus": 1},
			fields=[
				"name", "posting_date", "payment_type", "mode_of_payment", "reference_no",
				"paid_amount", "received_amount", "paid_from_account_currency",
				"paid_to_account_currency",
			],
		)
	}
	allocated = defaultdict(float)
	reference_names = defaultdict(list)
	for reference in references:
		if reference.parent in entries:
			allocated[reference.parent] += abs(flt(reference.allocated_amount))
			reference_names[reference.parent].append(reference.reference_name)

	payments = []
	activity = []
	for name, entry in entries.items():
		amount = allocated[name]
		currency = (
			entry.paid_to_account_currency
			if entry.payment_type == "Receive"
			else entry.paid_from_account_currency
		)
		row = {
			"name": entry.name,
			"payment_date": entry.posting_date,
			"payment_method": entry.mode_of_payment,
			"reference_number": entry.reference_no,
			"amount_paid": amount,
			"receipt_number": entry.name,
			"status": "Submitted",
			"payment_type": entry.payment_type,
			"billing_statements": reference_names[name],
			"currency": currency,
		}
		payments.append(row)
		activity.append(_activity_row(
			entry.posting_date,
			_("Refund payment") if entry.payment_type == "Pay" else _("Student Payment"),
			amount if entry.payment_type == "Pay" else 0,
			0 if entry.payment_type == "Pay" else amount,
			"Refund" if entry.payment_type == "Pay" else "Student Payment",
			entry.name,
			currency,
			0,
		))
	payments.sort(key=lambda row: (row["payment_date"], row["name"]), reverse=True)
	return payments, activity


def _standalone_journal_activity(student_doc) -> list[dict]:
	if not frappe.has_permission("Journal Entry", "read"):
		return []
	parties = [("Student", student_doc.name)]
	if student_doc.get("customer"):
		parties.append(("Customer", student_doc.customer))
	accounts = []
	for party_type, party in parties:
		accounts.extend(frappe.get_all(
			"Journal Entry Account",
			filters={"party_type": party_type, "party": party, "docstatus": 1},
			fields=[
				"parent", "debit_in_account_currency", "credit_in_account_currency",
				"account_currency", "reference_type", "reference_name",
			],
		))
	accounts = [row for row in accounts if not row.reference_type]
	parents = sorted({row.parent for row in accounts})
	if not parents:
		return []
	entries = {
		row.name: row
		for row in frappe.get_list(
			"Journal Entry",
			filters={"name": ("in", parents), "docstatus": 1},
			fields=["name", "posting_date", "voucher_type", "user_remark"],
		)
	}
	rows = []
	for account in accounts:
		entry = entries.get(account.parent)
		if not entry:
			continue
		rows.append(_activity_row(
			entry.posting_date,
			entry.user_remark or entry.voucher_type or _("Account Adjustment"),
			flt(account.debit_in_account_currency),
			flt(account.credit_in_account_currency),
			"Account Adjustment",
			entry.name,
			account.account_currency,
			0,
		))
	return rows


def _activity_row(date, description, charge, credit, activity_type, source, currency, sequence):
	return {
		"date": date,
		"description": description,
		"charge": flt(charge),
		"credit": flt(credit),
		"balance": 0.0,
		"activity_type": activity_type,
		"source": source,
		"currency": currency,
		"sequence": sequence,
	}


def _running_balance(rows: list[dict]) -> list[dict]:
	rows.sort(key=lambda row: (row["date"], row["sequence"], row["source"] or ""))
	balance = 0.0
	for row in rows:
		balance += flt(row["charge"]) - flt(row["credit"])
		row["balance"] = balance
	return rows


def _restricted_account() -> dict:
	return {
		"restricted": True,
		"summary": {},
		"billing_statements": [],
		"billing_components": [],
		"student_payments": [],
		"account_activity": [],
		"scholarships": [],
		"waivers": [],
		"refunds": [],
		"legacy_fees_count": 0,
	}
