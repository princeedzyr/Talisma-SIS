"""Idempotent setup for the isolated Talisma SIS client demonstration site."""

from __future__ import annotations

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.translate import get_all_translations
from frappe.utils import getdate

from talisma_sis.academics import configure_academics, seed_demo_course_categories
from talisma_sis.curriculum import configure_curriculum, seed_demo_curricula
from talisma_sis.student_360 import configure_student_360
from talisma_sis.student_records import configure_student_records, seed_demo_student_records
from talisma_sis.student_documents import configure_student_documents
from talisma_sis.class_scheduling import configure_class_scheduling
from talisma_sis.assessment import configure_assessment
from talisma_sis.admissions import configure_admission_intake, seed_demo_admission_intake


DEMO_SITE = "demo.talisma.local"
DEMO_MODULES = (
	("Admissions", "Admissions", "graduation-cap"),
	("Student Records", "Student Records", "users-round"),
	("Registrar", "Registrar", "list"),
	("Academics", "Academics", "book-open-text"),
	("Faculty & Sections", "Faculty & Sections", "presentation"),
	("Assessment & Grades", "Assessment & Grades", "book-open-check"),
	("Attendance", "Attendance", "calendar-days"),
	("Finance", "Finance", "landmark"),
	("Reports", "Reports", "sheet"),
)
LEGACY_MODULE_WORKSPACES = {
	"Talisma Admissions": "Admissions",
	"Talisma Student Records": "Student Records",
	"Talisma Registrar": "Registrar",
	"Talisma Academics": "Academics",
	"Talisma Faculty & Sections": "Faculty & Sections",
	"Talisma Assessment & Grades": "Assessment & Grades",
	"Talisma Attendance": "Attendance",
	"Talisma Finance": "Finance",
	"Talisma Reports": "Reports",
}
DEMO_MODULE_ART = {
	label: f"/assets/talisma_sis/icons/{label.lower().replace(' & ', '-').replace(' ', '-')}.svg"
	for label, _, _ in DEMO_MODULES
}
DEMO_WORKSPACE_NAME = "Bryan University"
LEGACY_DEMO_WORKSPACE_NAME = "Talisma University"
MISSPELLED_DEMO_WORKSPACE_NAME = "Bryne University"
DEMO_WORKSPACE_ROUTE = "/desk/bryan-university"
GENDER_OPTIONS = ("Male", "Female", "Others", "Prefer not to say")
DEMO_GRADING_SCALE_NAME = "Talisma US Letter Grades"
DEMO_GRADING_INTERVALS = (
	("A", "Excellent", 90, 100, 4.0),
	("A-", "Excellent", 85, 89.99, 3.7),
	("B+", "Very Good", 80, 84.99, 3.3),
	("B", "Good", 75, 79.99, 3.0),
	("C", "Satisfactory", 70, 74.99, 2.0),
	("D", "Pass", 60, 69.99, 1.0),
	("F", "Fail", 0, 59.99, 0.0),
)


def redirect_demo_desk(response, request) -> None:
	"""Send authenticated demo users from the Desk root to the university workspace."""
	if (
		frappe.local.site != DEMO_SITE
		or frappe.session.user == "Guest"
		or request.path.rstrip("/") != "/desk"
	):
		return

	response.status_code = 302
	response.headers["Location"] = DEMO_WORKSPACE_ROUTE
	response.set_data(b"")


