"""Configurable student document requirements and secure portal uploads."""

from __future__ import annotations

import os

import frappe
from frappe import _
from frappe.utils import add_days, cint, now, today


STAFF_ROLES = {"System Manager", "Academics User"}


def configure_student_documents() -> None:
	"""Create reusable document types and a visible demo student document."""
	for values in (
		{
			"document_name": "Government-issued Photo ID",
			"document_code": "PHOTO-ID",
			"description": "Passport, driver's license, or another government-issued photo ID.",
			"allowed_extensions": "pdf,jpg,jpeg,png",
			"max_file_size_mb": 10,
			"requires_expiry_date": 1,
		},
		{
			"document_name": "Official Transcript",
			"document_code": "TRANSCRIPT",
			"description": "Official transcript from the previously attended institution.",
			"allowed_extensions": "pdf",
			"max_file_size_mb": 15,
			"requires_expiry_date": 0,
		},
	):
		if frappe.db.exists("Talisma Student Document Type", values["document_name"]):
			frappe.db.set_value(
				"Talisma Student Document Type", values["document_name"], {**values, "active": 1}, update_modified=False
			)
		else:
			frappe.get_doc({
				"doctype": "Talisma Student Document Type", **values, "active": 1
			}).insert(ignore_permissions=True)

	student = frappe.db.get_value("Student", {"first_name": "Prince"}, "name")
	if student and not frappe.db.exists(
		"Talisma Student Document",
		{"student": student, "document_type": "Government-issued Photo ID"},
	):
		frappe.get_doc({
			"doctype": "Talisma Student Document",
			"student": student,
			"document_type": "Government-issued Photo ID",
			"required": 1,
			"status": "Missing",
			"due_date": add_days(today(), 14),
		}).insert(ignore_permissions=True)


def student_for_user(user: str | None = None) -> str | None:
	user = user or frappe.session.user
	if not user or user == "Guest":
		return None
	student = frappe.db.get_value("Student", {"user": user}, "name")
	return student or frappe.db.get_value("Student", {"student_email_id": user}, "name")


def document_permission_query(user: str | None = None) -> str:
	user = user or frappe.session.user
	if STAFF_ROLES.intersection(frappe.get_roles(user)):
		return ""
	student = student_for_user(user)
	if not student:
		return "1=0"
	return f"`tabTalisma Student Document`.`student` = {frappe.db.escape(student)}"


def document_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	user = user or frappe.session.user
	if STAFF_ROLES.intersection(frappe.get_roles(user)):
		return True
	return bool(student_for_user(user) == doc.student and permission_type == "read")


@frappe.whitelist()
def assign_document_requirement(
	student: str,
	document_type: str,
	due_date: str | None = None,
	required: int = 1,
) -> dict:
	if not frappe.has_permission("Talisma Student Document", "create"):
		frappe.throw(_("You do not have permission to assign student documents."), frappe.PermissionError)
	if not frappe.db.exists("Student", student):
		frappe.throw(_("Student does not exist."))
	if not frappe.db.get_value("Talisma Student Document Type", document_type, "active"):
		frappe.throw(_("Select an active Document Type."))
	existing = frappe.db.get_value(
		"Talisma Student Document",
		{"student": student, "document_type": document_type},
		"name",
	)
	if existing:
		frappe.throw(_("This Document Type is already assigned to the student."))
	doc = frappe.get_doc({
		"doctype": "Talisma Student Document",
		"student": student,
		"document_type": document_type,
		"required": cint(required),
		"due_date": due_date,
		"status": "Missing",
	}).insert()
	return _document_dict(doc)


@frappe.whitelist()
def get_student_document(document: str) -> dict:
	doc = frappe.get_doc("Talisma Student Document", document)
	doc.check_permission("read")
	return _document_dict(doc)


@frappe.whitelist()
def update_student_document(
	document: str,
	required: int = 1,
	due_date: str | None = None,
	status: str = "Missing",
	document_file: str | None = None,
	expiry_date: str | None = None,
	rejection_reason: str | None = None,
	notes: str | None = None,
) -> dict:
	doc = frappe.get_doc("Talisma Student Document", document)
	doc.check_permission("write")
	allowed_statuses = {"Missing", "Overdue", "Submitted", "Verified", "Rejected", "Expired", "Waived"}
	if status not in allowed_statuses:
		frappe.throw(_("Select a valid document status."))
	if status == "Verified" and not document_file:
		frappe.throw(_("A document must be uploaded before it can be verified."))
	if status == "Rejected" and not rejection_reason:
		frappe.throw(_("A rejection reason is required."))

	if document_file and document_file != doc.document_file:
		file_doc = frappe.db.get_value(
			"File", {"file_url": document_file}, ["name", "file_name", "file_size"], as_dict=True
		)
		if not file_doc:
			frappe.throw(_("The uploaded file could not be found."))
		document_type = frappe.get_doc("Talisma Student Document Type", doc.document_type)
		_validate_file(file_doc, document_type)
		frappe.db.set_value(
			"File",
			file_doc.name,
			{
				"is_private": 1,
				"attached_to_doctype": doc.doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "document_file",
			},
			update_modified=False,
		)
		doc.uploaded_by = frappe.session.user
		doc.uploaded_on = now()

	status_changed = status != doc.status
	doc.required = cint(required)
	doc.due_date = due_date
	doc.status = status
	doc.document_file = document_file
	doc.expiry_date = expiry_date
	doc.rejection_reason = rejection_reason if status == "Rejected" else None
	doc.notes = notes
	if status_changed and status in {"Verified", "Rejected", "Waived"}:
		doc.verified_by = frappe.session.user
		doc.verified_on = now()
	elif status_changed:
		doc.verified_by = None
		doc.verified_on = None
	doc.save()
	return _document_dict(doc)


