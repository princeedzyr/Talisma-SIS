from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from talisma_sis.admissions import (
	_sync_application_workflow,
	_validate_timeline,
	validate_admission_intake,
	validate_student_application_intake,
)


def intake_doc(**values):
	doc = frappe._dict(
		name="TEST-INTAKE",
		academic_year="2026-2027",
		talisma_academic_term="Fall 2026",
		talisma_status="Open",
		admission_start_date="2026-06-01",
		admission_end_date="2026-08-15",
		talisma_decision_release_date="2026-08-20",
		talisma_enrollment_confirmation_deadline="2026-08-31",
		program_details=[],
	)
	doc.update(values)
	return doc


def program_row(**values):
	row = frappe._dict(
		idx=1,
		program="TEST-PROGRAM",
		application_fee=50,
		talisma_intake_capacity=10,
		talisma_seats_filled=0,
		talisma_seats_available=10,
		talisma_status="Open",
		talisma_minimum_gpa=2.5,
		talisma_minimum_credits=0,
		min_age=0,
		max_age=0,
		talisma_entrance_exam_required=0,
		talisma_minimum_entrance_exam_score=0,
		talisma_work_experience_required=0,
		talisma_minimum_work_experience=0,
		talisma_degree="Bachelor of Science",
		talisma_academic_unit="Science",
	)
	row.update(values)
	return row


class TestAdmissionIntake(FrappeTestCase):
	def test_timeline_requires_decision_after_application_end(self):
		doc = intake_doc(talisma_decision_release_date="2026-08-15")
		with self.assertRaisesRegex(frappe.ValidationError, "Decision Release Date"):
			_validate_timeline(doc)

	def test_duplicate_program_is_rejected(self):
		doc = intake_doc(program_details=[program_row(), program_row(idx=2)])
		def get_value(doctype, *args, **kwargs):
			if doctype == "Academic Term":
				return "2026-2027"
			if doctype == "Program":
				return frappe._dict(talisma_degree="Bachelor of Science", talisma_academic_unit="Science")
			return None
		with (
			patch.object(frappe.db, "get_value", side_effect=get_value),
			patch("talisma_sis.admissions._application_count", return_value=0),
			self.assertRaisesRegex(frappe.ValidationError, "listed more than once"),
		):
			validate_admission_intake(doc)

	def test_capacity_marks_program_full(self):
		row = program_row(talisma_intake_capacity=5)
		doc = intake_doc(program_details=[row])
		def get_value(doctype, *args, **kwargs):
			if doctype == "Academic Term":
				return "2026-2027"
			if doctype == "Program":
				return frappe._dict(talisma_degree="Bachelor of Science", talisma_academic_unit="Science")
			return None
		with (
			patch.object(frappe.db, "get_value", side_effect=get_value),
			patch("talisma_sis.admissions._application_count", return_value=5),
		):
			validate_admission_intake(doc)

		self.assertEqual(row.talisma_status, "Full")
		self.assertEqual(row.talisma_seats_available, 0)

	def test_application_uses_authoritative_intake_defaults(self):
		row = program_row()
		intake = intake_doc(talisma_campus="Main Campus", program_details=[row])
		applicant = frappe._dict(
			name="NEW-APPLICATION",
			student_admission=intake.name,
			program=row.program,
			application_date="2026-07-15",
			talisma_capacity_override=0,
			talisma_application_stage="Draft",
			talisma_eligibility_status="Pending",
			talisma_application_fee_status="Pending",
			paid=0,
			is_new=lambda: True,
		)
		with (
			patch.object(frappe, "get_doc", return_value=intake),
			patch("talisma_sis.admissions._application_count", return_value=3),
		):
			validate_student_application_intake(applicant)

		self.assertEqual(applicant.academic_year, intake.academic_year)
		self.assertEqual(applicant.academic_term, intake.talisma_academic_term)
		self.assertEqual(applicant.talisma_degree, row.talisma_degree)
		self.assertEqual(applicant.talisma_application_fee, row.application_fee)
		self.assertEqual(applicant.application_status, "Applied")

	def test_decision_pending_requires_eligibility_review(self):
		applicant = frappe._dict(
			talisma_application_stage="Decision Pending",
			talisma_eligibility_status="Pending",
			talisma_application_fee_status="Pending",
			talisma_application_fee=50,
			paid=0,
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Eligibility Review"):
			_sync_application_workflow(applicant)

	def test_submitted_application_selection_is_locked(self):
		old = frappe._dict(
			student_admission="OLD-INTAKE", program="OLD-PROGRAM",
			talisma_application_stage="Submitted", application_status="Applied",
		)
		applicant = frappe._dict(
			name="TEST-APPLICATION", student_admission="NEW-INTAKE", program="NEW-PROGRAM",
			talisma_application_stage="Submitted", application_status="Applied",
			flags=frappe._dict(), is_new=lambda: False, get_doc_before_save=lambda: old,
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Transfer Application"):
			validate_student_application_intake(applicant)
