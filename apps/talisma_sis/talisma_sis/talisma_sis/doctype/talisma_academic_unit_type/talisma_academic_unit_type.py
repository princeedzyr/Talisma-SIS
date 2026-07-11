# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

import re
from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document


TYPE_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{2,32}$")
CAPABILITY_FIELDS = ("can_grant_credentials", "can_own_programs", "can_own_courses")


class TalismaAcademicUnitType(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_validate(self) -> None:
		if self.type_code:
			self.type_code = self.type_code.strip().upper()

	def validate(self) -> None:
		if not TYPE_CODE_PATTERN.fullmatch(self.type_code or ""):
			frappe.throw(
				_("Type Code must be 2 to 32 characters using only A-Z, 0-9, hyphen or underscore."),
				frappe.ValidationError,
			)

		duplicate = frappe.db.exists(self.doctype, {"type_code": self.type_code, "name": ["!=", self.name]})
		if duplicate:
			frappe.throw(
				_("Type Code {0} already exists.").format(frappe.bold(self.type_code)),
				frappe.UniqueValidationError,
			)

		if self.is_new():
			return

		stored = frappe.db.get_value(
			self.doctype,
			self.name,
			["type_code", "type_name", *CAPABILITY_FIELDS],
			as_dict=True,
		)
		if stored and self.type_code != stored.type_code:
			frappe.throw(_("Type Code cannot be changed after creation."), frappe.ValidationError)

		if not frappe.db.exists("Talisma Academic Unit", {"unit_type": self.name}):
			return

		if self.type_name != stored.type_name or any(self.get(field) != stored.get(field) for field in CAPABILITY_FIELDS):
			frappe.throw(
				_("The name and capability maxima of a referenced Unit Type cannot be changed."),
				frappe.ValidationError,
			)