@frappe.whitelist()
def dashboard_summary() -> dict:
	"""Return non-sensitive live counts for the authenticated demo dashboard."""
	if frappe.local.site != DEMO_SITE:
		frappe.throw(f"Demo dashboard is restricted to {DEMO_SITE}.")

	return {
		"students": frappe.db.count("Student", {"enabled": 1}),
		"applicants": frappe.db.count("Student Applicant"),
		"courses": frappe.db.count("Course"),
		"faculty": frappe.db.count("Instructor", {"status": "Active"}),
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def gender_options_query(doctype, txt, searchfield, start, page_len, filters):
	"""Return the demo's intentionally small Gender list in its display order."""
	search_text = (txt or "").lower()
	matches = [
		value for value in GENDER_OPTIONS if not search_text or search_text in value.lower()
	]
	start = int(start or 0)
	page_len = int(page_len or 20)
	return [[value] for value in matches[start : start + page_len]]


def healthcheck() -> dict:
	"""Return the demo launcher's routing and isolation state without changing data."""
	if frappe.local.site != DEMO_SITE:
		frappe.throw(f"Demo health check is restricted to {DEMO_SITE}.")

	icon = frappe.db.get_value(
		"Desktop Icon",
		{"hidden": 0},
		["name", "label", "link_type", "link_to", "sidebar"],
		as_dict=True,
	)
	default_workspaces = sorted(
		set(
			frappe.get_all(
				"User",
				filters={"enabled": 1, "user_type": "System User"},
				pluck="default_workspace",
			)
		)
	)
	visible_icons = frappe.get_all(
		"Desktop Icon", filters={"hidden": 0}, pluck="label", order_by="idx"
	)
	admissions_sidebar_links = []
	student_management_links = []
	academics_sidebar_links = []
	finance_sidebar_links = []
	if frappe.db.exists("Workspace Sidebar", DEMO_WORKSPACE_NAME):
		university_sidebar = frappe.get_doc("Workspace Sidebar", DEMO_WORKSPACE_NAME)
		admissions_sidebar_links = _sidebar_section_links(university_sidebar, "Admissions")
		student_management_links = _sidebar_section_links(university_sidebar, "Student Management")
		academics_sidebar_links = _sidebar_section_links(university_sidebar, "Academics")
		finance_sidebar_links = _sidebar_section_links(university_sidebar, "Finance")
	student_meta = frappe.get_meta("Student")
	student_field_order = [field.fieldname for field in student_meta.fields]
	applicant_meta = frappe.get_meta("Student Applicant")
	admission_meta = frappe.get_meta("Student Admission")
	family_member_meta = frappe.get_meta("Talisma Family Member")
	grading_interval_meta = frappe.get_meta("Grading Scale Interval")
	admission_program_meta = frappe.get_meta("Student Admission Program")
	gender_values = frappe.get_all("Gender", pluck="name")
	grading_scale = frappe.db.get_value(
		"Grading Scale", {"grading_scale_name": DEMO_GRADING_SCALE_NAME}, "name"
	)
	grading_ranges = {}
	if grading_scale:
		grading_ranges = {
			row.grade_code: (
				row.grade_description,
				float(row.threshold),
				float(row.talisma_maximum_score),
				float(row.talisma_grade_points),
			)
			for row in frappe.get_all(
				"Grading Scale Interval",
				filters={"parent": grading_scale, "parenttype": "Grading Scale"},
				fields=["grade_code", "grade_description", "threshold", "talisma_maximum_score", "talisma_grade_points"],
			)
		}
	checks = {
		"workspace_exists": bool(frappe.db.exists("Workspace", DEMO_WORKSPACE_NAME)),
		"sidebar_exists": bool(frappe.db.exists("Workspace Sidebar", DEMO_WORKSPACE_NAME)),
		"module_desktop_icons": visible_icons == [item[0] for item in DEMO_MODULES],
		"no_redundant_university_icon": DEMO_WORKSPACE_NAME not in visible_icons,
		"module_sidebars": all(
			frappe.db.exists("Workspace Sidebar", label) for label, _, _ in DEMO_MODULES
		),
		"module_artwork": all(
			frappe.db.get_value("Desktop Icon", label, "logo_url") == DEMO_MODULE_ART[label]
			for label, _, _ in DEMO_MODULES
		),
		"admissions_sidebar_order": admissions_sidebar_links[:2]
		== [
			("Admission Intake", "Student Admission"),
			("Student Application", "Student Applicant"),
		],
		"student_admission_ui_label": get_all_translations("en").get("Student Admission")
		== "Admission Intake",
		"application_type_removed": not applicant_meta.get_field("talisma_application_type"),
		"admission_introduction_hidden": bool(
			admission_meta.get_field("introduction").hidden
		),
		"admission_intake_configuration": (
			admission_meta.get_field("title").label == "Admission Intake Name"
			and admission_meta.get_field("title").reqd
			and admission_meta.get_field("talisma_academic_term").reqd
			and admission_meta.get_field("talisma_status").reqd
			and admission_meta.get_field("route").hidden
			and admission_meta.get_field("published").hidden
			and admission_meta.get_field("program_details").label == "Programs"
		),
		"admission_program_capacity": all(
			admission_program_meta.get_field(fieldname)
			for fieldname in (
				"talisma_degree", "talisma_academic_unit", "talisma_intake_capacity",
				"talisma_seats_filled", "talisma_seats_available", "talisma_status",
				"talisma_minimum_gpa", "talisma_previous_qualification",
			)
		),
		"student_application_workflow": (
			applicant_meta.get_field("application_status").hidden
			and applicant_meta.get_field("talisma_application_stage").read_only
			and applicant_meta.get_field("talisma_eligibility_status").read_only
			and applicant_meta.get_field("talisma_application_fee_status").read_only
			and all(
				applicant_meta.get_field(fieldname)
				for fieldname in (
					"talisma_decision_by", "talisma_decision_reason", "talisma_admission_conditions",
					"talisma_transfer_reason", "talisma_transferred_by",
				)
			)
		),
		"student_identity_and_additional_layout": (
			student_meta.get_field("section_break_3").label == "Student Information"
			and student_meta.get_field("section_break_7").label == "Additional Information"
			and all(
				student_field_order.index(left) < student_field_order.index(right)
				for left, right in (
					("talisma_student_number", "student_name"),
					("student_name", "talisma_identity_name_column_2"),
					("talisma_identity_name_column_2", "first_name"),
					("talisma_identity_name_column_3", "middle_name"),
					("talisma_identity_name_column_4", "last_name"),
					("talisma_contact_section", "section_break_7"),
					("section_break_7", "gender"),
					("section_break_7", "talisma_ethnic_group"),
					("section_break_7", "talisma_marital_status"),
				)
			)
		),
		"student_academic_history_layout": (
			student_meta.get_field("talisma_status_history_section").label == "Student History"
			and student_meta.get_field("talisma_student_history_tab").label == "Documents"
			and student_field_order.index("talisma_advisor_assignments_html")
			< student_field_order.index("talisma_status_history_section")
			< student_field_order.index("talisma_academic_standing_section")
		),
		"gender_options": set(gender_values) == set(GENDER_OPTIONS),
		"gender_option_order": gender_options_query(
			"Gender", "", "name", 0, 20, None
		) == [[value] for value in GENDER_OPTIONS],
		"grading_scale_labels": (
			grading_interval_meta.get_field("threshold").label == "Minimum Score"
			and grading_interval_meta.get_field("grade_code").label == "Letter Grade"
			and grading_interval_meta.get_field("grade_description").label == "Name"
			and grading_interval_meta.get_field("talisma_maximum_score").label == "Maximum Score"
		),
		"grading_scale_ranges": grading_ranges
		== {
			grade_code: (grade_name, float(minimum), float(maximum), float(points))
			for grade_code, grade_name, minimum, maximum, points in DEMO_GRADING_INTERVALS
		},
		"applicant_classification_layout": (
			applicant_meta.get_field("talisma_campus").insert_after == "last_name"
			and applicant_meta.get_field("talisma_decision_section").insert_after == "paid"
			and applicant_meta.get_field("talisma_residency").insert_after == "student_category"
			and applicant_meta.get_field("talisma_deposit_status").insert_after
			== "talisma_admit_type"
		),
		"student_academic_layout": (
			student_meta.get_field("talisma_academic_level").insert_after
			== "talisma_home_campus"
			and student_meta.get_field("talisma_class_standing").insert_after
			== "talisma_academic_level"
			and student_meta.get_field("talisma_enrollment_status").insert_after
			== "nationality"
		),
		"family_details_configured": all(
			meta.get_field("talisma_family_members")
			and meta.get_field("talisma_family_members").options == "Talisma Family Member"
			and meta.get_field(section_field).label == "Family Details"
			and not meta.get_field(section_field).hidden
			and meta.get_field("guardians").hidden
			for meta, section_field in (
				(student_meta, "section_break_18"),
				(applicant_meta, "section_break_20"),
			)
		),
		"family_member_fields": (
			family_member_meta.get_field("family_member_name").fieldtype == "Data"
			and "Guardian" in family_member_meta.get_field("relation").options
		),
		"simplified_student_navigation": all(
			link_to
			not in {
				"Guardian",
				"Student Batch Name",
				"Student Log",
				"Program Enrollment",
				"Course Enrollment",
			}
			for _, link_to in student_management_links
		),
		"document_type_navigation": (
			("Document Type", "Talisma Student Document Type") in student_management_links
			and student_management_links.index(("Document Type", "Talisma Student Document Type"))
			> student_management_links.index(("Student", "Student"))
		),
		"academics_navigation_order": academics_sidebar_links[:8]
		== [
			("Academic Year", "Academic Year"),
			("Academic Term", "Academic Term"),
			("Degree", "Degree"),
			("Program", "Program"),
			("Course Category", "Course Category"),
			("Course", "Course"),
			("Topic", "Topic"),
			("Class Scheduling", "Student Group"),
		],
		"finance_navigation": finance_sidebar_links
		== [
			("Fee Category", "Fee Category"),
			("Fee Structure", "Fee Structure"),
			("Fee Schedule", "Fee Schedule"),
			("Student Billing", "Student Billing Report"),
			("Student Payments", "Student Payment Report"),
			("Scholarships", "Scholarship Report"),
			("Waivers", "Waiver Report"),
			("Refunds", "Refund Report"),
			("Student Account", "Student"),
		],
		"default_workspace": default_workspaces == [DEMO_WORKSPACE_NAME],
	}
	return {
		"ok": all(checks.values()),
		"checks": checks,
		"desktop_icon": icon,
		"visible_icons": visible_icons,
		"admissions_sidebar_links": admissions_sidebar_links,
		"student_management_links": student_management_links,
		"academics_sidebar_links": academics_sidebar_links,
		"finance_sidebar_links": finance_sidebar_links,
		"default_workspaces": default_workspaces,
		"gender_values": gender_values,
	}


def report_card_healthcheck() -> dict:
	"""Generate the seeded Education report card and return PDF metadata."""
	if frappe.local.site != DEMO_SITE:
		frappe.throw(f"Report-card health check is restricted to {DEMO_SITE}.")

	from talisma_sis.report_card import preview_report_card

	student = frappe.db.get_value(
		"Student", {"student_email_id": "avery.johnson@example.edu"}, "name"
	)
	preview_report_card(frappe.as_json({
		"student": student,
		"program": "Bachelor of Science in Computer Science",
		"assessment_group": "Fall 2026 Report Card",
		"academic_year": "2026-2027",
		"academic_term": "Fall 2026",
		"add_letterhead": 0,
		"show_marks": 1,
	}))
	pdf = frappe.response.get("filecontent") or b""
	return {
		"ok": pdf.startswith(b"%PDF") and len(pdf) > 1000,
		"filename": frappe.response.get("filename"),
		"bytes": len(pdf),
	}


def setup() -> dict[str, int]:
	"""Create the synthetic demo dataset on the dedicated demo site only."""
	if frappe.local.site != DEMO_SITE:
		frappe.throw(f"Demo setup is restricted to {DEMO_SITE}.")

	_required_apps()
	_configure_student_finance()
	_configure_gender_options()
	_remove_obsolete_demo_fields()
	_create_integration_fields()
	configure_class_scheduling()
	configure_academics()
	configure_assessment()
	configure_admission_intake()
	configure_curriculum()
	configure_student_records()
	configure_student_360()
	_configure_compact_form_layouts()
	foundation = _create_institutional_foundation()
	calendar = _create_academic_calendar()
	_create_education_catalog(foundation["academic_unit"], calendar["academic_term"])
	seed_demo_course_categories()
	seed_demo_curricula()
	_create_us_course_sections(foundation["campus"], calendar)
	seed_demo_admission_intake()
	_create_people_and_enrollments(foundation["campus"], calendar)
	seed_demo_admission_intake()
	seed_demo_student_records()
	configure_student_documents()
	seed_demo_curricula()
	_create_demo_assessment_results(calendar)
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	_create_demo_workspaces()
	_configure_demo_branding()
	_configure_demo_desktop_icons()
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
		"assessment_results": frappe.db.count("Assessment Result", {"docstatus": 1}),
		"curriculum_versions": frappe.db.count("Talisma Curriculum Version"),
		"curriculum_requirements": frappe.db.count("Talisma Curriculum Requirement"),
		"student_status_history": frappe.db.count("Talisma Student Status History"),
		"student_academic_programs": frappe.db.count("Talisma Student Academic Program"),
		"student_holds": frappe.db.count("Talisma Student Hold"),
		"admission_intakes": frappe.db.count("Student Admission"),
		"demo_workspaces": frappe.db.count(
			"Workspace",
			{"label": ["in", ["Admissions", "Registrar"]]},
		),
		"visible_desktop_icons": frappe.db.count("Desktop Icon", {"hidden": 0}),
	}


