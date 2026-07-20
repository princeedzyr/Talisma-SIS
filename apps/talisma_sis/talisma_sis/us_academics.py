"""US higher-education validation extensions for the isolated demo."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from talisma_sis.demo import DEMO_SITE


def validate_course(doc, method=None) -> None:
	if not _is_demo() or not doc.meta.has_field("talisma_credit_hours"):
		return
	if flt(doc.talisma_credit_hours) <= 0:
		frappe.throw(_("Credit Hours must be greater than zero."))
	if not doc.talisma_subject_code or not doc.talisma_catalog_number:
		frappe.throw(_("Subject Code and Catalog Number are required for the US course catalog."))


def validate_academic_term(doc, method=None) -> None:
	if not _is_demo() or not doc.meta.has_field("talisma_registration_opens"):
		return
	dates = [
		doc.talisma_registration_opens,
		doc.term_start_date,
		doc.talisma_add_drop_deadline,
		doc.talisma_census_date,
		doc.talisma_withdrawal_deadline,
		doc.term_end_date,
		doc.talisma_grades_due,
	]
	if any(not value for value in dates):
		frappe.throw(_("US academic-term milestone dates are required."))
	parsed = [getdate(value) for value in dates]
	if parsed != sorted(parsed):
		frappe.throw(_("Academic-term milestone dates must follow their lifecycle order."))


def validate_course_section(doc, method=None) -> None:
	if not _is_demo() or doc.group_based_on != "Course" or not doc.meta.has_field("talisma_crn"):
		return
	for fieldname in ("talisma_crn", "talisma_section_number", "talisma_campus", "talisma_delivery_method"):
		if not doc.get(fieldname):
			frappe.throw(_("{0} is required for a US course section.").format(doc.meta.get_label(fieldname)))
	if doc.max_strength < 0 or doc.talisma_waitlist_capacity < 0:
		frappe.throw(_("Section and waitlist capacities cannot be negative."))
	if doc.talisma_start_time and doc.talisma_end_time and doc.talisma_start_time >= doc.talisma_end_time:
		frappe.throw(_("Section Start Time must be before End Time."))


def healthcheck() -> dict:
	"""Verify the prepared US catalog, term, section, and registration records."""
	if not _is_demo():
		frappe.throw(_("US academic health checks are restricted to the demo site."))
	catalog_courses = frappe.db.count(
		"Course",
		{
			"talisma_subject_code": ("is", "set"),
			"talisma_catalog_number": ("is", "set"),
			"talisma_credit_hours": (">", 0),
		},
	)
	sections = frappe.db.count(
		"Student Group",
		{"group_based_on": "Course", "talisma_crn": ("is", "set")},
	)
	schedules = frappe.db.count("Course Schedule", {"student_group": ("is", "set")})
	section_registrations = frappe.db.count(
		"Course Enrollment", {"talisma_course_section": ("is", "set")}
	)
	term = frappe.db.get_value(
		"Academic Term",
		"2026-2027 (Fall 2026)",
		[
			"talisma_registration_opens",
			"talisma_add_drop_deadline",
			"talisma_census_date",
			"talisma_withdrawal_deadline",
			"talisma_grades_due",
		],
		as_dict=True,
	)
	checks = {
		"six_catalog_courses": catalog_courses == 6,
		"four_bscs_sections": sections == 4,
		"four_course_schedules": schedules >= 4,
		"term_milestones_complete": bool(term and all(term.values())),
		"section_registration_exists": section_registrations >= 1,
	}
	return {
		"ok": all(checks.values()),
		"checks": checks,
		"catalog_courses": catalog_courses,
		"sections": sections,
		"course_schedules": schedules,
		"section_registrations": section_registrations,
		"term": term,
	}


def _is_demo() -> bool:
	return frappe.local.site == DEMO_SITE
