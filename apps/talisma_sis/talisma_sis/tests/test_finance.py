from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from talisma_sis.finance import _gross_amount, _running_balance
from talisma_sis.finance_reports import account_statement


class TestStudentFinance(FrappeTestCase):
	def test_running_balance_uses_charges_and_credits_in_date_order(self):
		rows = [
			{"date": "2026-08-15", "description": "Payment", "charge": 0, "credit": 2000, "source": "PAY-1", "sequence": 3},
			{"date": "2026-08-01", "description": "Tuition", "charge": 6000, "credit": 0, "source": "INV-1", "sequence": 1},
			{"date": "2026-08-10", "description": "Scholarship", "charge": 0, "credit": 1000, "source": "INV-1", "sequence": 2},
		]

		result = _running_balance(rows)

		self.assertEqual([row["balance"] for row in result], [6000, 5000, 3000])

	def test_gross_amount_prefers_listed_rate_before_discount(self):
		item = frappe._dict(price_list_rate=1000, rate=900, qty=2, amount=1800)

		self.assertEqual(_gross_amount(item), 2000)

	def test_account_statement_requires_a_student(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Student is required"):
			account_statement({})

	def test_account_statement_filters_authoritative_activity_by_date(self):
		account = {
			"account_activity": [
				{"date": "2026-08-01", "description": "Before"},
				{"date": "2026-08-15", "description": "Included"},
				{"date": "2026-09-01", "description": "After"},
			]
		}
		with patch("talisma_sis.finance_reports.get_student_account", return_value=account):
			_columns, rows = account_statement({
				"student": "TEST-STUDENT",
				"from_date": "2026-08-10",
				"to_date": "2026-08-20",
			})

		self.assertEqual([row["description"] for row in rows], ["Included"])