def restore_demo_navigation_after_migrate() -> None:
	"""Restore generated demo navigation removed by Frappe's orphan cleanup."""
	if frappe.local.site != DEMO_SITE or not frappe.db.exists("Workspace", DEMO_WORKSPACE_NAME):
		return
	_create_demo_workspaces()
	_configure_demo_desktop_icons()


def _required_apps() -> None:
	missing = {"erpnext", "education", "talisma_sis"} - set(frappe.get_installed_apps())
	if missing:
		frappe.throw(f"Install required apps before demo setup: {', '.join(sorted(missing))}")


def _configure_student_finance() -> None:
	"""Use Sales Invoice as the hidden accounting source for new student billing."""
	frappe.db.set_single_value("Education Settings", "create_so", 0)


def _configure_gender_options() -> None:
	"""Normalize the demo Gender master without leaving obsolete choices behind."""
	if frappe.db.exists("Gender", "Other") and not frappe.db.exists("Gender", "Others"):
		frappe.rename_doc("Gender", "Other", "Others", force=True)

	for value in GENDER_OPTIONS:
		if not frappe.db.exists("Gender", value):
			frappe.get_doc({"doctype": "Gender", "gender": value}).insert(
				ignore_permissions=True
			)

	for value in frappe.get_all("Gender", pluck="name"):
		if value not in GENDER_OPTIONS:
			frappe.delete_doc("Gender", value, ignore_permissions=True)


def _remove_obsolete_demo_fields() -> None:
	for doctype, fieldname in (
		("Student Applicant", "talisma_application_type"),
		("Student", "talisma_guardian_name"),
	):
		custom_field = frappe.db.exists(
			"Custom Field",
			{"dt": doctype, "fieldname": fieldname},
		)
		if custom_field:
			frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True)
			frappe.clear_cache(doctype=doctype)


def _create_integration_fields() -> None:
	create_custom_fields(
		{
			"Student Applicant": [
				_field("talisma_campus", "Campus", "Link", "Talisma Campus", "last_name"),
				_field("talisma_name_column_2", "", "Column Break", "", "first_name"),
				_field("talisma_name_column_3", "", "Column Break", "", "middle_name"),
				{
					"fieldname": "talisma_decision_section",
					"label": "Admission Decision",
					"fieldtype": "Section Break",
					"insert_after": "paid",
				},
				{
					"fieldname": "talisma_decision_date",
					"label": "Decision Date",
					"fieldtype": "Date",
					"insert_after": "talisma_decision_section",
					"read_only": 1,
				},
				{
					"fieldname": "talisma_decision_note",
					"label": "Decision Note",
					"fieldtype": "Small Text",
					"insert_after": "talisma_decision_date",
				},
				{
					"fieldname": "talisma_converted_student",
					"label": "Student Record",
					"fieldtype": "Link",
					"options": "Student",
					"insert_after": "talisma_decision_note",
					"read_only": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "talisma_program_enrollment",
					"label": "Program Enrollment",
					"fieldtype": "Link",
					"options": "Program Enrollment",
					"insert_after": "talisma_converted_student",
					"read_only": 1,
					"no_copy": 1,
				},
				_field(
					"talisma_decision_column_2",
					"",
					"Column Break",
					"",
					"talisma_decision_note",
				),
				{
					**_field("talisma_admit_type", "Admit Type", "Select", "", "academic_term"),
					"options": "New First-Time\nTransfer\nReturning\nVisiting\nExchange",
				},
				{
					**_field("talisma_residency", "Residency Classification", "Select", "", "student_category"),
					"options": "In-State\nOut-of-State\nInternational\nUndetermined",
				},
				{
					**_field("talisma_deposit_status", "Enrollment Deposit", "Select", "", "talisma_admit_type"),
					"options": "Not Required\nPending\nPaid\nWaived",
				},
				_field(
					"talisma_family_members",
					"Family Members",
					"Table",
					"Talisma Family Member",
					"section_break_20",
				),
			],
			"Student": [
				_field("talisma_home_campus", "Home Campus", "Link", "Talisma Campus", "student_email_id"),
				_field("talisma_preferred_name", "Preferred Name", "Data", "", "first_name"),
				_field("talisma_pronouns", "Pronouns", "Data", "", "talisma_preferred_name"),
				_field("talisma_name_column_3", "", "Column Break", "", "middle_name"),
				_field("talisma_profile_section", "", "Section Break", "", "last_name"),
				_field("talisma_profile_column_2", "", "Column Break", "", "talisma_pronouns"),
				_field("talisma_profile_column_3", "", "Column Break", "", "user"),
				_field("talisma_academic_section", "Academic Details", "Section Break", "", "nationality"),
				_field("talisma_academic_column_2", "", "Column Break", "", "talisma_class_standing"),
				_field("talisma_academic_column_3", "", "Column Break", "", "talisma_catalog_year"),
				_field(
					"talisma_family_members",
					"Family Members",
					"Table",
					"Talisma Family Member",
					"section_break_18",
				),
				{
					**_field("talisma_academic_level", "Academic Level", "Select", "", "talisma_home_campus"),
					"options": "Undergraduate\nGraduate\nProfessional\nNon-Degree",
				},
				{
					**_field("talisma_class_standing", "Class Standing", "Select", "", "talisma_academic_level"),
					"options": "Freshman\nSophomore\nJunior\nSenior\nGraduate",
				},
				{
					**_field("talisma_enrollment_status", "Enrollment Status", "Select", "", "nationality"),
					"options": "Full-Time\nPart-Time\nLeave of Absence\nWithdrawn\nGraduated",
				},
				_field("talisma_catalog_year", "Catalog Year", "Data", "", "talisma_enrollment_status"),
				_field("talisma_expected_graduation_term", "Expected Graduation Term", "Link", "Academic Term", "talisma_catalog_year"),
				_field("talisma_advisor", "Academic Advisor", "Link", "Instructor", "talisma_expected_graduation_term"),
			],
			"Program": [
				_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "program_name"),
			],
			"Course": [
				_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "course_name"),
				_field("talisma_subject_code", "Subject Code", "Data", "", "talisma_academic_unit"),
				_field("talisma_catalog_number", "Catalog Number", "Data", "", "talisma_subject_code"),
				{
					**_field("talisma_credit_hours", "Credit Hours", "Float", "", "talisma_catalog_number"),
					"precision": 1,
				},
				{
					**_field("talisma_course_level", "Course Level", "Select", "", "talisma_credit_hours"),
					"options": "Undergraduate\nGraduate\nProfessional\nContinuing Education",
				},
				{
					**_field("talisma_grading_basis", "Grading Basis", "Select", "", "talisma_course_level"),
					"options": "Letter Grade\nPass/Fail\nAudit\nSatisfactory/Unsatisfactory",
				},
				_field("talisma_effective_term", "Effective Term", "Link", "Academic Term", "talisma_grading_basis"),
				{
					**_field("talisma_repeatable", "Repeatable for Credit", "Check", "", "talisma_effective_term"),
					"default": 0,
				},
			],
			"Academic Term": [
				_field("talisma_registration_opens", "Registration Opens", "Date", "", "term_end_date"),
				_field("talisma_add_drop_deadline", "Add/Drop Deadline", "Date", "", "talisma_registration_opens"),
				_field("talisma_census_date", "Census Date", "Date", "", "talisma_add_drop_deadline"),
				_field("talisma_withdrawal_deadline", "Withdrawal Deadline", "Date", "", "talisma_census_date"),
				_field("talisma_grades_due", "Grades Due", "Date", "", "talisma_withdrawal_deadline"),
			],
			"Student Group": [
				{
					**_field("talisma_crn", "CRN", "Data", "", "student_group_name"),
					"unique": 1,
					"in_list_view": 1,
				},
				_field("talisma_section_number", "Section", "Data", "", "talisma_crn"),
				_field("talisma_campus", "Campus", "Link", "Talisma Campus", "talisma_section_number"),
				{
					**_field("talisma_delivery_method", "Delivery Method", "Select", "", "talisma_campus"),
					"options": "In Person\nOnline\nHybrid\nHyFlex",
				},
				{
					**_field("talisma_section_status", "Section Status", "Select", "", "talisma_delivery_method"),
					"options": "Open\nClosed\nCancelled",
					"default": "Open",
				},
				_field("talisma_waitlist_capacity", "Waitlist Capacity", "Int", "", "max_strength"),
				_field("talisma_meeting_days", "Meeting Days", "Data", "", "talisma_waitlist_capacity"),
				_field("talisma_start_time", "Start Time", "Time", "", "talisma_meeting_days"),
				_field("talisma_end_time", "End Time", "Time", "", "talisma_start_time"),
				_field("talisma_room", "Room", "Link", "Room", "talisma_end_time"),
				_field("talisma_primary_instructor", "Primary Instructor", "Link", "Instructor", "talisma_room"),
			],
			"Course Enrollment": [
				_field("talisma_course_section", "Course Section / CRN", "Link", "Student Group", "course"),
			],
			"Instructor": [
				_field("talisma_academic_unit", "Academic Unit", "Link", "Talisma Academic Unit", "instructor_name"),
			],
			"Program Enrollment": [
				_field("talisma_campus", "Campus", "Link", "Talisma Campus", "program"),
				{
					"fieldname": "talisma_registration_status",
					"label": "Registration Status",
					"fieldtype": "Data",
					"insert_after": "talisma_campus",
					"read_only": 1,
				},
				{
					"fieldname": "talisma_registration_updated_on",
					"label": "Registration Updated On",
					"fieldtype": "Datetime",
					"insert_after": "talisma_registration_status",
					"read_only": 1,
				},
			],
		}
	)
	for doctype, section_field in (
		("Student", "section_break_18"),
		("Student Applicant", "section_break_20"),
	):
		make_property_setter(doctype, section_field, "label", "Family Details", "Data")
		make_property_setter(doctype, section_field, "hidden", 0, "Check")
		make_property_setter(doctype, "guardians", "hidden", 1, "Check")
	make_property_setter("Student", "relations_tab", "hidden", 1, "Check")
	make_property_setter("Student", "section_break_20", "hidden", 1, "Check")
	make_property_setter("Student", "siblings", "hidden", 1, "Check")

	make_property_setter(
		"Student Admission", "introduction", "hidden", 1, "Check"
	)
	make_property_setter(
		"Student Applicant", "section_break_xuzu", "label", "Application Details", "Data"
	)


