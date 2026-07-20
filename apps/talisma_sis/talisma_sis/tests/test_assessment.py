from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from talisma_sis.assessment import populate_gradebook


class TestAssessmentGradebook(FrappeTestCase):
	def make_gradebook(self):
		doc = frappe.new_doc("Assessment Gradebook")
		doc.update(
			{
				"student": "TEST-STUDENT",
				"course": "TEST-COURSE",
				"academic_term": "TEST-TERM",
				"student_group": "TEST-SECTION",
				"grading_scale": "TEST-SCALE",
			}
		)
		return doc

	def test_locked_results_are_weighted_into_final_grade(self):
		plans = [
			frappe._dict(name="PLAN-1", assessment_name="Assignment", assessment_group="Assignment", talisma_course_grade_weightage=20),
			frappe._dict(name="PLAN-2", assessment_name="Final", assessment_group="Final", talisma_course_grade_weightage=80),
		]
		results = {
			"PLAN-1": frappe._dict(name="RESULT-1", total_score=82, maximum_score=100, talisma_percentage=82, grade="B+", talisma_result_status="Locked"),
			"PLAN-2": frappe._dict(name="RESULT-2", total_score=90, maximum_score=100, talisma_percentage=90, grade="A", talisma_result_status="Locked"),
		}
		doc = self.make_gradebook()
		original_get_value = frappe.db.get_value
		def get_result(doctype, filters, *args, **kwargs):
			if doctype == "Assessment Result":
				return results[filters["assessment_plan"]]
			return original_get_value(doctype, filters, *args, **kwargs)
		with (
			patch("education.education.validate_student_belongs_to_group"),
			patch.object(frappe.db, "exists", return_value=None),
			patch.object(frappe, "get_all", return_value=plans),
			patch.object(frappe.db, "get_value", side_effect=get_result),
			patch("education.education.api.get_grade", return_value="B+"),
			patch("talisma_sis.academics._grade_points", return_value=3.3),
		):
			populate_gradebook(doc)

		self.assertAlmostEqual(doc.final_percentage, 88.4)
		self.assertEqual(doc.letter_grade, "B+")
		self.assertEqual(doc.grade_points, 3.3)
		self.assertEqual(len(doc.assessment_summary), 2)

	def test_publish_rejects_missing_locked_results(self):
		plans = [frappe._dict(name="PLAN-1", assessment_name="Final", assessment_group="Final", talisma_course_grade_weightage=100)]
		doc = self.make_gradebook()
		doc.flags.publishing = True
		with (
			patch("education.education.validate_student_belongs_to_group"),
			patch.object(frappe.db, "exists", return_value=None),
			patch.object(frappe, "get_all", return_value=plans),
			patch.object(frappe.db, "get_value", return_value=None),
			self.assertRaisesRegex(frappe.ValidationError, "do not yet have Locked results"),
		):
			populate_gradebook(doc)

	def test_publish_requires_one_hundred_percent_weightage(self):
		plans = [frappe._dict(name="PLAN-1", assessment_name="Final", assessment_group="Final", talisma_course_grade_weightage=90)]
		result = frappe._dict(name="RESULT-1", total_score=90, maximum_score=100, talisma_percentage=90, grade="A", talisma_result_status="Locked")
		doc = self.make_gradebook()
		doc.flags.publishing = True
		original_get_value = frappe.db.get_value
		def get_result(doctype, filters, *args, **kwargs):
			if doctype == "Assessment Result":
				return result
			return original_get_value(doctype, filters, *args, **kwargs)
		with (
			patch("education.education.validate_student_belongs_to_group"),
			patch.object(frappe.db, "exists", return_value=None),
			patch.object(frappe, "get_all", return_value=plans),
			patch.object(frappe.db, "get_value", side_effect=get_result),
			self.assertRaisesRegex(frappe.ValidationError, "weightage must total 100%"),
		):
			populate_gradebook(doc)
