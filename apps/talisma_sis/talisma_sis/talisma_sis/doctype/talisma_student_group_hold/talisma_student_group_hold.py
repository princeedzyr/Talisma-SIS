from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


BLOCK_FIELDS = (
	"blocks_registration",
	"blocks_transcript",
	"blocks_graduation",
	"blocks_financial_activity",
)


class TalismaStudentGroupHold(Document):
	def validate(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		if not any(self.get(fieldname) for fieldname in BLOCK_FIELDS):
			frappe.throw(_("Select at least one activity for this Group Hold to block."))
		members = group_members(self.student_group)
		if not members:
			frappe.throw(_("The selected Student Group has no active members."))
		if self.is_new():
			existing = frappe.db.exists(
				"Talisma Student Group Hold",
				{
					"student_group": self.student_group,
					"hold_type": self.hold_type,
					"reason": self.reason,
					"effective_from": self.effective_from,
					"status": "Active",
				},
			)
			if existing:
				frappe.throw(_("This Student Group Hold is already active as {0}.").format(existing))

	def after_insert(self):
		members = group_members(self.student_group)
		created = 0
		for member in members:
			hold = frappe.new_doc("Talisma Student Hold")
			hold.update(
				{
					"student": member.student,
					"source_group_hold": self.name,
					"hold_type": self.hold_type,
					"reason": self.reason,
					"effective_from": self.effective_from,
					"effective_to": self.effective_to,
					"status": "Active",
					**{fieldname: self.get(fieldname) for fieldname in BLOCK_FIELDS},
				}
			)
			hold.insert()
			created += 1
		frappe.db.set_value(
			self.doctype,
			self.name,
			{
				"status": "Active",
				"affected_student_count": created,
				"applied_by": frappe.session.user,
				"applied_on": now_datetime(),
			},
			update_modified=False,
		)


def group_members(student_group: str) -> list:
	return frappe.get_all(
		"Student Group Student",
		filters={"parent": student_group, "parenttype": "Student Group", "active": 1},
		fields=["student", "student_name"],
		order_by="idx asc",
	)


@frappe.whitelist()
def release_group_hold(group_hold: str, release_comments: str) -> dict:
	doc = frappe.get_doc("Talisma Student Group Hold", group_hold)
	if not frappe.has_permission(doc.doctype, "write", doc=doc):
		frappe.throw(_("You do not have permission to release this Student Group Hold."), frappe.PermissionError)
	comments = str(release_comments or "").strip()
	if not comments:
		frappe.throw(_("Release Comments are required."))
	if doc.status == "Released":
		return {"success": True, "name": doc.name, "released_holds": 0, "message": "This Student Group Hold is already released."}

	released = 0
	for name in frappe.get_all(
		"Talisma Student Hold",
		filters={"source_group_hold": doc.name, "status": "Active"},
		pluck="name",
	):
		hold = frappe.get_doc("Talisma Student Hold", name)
		hold.status = "Released"
		hold.release_comments = comments
		hold.released_by = frappe.session.user
		hold.released_on = now_datetime()
		hold.save()
		released += 1

	doc.db_set(
		{
			"status": "Released",
			"release_comments": comments,
			"released_by": frappe.session.user,
			"released_on": now_datetime(),
		},
	)
	return {"success": True, "name": doc.name, "released_holds": released, "message": f"Released {released} student holds."}