def _set_compact_field_order(doctype: str, regions: list[tuple[str, str, list[str]]]) -> None:
	field_order = [field.fieldname for field in frappe.get_meta(doctype).fields]
	for _start_field, end_field, compact_region in regions:
		missing_fields = set(compact_region) - set(field_order)
		if missing_fields:
			frappe.throw(
				f"Cannot configure compact {doctype} layout; missing fields: "
				f"{', '.join(sorted(missing_fields))}."
			)

		field_order = [
			fieldname for fieldname in field_order if fieldname not in compact_region
		]
		end = field_order.index(end_field)
		field_order[end:end] = compact_region

	make_property_setter(
		doctype,
		None,
		"field_order",
		json.dumps(field_order),
		"Data",
		for_doctype=True,
	)
	frappe.clear_cache(doctype=doctype)


def _configure_compact_form_layouts() -> None:
	"""Keep related fields on the same visual row without uneven column gaps."""
	_set_compact_field_order(
		"Student Applicant",
		[
			(
				"first_name",
				"section_break_23",
				[
					"first_name",
					"talisma_name_column_2",
					"middle_name",
					"talisma_name_column_3",
					"last_name",
					"section_break_xuzu",
					"application_date",
					"application_status",
					"student_admission",
					"program",
					"column_break_8",
					"academic_year",
					"academic_term",
					"talisma_campus",
					"column_break_lvby",
					"talisma_degree",
					"talisma_academic_unit",
					"talisma_application_fee",
					"talisma_applicant_classification_section",
					"student_email_id",
					"student_category",
					"talisma_residency",
					"talisma_applicant_classification_column_2",
					"talisma_admit_type",
					"talisma_deposit_status",
					"paid",
					"talisma_admin_override_section",
					"talisma_capacity_override",
					"naming_series",
					"image",
					"talisma_workflow_section",
					"talisma_application_stage",
					"talisma_last_transition_on",
					"talisma_workflow_column_2",
					"talisma_last_transition_by",
					"talisma_eligibility_section",
					"talisma_eligibility_status",
					"talisma_eligibility_notes",
					"talisma_eligibility_column_2",
					"talisma_eligibility_reviewed_by",
					"talisma_eligibility_reviewed_on",
					"talisma_fee_section",
					"talisma_application_fee_status",
					"talisma_payment_reference",
					"talisma_decision_section",
					"talisma_decision_date",
					"talisma_decision_note",
					"talisma_decision_column_2",
					"talisma_converted_student",
					"talisma_program_enrollment",
					"talisma_decision_audit_section",
					"talisma_decision_by",
					"talisma_decision_reason",
					"talisma_decision_column_3",
					"talisma_admission_conditions",
					"talisma_transfer_audit_section",
					"talisma_transfer_reason",
					"talisma_transfer_column_2",
					"talisma_transferred_by",
					"talisma_transferred_on",
				],
			),
		],
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
		talisma_registration_opens="2026-04-01",
		talisma_add_drop_deadline="2026-09-01",
		talisma_census_date="2026-09-04",
		talisma_withdrawal_deadline="2026-11-06",
		talisma_grades_due="2026-12-23",
	)
	frappe.db.set_value(
		"Academic Term",
		academic_term,
		{
			"talisma_registration_opens": "2026-04-01",
			"talisma_add_drop_deadline": "2026-09-01",
			"talisma_census_date": "2026-09-04",
			"talisma_withdrawal_deadline": "2026-11-06",
			"talisma_grades_due": "2026-12-23",
		},
		update_modified=False,
	)
	return {"academic_year": academic_year, "academic_term": academic_term}


