import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class TalismaStudentDocument(Document):
	def validate(self):
		if self.due_date and getdate(self.due_date) < getdate(today()) and self.status == "Missing":
			self.status = "Overdue"
		if self.document_file and self.status in {"Missing", "Overdue", "Rejected"}:
			self.status = "Submitted"
		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(_("A rejection reason is required."))
		if self.expiry_date and getdate(self.expiry_date) < getdate(today()) and self.status == "Verified":
			self.status = "Expired"

		duplicate = frappe.db.exists(
			self.doctype,
			{"student": self.student, "document_type": self.document_type, "name": ("!=", self.name)},
		)
		if duplicate:
			frappe.throw(_("This document requirement is already assigned to the student."))
