"""Compatibility adapter for Education v16 report-card PDF generation."""

from __future__ import annotations

import json

import frappe
from frappe.utils.pdf import get_pdf
from frappe.www.printview import get_letter_head

from education.education.report.course_wise_assessment_report.course_wise_assessment_report import (
	get_child_assessment_groups,
	get_formatted_result,
)


def _get_attendance_count(student, academic_year, academic_term=None):
	"""Aggregate attendance without legacy SQL expressions in query fields."""
	attendance = frappe._dict(total=0)
	if academic_year:
		from_date, to_date = frappe.db.get_value(
			"Academic Year", academic_year, ["year_start_date", "year_end_date"]
		)
	elif academic_term:
		from_date, to_date = frappe.db.get_value(
			"Academic Term", academic_term, ["term_start_date", "term_end_date"]
		)
	else:
		from_date = to_date = None

	if not from_date or not to_date:
		frappe.throw("Please enter an Academic Year with Start and End dates.")

	rows = frappe.db.sql(
		"""
		select status, count(*) as count
		from `tabStudent Attendance`
		where student = %(student)s
			and docstatus = 1
			and date between %(from_date)s and %(to_date)s
		group by status
		""",
		{"student": student, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	for row in rows:
		if row.status == "Present":
			attendance.present = row.count
		elif row.status == "Absent":
			attendance.absent = row.count
		attendance.total += row.count
	return attendance


@frappe.whitelist()
def preview_report_card(doc):
	"""Render Education's standard report card with a Frappe-v16-safe query."""
	doc = frappe._dict(json.loads(doc))
	doc.students = [doc.student]
	values = get_formatted_result(doc, get_course=True)
	doc.attendance = _get_attendance_count(
		doc.students[0], doc.academic_year, doc.academic_term
	)
	letterhead = get_letter_head(doc, not doc.add_letterhead)
	html = frappe.render_template(
		"education/education/doctype/student_report_generation_tool/student_report_generation_tool.html",
		{
			"doc": doc,
			"assessment_result": values.get("assessment_result"),
			"courses": values.get("courses"),
			"assessment_groups": get_child_assessment_groups(doc.assessment_group),
			"letterhead": letterhead and letterhead.get("content"),
			"add_letterhead": doc.add_letterhead if doc.add_letterhead else 0,
		},
	)
	# Keep the PDF self-contained. Frappe's standard print wrapper loads remote font
	# and stylesheet URLs, which wkhtmltopdf cannot resolve in the isolated network.
	final_template = f"""<!doctype html>
	<html><head><meta charset="utf-8"><title>Report Card</title><style>
	body {{ color:#1f2937; font-family:Arial,sans-serif; margin:0; }}
	.row {{ display:block; width:100%; clear:both; }}
	.col-xs-1,.col-xs-5,.col-xs-6,.col-xs-7,.col-xs-11,.col-xs-12 {{ float:left; box-sizing:border-box; }}
	.col-xs-1 {{ width:8.333%; }} .col-xs-5 {{ width:41.667%; }}
	.col-xs-6 {{ width:50%; }} .col-xs-7 {{ width:58.333%; }}
	.col-xs-11 {{ width:91.667%; }} .col-xs-12 {{ width:100%; }}
	table {{ border-collapse:collapse; width:100%; }}
	.table-bordered th,.table-bordered td {{ border:1px solid #d1d5db; }}
	caption {{ color:#111827; font-weight:bold; padding:10px 0; text-align:left; }}
	</style></head><body>{html}</body></html>"""
	final_template = final_template.replace('src="/', 'src="http://frontend:8080/')
	frappe.response.filename = f"Report Card {doc.students[0]}.pdf"
	frappe.response.filecontent = get_pdf(
		final_template,
		options={"load-error-handling": "ignore", "load-media-error-handling": "ignore"},
	)
	frappe.response.type = "pdf"