def _create_education_catalog(academic_unit: str, academic_term: str) -> None:
	for name, abbreviation, degree in (
		("Bachelor of Science in Computer Science", "BSCS", "Bachelor of Science"),
		("Master of Science in Data Science", "MSDS", "Master of Science"),
	):
		_ensure(
			"Program",
			name,
			program_name=name,
			program_abbreviation=abbreviation,
			talisma_program_code=abbreviation,
			talisma_degree=degree,
			talisma_academic_unit=academic_unit,
		)

	for code, title in (
		("CS-101", "Introduction to Computer Science"),
		("CS-201", "Data Structures"),
		("CS-220", "Database Systems"),
		("CS-310", "Software Engineering"),
		("DS-501", "Foundations of Data Science"),
		("DS-520", "Applied Machine Learning"),
	):
		subject_code, catalog_number = code.split("-", 1)
		course_level = "Graduate" if int(catalog_number) >= 500 else "Undergraduate"
		program = (
			"Master of Science in Data Science"
			if subject_code == "DS"
			else "Bachelor of Science in Computer Science"
		)
		_ensure(
			"Course",
			title,
			course_name=title,
			course_code=code,
			talisma_course_code=code,
			talisma_program=program,
			talisma_academic_unit=academic_unit,
			talisma_subject_code=subject_code,
			talisma_catalog_number=catalog_number,
			talisma_credit_hours=3,
			talisma_course_level=course_level,
			talisma_course_type="Core",
			talisma_grading_basis="Letter Grade",
			talisma_effective_term=academic_term,
		)
		frappe.db.set_value(
			"Course",
			title,
			{
				"talisma_course_code": code,
				"talisma_program": program,
				"talisma_subject_code": subject_code,
				"talisma_catalog_number": catalog_number,
				"talisma_credit_hours": 3,
				"talisma_course_level": course_level,
				"talisma_course_type": "Core",
				"talisma_grading_basis": "Letter Grade",
				"talisma_effective_term": academic_term,
			},
			update_modified=False,
		)

	for name in ("Dr. Maya Chen", "Professor Daniel Brooks", "Dr. Elena Rodriguez"):
		_ensure("Instructor", None, filters={"instructor_name": name}, instructor_name=name, talisma_academic_unit=academic_unit)

	_ensure_program_courses(
		"Bachelor of Science in Computer Science",
		(
			"Introduction to Computer Science",
			"Data Structures",
			"Database Systems",
			"Software Engineering",
		),
	)
	_ensure_program_courses(
		"Master of Science in Data Science",
		("Foundations of Data Science", "Applied Machine Learning"),
	)


def _ensure_program_courses(program_name: str, courses: tuple[str, ...]) -> None:
	program = frappe.get_doc("Program", program_name)
	existing = {row.course for row in program.courses}
	changed = False
	for course in courses:
		if course not in existing:
			program.append("courses", {"course": course, "required": 1})
			changed = True
	if changed:
		program.save(ignore_permissions=True)


def _create_us_course_sections(campus: str, calendar: dict[str, str]) -> None:
	room_a = _ensure(
		"Room",
		None,
		filters={"room_name": "Innovation Hall 101"},
		room_name="Innovation Hall 101",
		room_number="IH-101",
		seating_capacity="40",
	)
	room_b = _ensure(
		"Room",
		None,
		filters={"room_name": "Technology Center 204"},
		room_name="Technology Center 204",
		room_number="TC-204",
		seating_capacity="35",
	)
	sections = (
		("10001", "001", "Introduction to Computer Science", "MWF", "09:00:00", "09:50:00", room_a, "Dr. Maya Chen"),
		("10002", "001", "Data Structures", "TR", "10:00:00", "11:15:00", room_b, "Professor Daniel Brooks"),
		("10003", "001", "Database Systems", "TR", "11:30:00", "12:45:00", room_a, "Dr. Elena Rodriguez"),
		("10004", "001", "Software Engineering", "MWF", "13:00:00", "13:50:00", room_b, "Dr. Maya Chen"),
	)
	for crn, section_number, course, days, start_time, end_time, room, instructor in sections:
		section = _ensure(
			"Student Group",
			None,
			filters={"talisma_crn": crn},
			student_group_name=f"Fall 2026 {course} {section_number}",
			academic_year=calendar["academic_year"],
			academic_term=calendar["academic_term"],
			group_based_on="Course",
			program="Bachelor of Science in Computer Science",
			course=course,
			max_strength=30,
			talisma_crn=crn,
			talisma_section_number=section_number,
			talisma_campus=campus,
			talisma_delivery_method="In Person",
			talisma_section_status="Open",
			talisma_waitlist_capacity=5,
			talisma_meeting_days=days,
			talisma_start_time=start_time,
			talisma_end_time=end_time,
			talisma_room=room,
			talisma_primary_instructor=frappe.db.get_value(
				"Instructor", {"instructor_name": instructor}, "name"
			),
		)
		_ensure(
			"Course Schedule",
			None,
			filters={"student_group": section, "schedule_date": "2026-08-24"},
			student_group=section,
			course=course,
			instructor=frappe.db.get_value("Instructor", {"instructor_name": instructor}, "name"),
			room=room,
			schedule_date="2026-08-24",
			from_time=start_time,
			to_time=end_time,
		)