@frappe.whitelist()
def review_student_document(document: str, status: str, rejection_reason: str | None = None) -> dict:
	if not frappe.has_permission("Talisma Student Document", "write"):
		frappe.throw(_("You do not have permission to review student documents."), frappe.PermissionError)
	if status not in {"Verified", "Rejected", "Waived"}:
		frappe.throw(_("Review status must be Verified, Rejected, or Waived."))
	doc = frappe.get_doc("Talisma Student Document", document)
	if status == "Verified" and not doc.document_file:
		frappe.throw(_("A document must be uploaded before it can be verified."))
	if status == "Rejected" and not rejection_reason:
		frappe.throw(_("A rejection reason is required."))
	doc.status = status
	doc.rejection_reason = rejection_reason if status == "Rejected" else None
	doc.verified_by = frappe.session.user
	doc.verified_on = now()
	doc.save()
	return _document_dict(doc)


@frappe.whitelist()
def upload_student_document(document: str, file_url: str, expiry_date: str | None = None) -> dict:
	student = student_for_user()
	if not student:
		frappe.throw(_("Your portal user is not linked to a Student record."), frappe.PermissionError)
	doc = frappe.get_doc("Talisma Student Document", document)
	if doc.student != student:
		frappe.throw(_("This document requirement does not belong to you."), frappe.PermissionError)
	if doc.status == "Waived":
		frappe.throw(_("A waived document requirement cannot be uploaded."))
	file_doc = frappe.db.get_value(
		"File",
		{"file_url": file_url},
		["name", "file_name", "file_size", "owner"],
		as_dict=True,
	)
	if not file_doc or file_doc.owner != frappe.session.user:
		frappe.throw(_("The uploaded file could not be verified."), frappe.PermissionError)
	document_type = frappe.get_doc("Talisma Student Document Type", doc.document_type)
	_validate_file(file_doc, document_type)
	if document_type.requires_expiry_date and not expiry_date:
		frappe.throw(_("Expiry Date is required for this document."))
	frappe.db.set_value(
		"File",
		file_doc.name,
		{
			"is_private": 1,
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"attached_to_field": "document_file",
		},
		update_modified=False,
	)
	doc.document_file = file_url
	doc.expiry_date = expiry_date
	doc.status = "Submitted"
	doc.uploaded_by = frappe.session.user
	doc.uploaded_on = now()
	doc.verified_by = None
	doc.verified_on = None
	doc.rejection_reason = None
	doc.save(ignore_permissions=True)
	return _document_dict(doc)


def portal_documents(student: str) -> list[dict]:
	rows = frappe.get_all(
		"Talisma Student Document",
		filters={"student": student},
		fields=[
			"name", "document_type", "required", "status", "due_date", "document_file",
			"expiry_date", "uploaded_on", "rejection_reason",
		],
		order_by="required desc, due_date asc, creation asc",
		ignore_permissions=True,
	)
	for row in rows:
		placeholder = frappe.db.get_value(
			"Talisma Student Document Type",
			row.document_type,
			["description", "allowed_extensions", "max_file_size_mb", "requires_expiry_date"],
			as_dict=True,
		) or {}
		row.update(placeholder)
	return rows


def _validate_file(file_doc, document_type) -> None:
	extension = os.path.splitext(file_doc.file_name or "")[1].lower().lstrip(".")
	allowed = {
		value.strip().lower().lstrip(".")
		for value in (document_type.allowed_extensions or "").split(",")
		if value.strip()
	}
	if allowed and extension not in allowed:
		frappe.throw(_("File type .{0} is not allowed. Use: {1}.").format(extension, ", ".join(sorted(allowed))))
	max_bytes = cint(document_type.max_file_size_mb) * 1024 * 1024
	if max_bytes and cint(file_doc.file_size) > max_bytes:
		frappe.throw(_("The file exceeds the {0} MB limit.").format(document_type.max_file_size_mb))


def _document_dict(doc) -> dict:
	return {
		"name": doc.name,
		"student": doc.student,
		"document_type": doc.document_type,
		"required": doc.required,
		"status": doc.status,
		"due_date": doc.due_date,
		"document_file": doc.document_file,
		"expiry_date": doc.expiry_date,
		"uploaded_by": doc.uploaded_by,
		"uploaded_on": doc.uploaded_on,
		"verified_by": doc.verified_by,
		"verified_on": doc.verified_on,
		"rejection_reason": doc.rejection_reason,
		"notes": doc.notes,
	}
