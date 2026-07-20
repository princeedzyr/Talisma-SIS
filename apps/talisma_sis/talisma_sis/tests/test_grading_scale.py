from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from talisma_sis.academics import validate_grading_scale


class TestGradingScalePolicy(FrappeTestCase):
	def make_scale(self, rows):
		doc = frappe.new_doc("Grading Scale")
		doc.grading_scale_name = "Test US Grade Scale"
		for row in rows:
			doc.append("intervals", row)
		return doc

	def test_valid_definitions_are_sorted_descending(self):
		doc = self.make_scale([
			{"grade_code": "F", "grade_description": "Fail", "threshold": 0, "talisma_maximum_score": 59.99, "talisma_grade_points": 0},
			{"grade_code": "A", "grade_description": "Excellent", "threshold": 90, "talisma_maximum_score": 100, "talisma_grade_points": 4},
			{"grade_code": "B", "grade_description": "Good", "threshold": 80, "talisma_maximum_score": 89.99, "talisma_grade_points": 3},
		])

		validate_grading_scale(doc)

		self.assertEqual([row.grade_code for row in doc.intervals], ["A", "B", "F"])

	def test_duplicate_letter_grades_are_rejected(self):
		doc = self.make_scale([
			{"grade_code": "A", "grade_description": "Excellent", "threshold": 90, "talisma_maximum_score": 100, "talisma_grade_points": 4},
			{"grade_code": "a", "grade_description": "Excellent", "threshold": 80, "talisma_maximum_score": 89.99, "talisma_grade_points": 4},
		])

		with self.assertRaisesRegex(frappe.ValidationError, "appears more than once"):
			validate_grading_scale(doc)

	def test_overlapping_ranges_are_rejected(self):
		doc = self.make_scale([
			{"grade_code": "A", "grade_description": "Excellent", "threshold": 90, "talisma_maximum_score": 100, "talisma_grade_points": 4},
			{"grade_code": "B", "grade_description": "Good", "threshold": 85, "talisma_maximum_score": 95, "talisma_grade_points": 3},
		])

		with self.assertRaisesRegex(frappe.ValidationError, "Score ranges overlap"):
			validate_grading_scale(doc)

	def test_invalid_values_are_rejected(self):
		invalid_rows = (
			({"grade_code": "A", "grade_description": "Excellent", "threshold": 95, "talisma_maximum_score": 90, "talisma_grade_points": 4}, "Minimum Score"),
			({"grade_code": "A", "grade_description": "Excellent", "threshold": -1, "talisma_maximum_score": 90, "talisma_grade_points": 4}, "between 0 and 100"),
			({"grade_code": "A", "grade_description": "Excellent", "threshold": 90, "talisma_maximum_score": 101, "talisma_grade_points": 4}, "between 0 and 100"),
			({"grade_code": "A", "grade_description": "Excellent", "threshold": 90, "talisma_maximum_score": 100, "talisma_grade_points": -1}, "cannot be negative"),
		)
		for row, message in invalid_rows:
			with self.subTest(message=message):
				with self.assertRaisesRegex(frappe.ValidationError, message):
					validate_grading_scale(self.make_scale([row]))