def _create_people_and_enrollments(campus: str, calendar: dict[str, str]) -> None:
	program = "Bachelor of Science in Computer Science"
	academic_year = calendar["academic_year"]
	academic_term = calendar["academic_term"]
	for first, last, status in (("Avery", "Johnson", "Applied"), ("Jordan", "Lee", "Approved"), ("Taylor", "Morgan", "Admitted")):
		stage = {"Applied": "Submitted", "Approved": "Approved", "Admitted": "Admitted"}[status]
		applicant = _ensure(
			"Student Applicant",
			None,
			filters={"student_email_id": f"{first.lower()}.{last.lower()}@example.edu"},
			first_name=first,
			last_name=last,
			student_email_id=f"{first.lower()}.{last.lower()}@example.edu",
			student_admission="Fall 2026 Intake",
			program=program,
			academic_year=academic_year,
			academic_term=academic_term,
			application_date=getdate("2026-07-15"),
			application_status=status,
			talisma_application_stage=stage,
			talisma_eligibility_status="Eligible" if status in {"Approved", "Admitted"} else "Pending",
			talisma_campus=campus,
			talisma_admit_type="New First-Time",
			talisma_residency="Out-of-State" if first == "Avery" else "In-State",
			talisma_deposit_status="Paid" if status == "Admitted" else "Pending",
		)
		frappe.db.set_value(
			"Student Applicant",
			applicant,
			{
				"talisma_admit_type": "New First-Time",
				"talisma_residency": "Out-of-State" if first == "Avery" else "In-State",
				"talisma_deposit_status": "Paid" if status == "Admitted" else "Pending",
			},
			update_modified=False,
		)

	students = (
		("Alex", "Carter"), ("Priya", "Shah"), ("Noah", "Williams"),
		("Sofia", "Martinez"), ("Ethan", "Brown"), ("Mia", "Davis"),
	)
	courses = (
		"Introduction to Computer Science",
		"Data Structures",
		"Database Systems",
		"Software Engineering",
	)
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
			talisma_preferred_name=first,
			talisma_academic_level="Undergraduate",
			talisma_class_standing="Freshman",
			talisma_enrollment_status="Full-Time",
			talisma_catalog_year="2026-2027",
			talisma_advisor=frappe.db.get_value("Instructor", {"instructor_name": "Dr. Maya Chen"}, "name"),
		)
		frappe.db.set_value(
			"Student",
			student,
			{
				"talisma_preferred_name": first,
				"talisma_academic_level": "Undergraduate",
				"talisma_class_standing": "Freshman",
				"talisma_enrollment_status": "Full-Time",
				"talisma_catalog_year": "2026-2027",
				"talisma_expected_graduation_term": None,
				"talisma_advisor": frappe.db.get_value(
					"Instructor", {"instructor_name": "Dr. Maya Chen"}, "name"
				),
			},
			update_modified=False,
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


def _create_demo_assessment_results(calendar: dict[str, str]) -> None:
	"""Create one complete, printable Education report-card example for Avery."""
	student = frappe.db.get_value(
		"Student", {"student_email_id": "avery.johnson@example.edu"}, "name"
	)
	section = frappe.db.get_value("Student Group", {"talisma_crn": "10001"}, "name")
	if not student or not section:
		frappe.throw("Avery and CRN 10001 are required before creating report-card data.")

	section_doc = frappe.get_doc("Student Group", section)
	if student not in {row.student for row in section_doc.students}:
		section_doc.append("students", {"student": student, "active": 1})
		section_doc.save(ignore_permissions=True)

	root = "All Assessment Groups"
	parent = _ensure(
		"Assessment Group",
		"Fall 2026 Report Card",
		assessment_group_name="Fall 2026 Report Card",
		parent_assessment_group=root,
		is_group=1,
	)
	leaf = _ensure(
		"Assessment Group",
		"Fall 2026 Final Examination",
		assessment_group_name="Fall 2026 Final Examination",
		parent_assessment_group=parent,
		is_group=0,
	)
	criterion = _ensure(
		"Assessment Criteria",
		"Final Examination",
		assessment_criteria="Final Examination",
	)

	grading_scale = frappe.db.get_value(
		"Grading Scale", {"grading_scale_name": DEMO_GRADING_SCALE_NAME}, "name"
	)
	if not grading_scale:
		scale = frappe.get_doc({
			"doctype": "Grading Scale",
			"grading_scale_name": DEMO_GRADING_SCALE_NAME,
			"description": "Demo US higher-education letter grade scale.",
			"intervals": [
				{
					"grade_code": grade_code,
					"grade_description": grade_name,
					"threshold": minimum,
					"talisma_maximum_score": maximum,
					"talisma_grade_points": points,
				}
				for grade_code, grade_name, minimum, maximum, points in DEMO_GRADING_INTERVALS
			],
		}).insert(ignore_permissions=True)
		scale.submit()
		grading_scale = scale.name
	else:
		scale = frappe.get_doc("Grading Scale", grading_scale)
		scale.flags.ignore_validate_update_after_submit = True
		scale.set("intervals", [
			{
				"grade_code": grade_code,
				"grade_description": grade_name,
				"threshold": minimum,
				"talisma_maximum_score": maximum,
				"talisma_grade_points": points,
			}
			for grade_code, grade_name, minimum, maximum, points in DEMO_GRADING_INTERVALS
		])
		scale.save(ignore_permissions=True)

	plan_name = frappe.db.get_value(
		"Assessment Plan",
		{"student_group": section, "assessment_group": leaf, "docstatus": ("!=", 2)},
		"name",
	)
	if not plan_name:
		plan = frappe.get_doc({
			"doctype": "Assessment Plan",
			"student_group": section,
			"assessment_name": "CS 101 Final Examination",
			"assessment_group": leaf,
			"grading_scale": grading_scale,
			"program": "Bachelor of Science in Computer Science",
			"course": "Introduction to Computer Science",
			"academic_year": calendar["academic_year"],
			"academic_term": calendar["academic_term"],
			"schedule_date": "2026-12-10",
			"from_time": "09:00:00",
			"to_time": "11:00:00",
			"maximum_assessment_score": 100,
			"assessment_criteria": [
				{"assessment_criteria": criterion, "maximum_score": 100}
			],
		}).insert(ignore_permissions=True)
		plan.submit()
		plan_name = plan.name

	if not frappe.db.exists(
		"Assessment Result",
		{"assessment_plan": plan_name, "student": student, "docstatus": ("!=", 2)},
	):
		result = frappe.get_doc({
			"doctype": "Assessment Result",
			"assessment_plan": plan_name,
			"student": student,
			"details": [{"assessment_criteria": criterion, "score": 94}],
			"comment": "Excellent mastery of foundational computing concepts.",
		}).insert(ignore_permissions=True)
		result.submit()


def _create_demo_workspaces() -> None:
	_migrate_module_workspaces()
	_create_workspace(
		'Admissions',
		'users',
		[
			('Applicants', 'Student Applicant', 'Blue'),
			('Admission Intakes', 'Student Admission', 'Orange'),
			('Programs', 'Program', 'Green'),
			('Students', 'Student', 'Grey'),
			('Intake Report', 'Admission Intake Report', 'Blue', 'Report'),
			('Program Capacity', 'Program Capacity Report', 'Green', 'Report'),
			('Program Applications', 'Program-wise Applications', 'Purple', 'Report'),
			('Open Intakes', 'Open Admission Intakes', 'Green', 'Report'),
			('Closed Intakes', 'Closed Admission Intakes', 'Grey', 'Report'),
			('Seat Availability', 'Seat Availability Report', 'Orange', 'Report'),
		],
	)
	_create_workspace(
		'Registrar',
		'list',
		[
			('Student Records', 'Student', 'Blue'),
			('Assessment Results', 'Assessment Result', 'Purple'),
		],
		number_cards=[
			('Talisma Students', 'Students', 'Student'),
			('Talisma Programs', 'Programs', 'Program'),
		],
	)
	_create_workspace(
		'Student Records',
		'users-round',
		[
			('Students', 'Student', 'Blue'),
		],
	)
	_create_workspace(
		'Academics',
		'book-open-text',
		[
			('Academic Years', 'Academic Year', 'Orange'),
			('Academic Terms', 'Academic Term', 'Purple'),
			('Degrees', 'Degree', 'Blue'),
			('Programs', 'Program', 'Green'),
			('Course Categories', 'Course Category', 'Orange'),
			('Courses', 'Course', 'Blue'),
			('Topics', 'Topic', 'Purple'),
			('Class Scheduling', 'Student Group', 'Green'),
		],
	)
	_create_workspace(
		'Faculty & Sections',
		'presentation',
		[
			('Faculty', 'Instructor', 'Blue'),
			('Course Sections', 'Student Group', 'Green'),
			('Course Schedules', 'Course Schedule', 'Orange'),
			('Rooms', 'Room', 'Grey'),
		],
	)
	_create_workspace(
		'Assessment & Grades',
		'book-open-check',
		[
			('Assessment Plans', 'Assessment Plan', 'Blue'),
			('Assessment Results', 'Assessment Result', 'Green'),
			('Assessment Gradebooks', 'Assessment Gradebook', 'Purple'),
			('Grading Scales', 'Grading Scale', 'Orange'),
			('Report Cards', 'Student Report Generation Tool', 'Purple'),
		],
	)
	_create_workspace(
		'Attendance',
		'calendar-days',
		[
			('Student Attendance', 'Student Attendance', 'Blue'),
			('Attendance Tool', 'Student Attendance Tool', 'Green'),
			('Leave Applications', 'Student Leave Application', 'Orange'),
		],
	)
	_create_workspace(
		'Finance',
		'landmark',
		[
			('Fee Categories', 'Fee Category', 'Blue'),
			('Fee Structures', 'Fee Structure', 'Green'),
			('Fee Schedules', 'Fee Schedule', 'Orange'),
			('Student Billing', 'Student Billing Report', 'Blue', 'Report'),
			('Student Payments', 'Student Payment Report', 'Green', 'Report'),
			('Scholarships', 'Scholarship Report', 'Purple', 'Report'),
			('Waivers', 'Waiver Report', 'Grey', 'Report'),
			('Refunds', 'Refund Report', 'Orange', 'Report'),
			('Student Accounts', 'Student', 'Blue'),
			('Outstanding Balances', 'Outstanding Balance Report', 'Red', 'Report'),
			('Program Fee Collection', 'Program Fee Collection Report', 'Green', 'Report'),
		],
	)
	_create_workspace(
		'Reports',
		'sheet',
		[
			('Course Assessment', 'Course wise Assessment Report', 'Blue', 'Report'),
			('Final Grades', 'Final Assessment Grades', 'Green', 'Report'),
			('Monthly Attendance', 'Student Monthly Attendance Sheet', 'Orange', 'Report'),
			('Student Contacts', 'Student and Guardian Contact Details', 'Purple', 'Report'),
			('Student Billing', 'Student Billing Report', 'Blue', 'Report'),
			('Student Payments', 'Student Payment Report', 'Green', 'Report'),
			('Outstanding Balances', 'Outstanding Balance Report', 'Orange', 'Report'),
			('Program Fee Collection', 'Program Fee Collection Report', 'Purple', 'Report'),
			('Admission Intakes', 'Admission Intake Report', 'Blue', 'Report'),
			('Program Capacity', 'Program Capacity Report', 'Green', 'Report'),
			('Program Applications', 'Program-wise Applications', 'Purple', 'Report'),
			('Open Admission Intakes', 'Open Admission Intakes', 'Green', 'Report'),
			('Closed Admission Intakes', 'Closed Admission Intakes', 'Grey', 'Report'),
			('Seat Availability', 'Seat Availability Report', 'Orange', 'Report'),
		],
	)


def _migrate_module_workspaces() -> None:
	for legacy_name, current_name in LEGACY_MODULE_WORKSPACES.items():
		if not frappe.db.exists('Workspace', legacy_name):
			continue
		if frappe.db.exists('Workspace', current_name):
			frappe.db.set_value('Workspace', legacy_name, 'is_hidden', 1)
			continue
		frappe.rename_doc('Workspace', legacy_name, current_name, force=True)


def _configure_demo_branding() -> None:
	logo = '/assets/talisma_sis/talisma-mark.svg'
	frappe.db.set_single_value('Navbar Settings', 'app_logo', logo)
	for fieldname, value in {
		'app_name': DEMO_WORKSPACE_NAME,
		'title_prefix': DEMO_WORKSPACE_NAME,
		'app_logo': logo,
		'favicon': logo,
		'splash_image': logo,
	}.items():
		frappe.db.set_single_value('Website Settings', fieldname, value)

	workspace_source = next(
		(
			name
			for name in (
				MISSPELLED_DEMO_WORKSPACE_NAME,
				LEGACY_DEMO_WORKSPACE_NAME,
				'Education',
			)
			if frappe.db.exists('Workspace', name)
		),
		None,
	)
	if workspace_source and not frappe.db.exists('Workspace', DEMO_WORKSPACE_NAME):
		frappe.rename_doc(
			'Workspace',
			workspace_source,
			DEMO_WORKSPACE_NAME,
			force=True,
		)

	if frappe.db.exists('Workspace', DEMO_WORKSPACE_NAME):
		frappe.db.set_value(
			'Workspace',
			DEMO_WORKSPACE_NAME,
			{'label': DEMO_WORKSPACE_NAME, 'title': DEMO_WORKSPACE_NAME, 'is_hidden': 0},
		)

	users = frappe.get_all(
		'User',
		filters={'enabled': 1, 'user_type': 'System User'},
		pluck='name',
	)
	for user in users:
		frappe.db.set_value('User', user, 'default_workspace', DEMO_WORKSPACE_NAME)


def _configure_demo_desktop_icons() -> None:
	_configure_education_sidebar()
	icons = frappe.get_all('Desktop Icon', fields=['name'])
	for icon in icons:
		frappe.db.set_value('Desktop Icon', icon.name, 'hidden', 1)

	for index, (label, workspace, icon) in enumerate(DEMO_MODULES, start=1):
		_create_module_sidebar(label, workspace, icon)
		values = {
			'label': label,
			'icon_type': 'Link',
			'link_type': 'Workspace Sidebar',
			'link_to': label,
			'icon': icon,
			'logo_url': DEMO_MODULE_ART[label],
			'icon_image': None,
			'bg_color': 'blue',
			'idx': index,
			'hidden': 0,
			'standard': 1,
			'app': 'talisma_sis',
			'restrict_removal': 1,
		}
		existing = frappe.db.exists('Desktop Icon', label)
		if existing:
			frappe.db.set_value('Desktop Icon', existing, values)
		else:
			frappe.get_doc({'doctype': 'Desktop Icon', **values}).insert(ignore_permissions=True)

	frappe.cache.delete_key('desktop_icons')
	frappe.cache.delete_key('bootinfo')


def _create_module_sidebar(label: str, workspace: str, icon: str) -> None:
	values = {
		'title': label,
		'module': 'Talisma SIS',
		'header_icon': icon,
		'standard': 0,
		'items': [{
			'type': 'Link',
			'label': 'Home',
			'icon': 'home',
			'link_type': 'Workspace',
			'link_to': workspace,
		}],
	}
	existing = frappe.db.exists('Workspace Sidebar', label)
	if existing:
		doc = frappe.get_doc('Workspace Sidebar', existing)
		doc.update(values)
		doc.set('items', values['items'])
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({
			'doctype': 'Workspace Sidebar',
			'name': label,
			**values,
		}).insert(ignore_permissions=True)


def _configure_education_sidebar() -> None:
	sidebar_source = next(
		(
			name
			for name in (
				MISSPELLED_DEMO_WORKSPACE_NAME,
				LEGACY_DEMO_WORKSPACE_NAME,
				'Education',
			)
			if frappe.db.exists('Workspace Sidebar', name)
		),
		None,
	)
	if sidebar_source and not frappe.db.exists('Workspace Sidebar', DEMO_WORKSPACE_NAME):
		frappe.rename_doc(
			'Workspace Sidebar',
			sidebar_source,
			DEMO_WORKSPACE_NAME,
			force=True,
			rebuild_search=False,
		)

	if not frappe.db.exists('Workspace Sidebar', DEMO_WORKSPACE_NAME):
		frappe.throw('Education Workspace Sidebar is required for the demo launcher.')

	sidebar = frappe.get_doc('Workspace Sidebar', DEMO_WORKSPACE_NAME)
	sidebar.title = DEMO_WORKSPACE_NAME
	for item in sidebar.items:
		if item.link_type == 'Workspace' and item.link_to in {
			'Education',
			LEGACY_DEMO_WORKSPACE_NAME,
			MISSPELLED_DEMO_WORKSPACE_NAME,
		}:
			item.link_to = DEMO_WORKSPACE_NAME

	admissions_section = next(
		(item for item in sidebar.items if item.type == 'Section Break' and item.label == 'Admissions'),
		None,
	)
	admission_intake = next(
		(item for item in sidebar.items if item.link_type == 'DocType' and item.link_to == 'Student Admission'),
		None,
	)
	student_application = next(
		(item for item in sidebar.items if item.link_type == 'DocType' and item.link_to == 'Student Applicant'),
		None,
	)
	if not all((admissions_section, admission_intake, student_application)):
		frappe.throw('Education Admissions sidebar links are required for the demo launcher.')

	admission_intake.label = 'Admission Intake'
	student_application.label = 'Student Application'
	academics_section = next(
		(item for item in sidebar.items if item.type == 'Section Break' and item.label == 'Academics'),
		None,
	)
	academics_links = []
	if academics_section:
		for label, link_to in (
			('Academic Year', 'Academic Year'),
			('Academic Term', 'Academic Term'),
			('Degree', 'Degree'),
			('Program', 'Program'),
			('Course Category', 'Course Category'),
			('Course', 'Course'),
			('Topic', 'Topic'),
			('Class Scheduling', 'Student Group'),
		):
			item = next(
				(
					row
					for row in sidebar.items
					if row.link_type == 'DocType' and row.link_to == link_to
				),
				None,
			)
			if not item:
				item = sidebar.append('items', {
					'type': 'Link',
					'label': label,
					'child': 1,
					'link_type': 'DocType',
					'link_to': link_to,
				})
			item.label = label
			item.child = 1
			academics_links.append(item)
	ordered_items = [
		item
		for item in sidebar.items
		if item not in (admission_intake, student_application)
		and not (
			item.link_type == 'DocType'
			and item.link_to in {
				'Guardian',
				'Student Batch Name',
				'Student Log',
				'Program Enrollment',
				'Course Enrollment',
			}
		)
	]
	admissions_index = ordered_items.index(admissions_section)
	ordered_items[admissions_index + 1:admissions_index + 1] = [
		admission_intake,
		student_application,
	]
	student_management_section = next(
		(
			item
			for item in ordered_items
			if item.type == 'Section Break' and item.label == 'Student Management'
		),
		None,
	)
	if student_management_section:
		student_record_item = next(
			(
				item
				for item in sidebar.items
				if item.link_type == 'DocType'
				and item.link_to == 'Student'
				and item.label != 'Student Account'
			),
			None,
		)
		if not student_record_item:
			student_record_item = sidebar.append('items', {
				'type': 'Link',
				'link_type': 'DocType',
				'link_to': 'Student',
			})
		student_record_item.label = 'Student'
		student_record_item.child = 1
		document_type_item = next(
			(
				item
				for item in sidebar.items
				if item.link_type == 'DocType'
				and item.link_to == 'Talisma Student Document Type'
			),
			None,
		)
		if not document_type_item:
			document_type_item = sidebar.append('items', {
				'type': 'Link',
				'link_type': 'DocType',
				'link_to': 'Talisma Student Document Type',
			})
		document_type_item.label = 'Document Type'
		document_type_item.child = 1
		ordered_items = [
			item for item in ordered_items
			if item not in (student_record_item, document_type_item)
		]
		student_management_index = ordered_items.index(student_management_section)
		ordered_items.insert(student_management_index + 1, student_record_item)
		student_category_index = next(
			(
				index
				for index, item in enumerate(ordered_items)
				if item.link_type == 'DocType' and item.link_to == 'Student Category'
			),
			student_management_index + 1,
		)
		ordered_items.insert(student_category_index + 1, document_type_item)
	if academics_section:
		academics_index = ordered_items.index(academics_section)
		existing_academics_children = []
		for item in ordered_items[academics_index + 1:]:
			if not item.child:
				break
			existing_academics_children.append(item)
		ordered_items = [
			item
			for item in ordered_items
			if item not in existing_academics_children and item not in academics_links
		]
		academics_index = ordered_items.index(academics_section)
		ordered_items[academics_index + 1:academics_index + 1] = academics_links
	assessment_section = next(
		(item for item in ordered_items if item.type == 'Section Break' and item.label == 'Assessment'),
		None,
	)
	if assessment_section:
		gradebook_item = next(
			(item for item in sidebar.items if item.link_type == 'DocType' and item.link_to == 'Assessment Gradebook'),
			None,
		)
		if not gradebook_item:
			gradebook_item = sidebar.append('items', {
				'type': 'Link',
				'label': 'Assessment Gradebook',
				'child': 1,
				'link_type': 'DocType',
				'link_to': 'Assessment Gradebook',
			})
		gradebook_item.label = 'Assessment Gradebook'
		gradebook_item.child = 1
		ordered_items = [item for item in ordered_items if item is not gradebook_item]
		result_index = next(
			(
				index
				for index, item in enumerate(ordered_items)
				if item.link_type == 'DocType' and item.link_to == 'Assessment Result'
			),
			ordered_items.index(assessment_section),
		)
		ordered_items.insert(result_index + 1, gradebook_item)
	finance_section = next(
		(
			item
			for item in ordered_items
			if item.type == 'Section Break' and item.label in {'Fee Management', 'Finance'}
		),
		None,
	)
	if finance_section:
		finance_section.label = 'Finance'
		finance_targets = (
			('Fee Category', 'DocType', 'Fee Category'),
			('Fee Structure', 'DocType', 'Fee Structure'),
			('Fee Schedule', 'DocType', 'Fee Schedule'),
			('Student Billing', 'Report', 'Student Billing Report'),
			('Student Payments', 'Report', 'Student Payment Report'),
			('Scholarships', 'Report', 'Scholarship Report'),
			('Waivers', 'Report', 'Waiver Report'),
			('Refunds', 'Report', 'Refund Report'),
			('Student Account', 'DocType', 'Student'),
		)
		finance_index = ordered_items.index(finance_section)
		existing_finance_children = []
		for item in ordered_items[finance_index + 1:]:
			if not item.child:
				break
			existing_finance_children.append(item)
		finance_links = []
		for label, link_type, link_to in finance_targets:
			item = next(
				(
					row
					for row in existing_finance_children
					if row.link_type == link_type and row.link_to == link_to
				),
				None,
			)
			if not item:
				item = sidebar.append('items', {
					'type': 'Link',
					'link_type': link_type,
					'link_to': link_to,
				})
			item.label = label
			item.child = 1
			finance_links.append(item)
		ordered_items = [
			item
			for item in ordered_items
			if item not in existing_finance_children and item not in finance_links
		]
		finance_index = ordered_items.index(finance_section)
		ordered_items[finance_index + 1:finance_index + 1] = finance_links
	sidebar.items = ordered_items
	for index, item in enumerate(sidebar.items, start=1):
		item.idx = index
	sidebar.save(ignore_permissions=True)


def _sidebar_section_links(sidebar, section_label: str) -> list[tuple[str, str]]:
	section_index = next(
		(
			index
			for index, item in enumerate(sidebar.items)
			if item.type == 'Section Break' and item.label == section_label
		),
		None,
	)
	if section_index is None:
		return []

	links = []
	for item in sidebar.items[section_index + 1:]:
		if not item.child:
			break
		if item.type == 'Link':
			links.append((item.label, item.link_to))
	return links


def _create_workspace(
	label: str,
	icon: str,
	shortcuts: list[tuple[str, ...]],
	number_cards: list[tuple[str, str, str]] | None = None,
) -> None:
	number_cards = number_cards or []
	resolved_number_cards = []
	content = [{
		'id': f'{label}-header',
		'type': 'header',
		'data': {'text': f'<span class=h4><b>{label}</b></span>', 'col': 12},
	}]
	for index, (card_name, card_label, document_type) in enumerate(number_cards):
		resolved_name = _create_number_card(card_name, card_label, document_type)
		resolved_number_cards.append(resolved_name)
		content.append({
			'id': f'{label}-number-{index}',
			'type': 'number_card',
			'data': {'number_card_name': resolved_name, 'col': 3},
		})
	for index, shortcut in enumerate(shortcuts):
		shortcut_label = shortcut[0]
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
			{
				'label': item[0],
				'link_to': item[1],
				'type': item[3] if len(item) > 3 else 'DocType',
				'color': item[2],
			}
			for item in shortcuts
		],
		'number_cards': [{'number_card_name': name} for name in resolved_number_cards],
	}
	existing = frappe.db.exists('Workspace', label)
	if existing:
		doc = frappe.get_doc('Workspace', existing)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({'doctype': 'Workspace', **values}).insert(ignore_permissions=True)


def _create_number_card(name: str, label: str, document_type: str) -> str:
	values = {
		'label': label,
		'type': 'Document Type',
		'document_type': document_type,
		'function': 'Count',
		'is_public': 1,
		'show_percentage_stats': 0,
		'show_full_number': 1,
		'filters_json': '[]',
	}
	existing = frappe.db.get_value(
		'Number Card',
		{'label': label, 'document_type': document_type, 'type': 'Document Type'},
		'name',
	)
	if existing:
		doc = frappe.get_doc('Number Card', existing)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({'doctype': 'Number Card', **values})
		doc.name = name
		doc.insert(ignore_permissions=True)
	return doc.name


def _ensure(doctype: str, name: str | None, filters: dict | None = None, **values) -> str:
	filters = filters or ({"name": name} if name else values)
	existing = frappe.db.get_value(doctype, filters, "name")
	if existing:
		return existing

	doc = frappe.get_doc({"doctype": doctype, **values})
	if name:
		doc.name = name
	return doc.insert(ignore_permissions=True).name
