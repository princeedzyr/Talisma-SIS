"""Authoritative, effective-dated Student lifecycle transitions.

Student Status History is the system of record. Fields on Student are projections
maintained by ``refresh_student_snapshot`` and must never be authored directly.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from talisma_sis.student_records import refresh_student_snapshot


STATUSES = (
	"Applicant",
	"Admitted",
	"Enrolled",
	"Active",
	"Leave of Absence",
	"Withdrawn",
	"Suspended",
	"Dismissed",
	"Graduated",
	"Deceased",
)

ALLOWED_TRANSITIONS = {
	None: set(STATUSES),
	"Applicant": {"Admitted", "Withdrawn", "Deceased"},
	"Admitted": {"Enrolled", "Withdrawn", "Deceased"},
	"Enrolled": {"Active", "Leave of Absence", "Withdrawn", "Suspended", "Dismissed", "Deceased"},
	"Active": {"Leave of Absence", "Withdrawn", "Suspended", "Dismissed", "Graduated", "Deceased"},
	"Leave of Absence": {"Active", "Withdrawn", "Dismissed", "Deceased"},
	"Suspended": {"Active", "Withdrawn", "Dismissed", "Deceased"},
	"Withdrawn": {"Active", "Deceased"},
	"Dismissed": {"Active", "Deceased"},
	"Graduated": {"Active", "Deceased"},
	"Deceased": set(),
}


def transition_student_status(
	student: str,
	new_status: str,
	effective_from=None,
	reason: str | None = None,
	academic_term: str | None = None,
	source: str = "Registrar",
	comments: str | None = None,
	changed_by: str | None = None,
	ignore_permissions: bool = False,
) -> dict:
	"""Close the current period, append a new status period, and refresh Student."""
	if not frappe.db.exists("Student", student):
		frappe.throw(_("Student {0} does not exist.").format(frappe.bold(student)))
	if new_status not in STATUSES:
		frappe.throw(_("{0} is not a valid Student lifecycle status.").format(frappe.bold(new_status)))
	if not reason or not reason.strip():
		frappe.throw(_("A reason is required for every Student status change."))
	if not ignore_permissions:
		_require_transition_permission(student)

	effective_from = getdate(effective_from or today())
	# Serialize transitions for this Student so two requests cannot create two
	# simultaneously-current status rows.
	frappe.db.sql("select name from `tabStudent` where name=%s for update", student)
	current = _status_on(student, effective_from)
	previous_status = current.status if current else None
	if previous_status == new_status:
		refresh_student_snapshot(student)
		return _transition_result(current, changed=False)
	if new_status not in ALLOWED_TRANSITIONS.get(previous_status, set()):
		frappe.throw(
			_("Student status cannot change from {0} to {1}.").format(
				frappe.bold(previous_status or _("No Status")), frappe.bold(new_status)
			)
		)

	next_row = _next_status(student, effective_from)
	if current and (not current.effective_to or getdate(current.effective_to) > effective_from):
		frappe.db.set_value(
			"Talisma Student Status History",
			current.name,
			"effective_to",
			effective_from,
			update_modified=False,
		)

	row = frappe.get_doc(
		{
			"doctype": "Talisma Student Status History",
			"student": student,
			"previous_status": previous_status,
			"status": new_status,
			"reason": reason.strip(),
			# Lifecycle status is institution-wide and intentionally independent
			# from an Academic Term. The argument remains for API compatibility.
			"academic_term": None,
			"effective_from": effective_from,
			"effective_to": next_row.effective_from if next_row else None,
			"source": source,
			"approved_by": changed_by or frappe.session.user,
			"changed_by": changed_by or frappe.session.user,
			"transition_timestamp": now_datetime(),
			"comments": comments,
		}
	)
	row.insert(ignore_permissions=ignore_permissions)
	refresh_student_snapshot(student)
	return _transition_result(row, changed=True)


@frappe.whitelist()
def change_student_status(
	student: str,
	new_status: str,
	effective_from=None,
	reason: str | None = None,
	academic_term: str | None = None,
	comments: str | None = None,
) -> dict:
	"""Registrar-facing manual action used by the Student Profile dialog."""
	return transition_student_status(
		student,
		new_status,
		effective_from,
		reason,
		academic_term,
		source="Registrar",
		comments=comments,
	)


@frappe.whitelist()
def get_allowed_transitions(student: str) -> dict:
	if not frappe.has_permission("Student", "read", student):
		frappe.throw(_("You do not have permission to view this Student."), frappe.PermissionError)
	current = _status_on(student, getdate(today()))
	status = current.status if current else None
	return {"current_status": status, "allowed_statuses": sorted(ALLOWED_TRANSITIONS.get(status, set()))}


@frappe.whitelist()
def get_status_history_record(record: str) -> dict:
	doc = frappe.get_doc("Talisma Student Status History", record)
	if not frappe.has_permission("Talisma Student Status History", "read", doc=doc):
		frappe.throw(_("You do not have permission to view this Student history record."), frappe.PermissionError)
	return {
		"name": doc.name,
		"student": doc.student,
		"previous_status": doc.previous_status,
		"status": doc.status,
		"reason": doc.reason,
		"effective_from": doc.effective_from,
		"effective_to": doc.effective_to,
		"source": doc.source,
		"changed_by": doc.changed_by or doc.approved_by,
		"transition_timestamp": doc.transition_timestamp or doc.creation,
		"comments": doc.comments,
	}


@frappe.whitelist()
def update_status_history_record(record: str, reason: str, comments: str | None = None) -> dict:
	"""Correct narrative details without rewriting the authoritative transition."""
	doc = frappe.get_doc("Talisma Student Status History", record)
	if not frappe.has_permission("Talisma Student Status History", "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Student history record."), frappe.PermissionError)
	if not reason or not reason.strip():
		frappe.throw(_("Reason is required."))
	doc.reason = reason.strip()
	doc.comments = comments
	doc.save()
	return {"name": doc.name, "reason": doc.reason, "comments": doc.comments}


def program_enrollment_created(doc, method=None) -> None:
	"""The first authoritative Program Enrollment moves Admitted to Enrolled."""
	if not doc.get("student"):
		return
	current = _status_on(doc.student, getdate(doc.get("enrollment_date") or today()))
	if current and current.status not in {"Applicant", "Admitted"}:
		return
	transition_student_status(
		doc.student,
		"Enrolled",
		doc.get("enrollment_date") or today(),
		"Program enrollment created",
		None,
		"Registrar",
		ignore_permissions=True,
	)


def course_enrollment_created(doc, method=None) -> None:
	"""A first valid course registration moves Enrolled to Active."""
	if not doc.get("student"):
		return
	effective_date = doc.get("enrollment_date") or today()
	current = _status_on(doc.student, getdate(effective_date))
	if not current or current.status not in {"Admitted", "Enrolled"}:
		return
	transition_student_status(
		doc.student,
		"Active",
		effective_date,
		"First course registration created",
		None,
		"Registrar",
		ignore_permissions=True,
	)


def record_application_admission(student: str, applicant) -> None:
	"""Record Applicant and Admitted milestones once a Student identity exists."""
	if frappe.db.exists("Talisma Student Status History", {"student": student}):
		return
	application_date = getdate(applicant.get("creation") or today())
	decision_date = getdate(applicant.get("talisma_decision_date") or today())
	transition_student_status(
		student,
		"Applicant",
		application_date,
		"Student application submitted",
		None,
		"Admissions",
		ignore_permissions=True,
	)
	transition_student_status(
		student,
		"Admitted",
		max(application_date, decision_date),
		"Student application admitted",
		None,
		"Admissions",
		ignore_permissions=True,
	)


def approve_leave_of_absence(student: str, effective_from, reason: str, academic_term=None, comments=None):
	return transition_student_status(student, "Leave of Absence", effective_from, reason, academic_term, "Student Request", comments)


def return_from_leave(student: str, effective_from, reason: str, academic_term=None, comments=None):
	return transition_student_status(student, "Active", effective_from, reason, academic_term, "Registrar", comments)


def approve_university_withdrawal(student: str, effective_from, reason: str, academic_term=None, comments=None):
	return transition_student_status(student, "Withdrawn", effective_from, reason, academic_term, "Student Request", comments)


def suspend_student(student: str, effective_from, reason: str, academic_term=None, comments=None):
	return transition_student_status(student, "Suspended", effective_from, reason, academic_term, "Institutional Action", comments)


def reinstate_student(student: str, effective_from, reason: str, academic_term=None, comments=None):
	return transition_student_status(student, "Active", effective_from, reason, academic_term, "Institutional Action", comments)


def complete_degree_award(student: str, effective_from, reason: str, academic_term=None, comments=None):
	return transition_student_status(student, "Graduated", effective_from, reason, academic_term, "Degree Awarding", comments)


def record_deceased(student: str, effective_from, reason: str, comments=None):
	return transition_student_status(student, "Deceased", effective_from, reason, source="Institutional Action", comments=comments)


def _status_on(student: str, as_of):
	rows = frappe.get_all(
		"Talisma Student Status History",
		filters={"student": student, "effective_from": ("<=", as_of)},
		fields=["*"],
		order_by="effective_from desc, creation desc",
	)
	return next((row for row in rows if not row.effective_to or getdate(row.effective_to) > as_of), None)


def _next_status(student: str, effective_from):
	rows = frappe.get_all(
		"Talisma Student Status History",
		filters={"student": student, "effective_from": (">", effective_from)},
		fields=["name", "effective_from"],
		order_by="effective_from asc, creation asc",
		limit=1,
	)
	return rows[0] if rows else None


def _require_transition_permission(student: str) -> None:
	student_doc = frappe.get_doc("Student", student)
	if not frappe.has_permission("Student", "write", doc=student_doc) or not frappe.has_permission(
		"Talisma Student Status History", "create"
	):
		frappe.throw(_("You do not have permission to change this Student's lifecycle status."), frappe.PermissionError)


def _transition_result(row, changed: bool) -> dict:
	return {
		"name": row.name,
		"status": row.status,
		"effective_from": row.effective_from,
		"effective_to": row.effective_to,
		"changed": changed,
	}
