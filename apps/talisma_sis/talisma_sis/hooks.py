app_name = "talisma_sis"
app_title = "Talisma SIS"
app_publisher = "Talisma"
app_description = "Student Information System built on ERPNext"
app_email = "princeebinezer58@gmail.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext", "education"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "talisma_sis",
# 		"logo": "/assets/talisma_sis/logo.png",
# 		"title": "Talisma SIS",
# 		"route": "/talisma_sis",
# 		"has_permission": "talisma_sis.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------
app_include_css = '/assets/talisma_sis/css/talisma_demo.css?v=20260719-25'
app_include_js = '/assets/talisma_sis/js/talisma_demo.js?v=20260719-16'
web_include_css = '/assets/talisma_sis/css/talisma_demo.css?v=20260719-25'

website_route_rules = [
	{"from_route": "/student-documents", "to_route": "student_documents"},
]

# include js, css files in header of desk.html
# app_include_css = "/assets/talisma_sis/css/talisma_sis.css"
# app_include_js = "/assets/talisma_sis/js/talisma_sis.js"

# include js, css files in header of web template
# web_include_css = "/assets/talisma_sis/css/talisma_sis.css"
# web_include_js = "/assets/talisma_sis/js/talisma_sis.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "talisma_sis/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Student Applicant": "public/js/student_applicant_demo.js",
	"Student Admission": "public/js/admission_intake.js",
	"Student": "public/js/student_demo.js",
	"Student Group": "public/js/class_scheduling.js",
	"Course Schedule": "public/js/course_schedule_legacy_redirect.js",
	"Grading Scale": "public/js/grading_scale.js",
	"Assessment Plan": "public/js/assessment_plan.js",
	"Assessment Result": "public/js/assessment_result.js",
	"Assessment Gradebook": "public/js/assessment_gradebook.js",
	"Degree": "public/js/degree_demo.js",
	"Program": "public/js/program_academics.js",
	"Course Category": "public/js/course_category_demo.js",
	"Course": "public/js/course_academics.js",
	"Program Enrollment": "public/js/program_enrollment_demo.js",
	"Student Report Generation Tool": "public/js/student_report_generation_tool_demo.js",
}

doctype_list_js = {
	"Student Applicant": "public/js/student_applicant_list.js",
}

doc_events = {
	"Student Admission": {
		"validate": "talisma_sis.admissions.validate_admission_intake",
	},
	"Student Applicant": {
		"validate": "talisma_sis.admissions.validate_student_application_intake",
		"on_update": "talisma_sis.admissions.refresh_admission_capacity",
		"after_delete": "talisma_sis.admissions.refresh_admission_capacity",
	},
	"Student": {
		"validate": "talisma_sis.student_records.validate_student",
		"on_update": [
			"talisma_sis.student_records.capture_name_history",
			"talisma_sis.admissions.sync_admitted_application",
		],
	},
	"Program": {"validate": "talisma_sis.academics.validate_program"},
	"Program Enrollment": {"validate": "talisma_sis.curriculum.validate_program_enrollment"},
	"Course": {"validate": ["talisma_sis.us_academics.validate_course", "talisma_sis.academics.validate_course"]},
	"Course Category": {"validate": "talisma_sis.academics.validate_course_category"},
	"Course Enrollment": {
		"validate": "talisma_sis.academics.validate_course_enrollment",
		"on_update": "talisma_sis.academics.refresh_academic_standing_for_enrollment",
		"after_delete": "talisma_sis.academics.refresh_academic_standing_for_enrollment",
	},
	"Assessment Result": {
		"validate": "talisma_sis.assessment.validate_assessment_result",
		"before_update_after_submit": "talisma_sis.assessment.capture_grade_change",
		"on_submit": "talisma_sis.assessment.assessment_result_submitted",
		"on_cancel": "talisma_sis.assessment.assessment_result_cancelled",
	},
	"Assessment Plan": {"validate": "talisma_sis.assessment.validate_assessment_plan"},
	"Academic Term": {"validate": "talisma_sis.us_academics.validate_academic_term"},
	"Grading Scale": {"validate": "talisma_sis.academics.validate_grading_scale"},
	"Student Group": {
		"before_validate": "talisma_sis.class_scheduling.before_validate_class_schedule",
		"validate": ["talisma_sis.us_academics.validate_course_section", "talisma_sis.class_scheduling.validate_class_schedule"],
	},
	"Address": {"validate": "talisma_sis.student_records.validate_contact_dates"},
	"Contact": {"validate": "talisma_sis.student_records.validate_contact_dates"},
	"Talisma Student Identifier": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Status History": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Academic Program": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Advisor Assignment": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Hold": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Privacy Preference": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Classification History": {
		"validate": "talisma_sis.student_records.validate_effective_record",
		"on_update": "talisma_sis.student_records.sync_student_snapshot",
		"after_delete": "talisma_sis.student_records.sync_student_snapshot",
	},
	"Talisma Student Name History": {
		"validate": "talisma_sis.student_records.validate_effective_record",
	},
	"Talisma Curriculum Version": {
		"validate": "talisma_sis.curriculum.validate_curriculum_version",
		"on_update": "talisma_sis.curriculum.sync_program_curriculum",
		"after_delete": "talisma_sis.curriculum.sync_program_curriculum",
	},
}

permission_query_conditions = {
	"Talisma Student Identifier": "talisma_sis.student_records.identifier_query_conditions",
	"Talisma Student Document": "talisma_sis.student_documents.document_permission_query",
	"Talisma Class Waitlist Entry": "talisma_sis.class_scheduling.waitlist_permission_query",
}

has_permission = {
	"Talisma Student Identifier": "talisma_sis.student_records.identifier_has_permission",
	"Talisma Student Document": "talisma_sis.student_documents.document_has_permission",
	"Talisma Class Waitlist Entry": "talisma_sis.class_scheduling.waitlist_has_permission",
}

override_whitelisted_methods = {
	"education.education.doctype.student_report_generation_tool.student_report_generation_tool.preview_report_card":
		"talisma_sis.report_card.preview_report_card",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "talisma_sis/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "talisma_sis.utils.jinja_methods",
# 	"filters": "talisma_sis.utils.jinja_filters"
# }

# Installation
# ------------

before_install = "talisma_sis.install.before_install"
# after_install = "talisma_sis.install.after_install"

# Refuse schema migration on an unapproved upstream version tuple. This protects
# durable academic records from accidental upgrades while the compatibility
# matrix is intentionally narrow.
before_migrate = ["talisma_sis.install.validate_runtime"]
after_migrate = ["talisma_sis.demo.restore_demo_navigation_after_migrate"]

# Uninstallation
# ------------

# before_uninstall = "talisma_sis.uninstall.before_uninstall"
# after_uninstall = "talisma_sis.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "talisma_sis.utils.before_app_install"
# after_app_install = "talisma_sis.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "talisma_sis.utils.before_app_uninstall"
# after_app_uninstall = "talisma_sis.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "talisma_sis.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "talisma_sis.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"talisma_sis.tasks.all"
# 	],
# 	"daily": [
# 		"talisma_sis.tasks.daily"
# 	],
# 	"hourly": [
# 		"talisma_sis.tasks.hourly"
# 	],
# 	"weekly": [
# 		"talisma_sis.tasks.weekly"
# 	],
# 	"monthly": [
# 		"talisma_sis.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "talisma_sis.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "talisma_sis.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "talisma_sis.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "talisma_sis.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["talisma_sis.utils.before_request"]
after_request = ["talisma_sis.demo.redirect_demo_desk"]

# Job Events
# ----------
# before_job = ["talisma_sis.utils.before_job"]
# after_job = ["talisma_sis.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"talisma_sis.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
