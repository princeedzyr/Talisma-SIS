# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

import re
from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


UNIT_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{2,32}$")
ALLOWED_INSTITUTION_STATUSES = {"Planned", "Active"}
CAPABILITY_FIELDS = ("can_grant_credentials", "can_own_programs", "can_own_courses")
CLOSED_IMMUTABLE_FIELDS = ("unit_name", "short_name", "unit_type", "valid_from", "valid_to", *CAPABILITY_FIELDS)
STATUS_TRANSITIONS = {
	"Planned": {"Planned", "Active", "Closed"},
	"Active": {"Active", "Inactive", "Closed"},
	"Inactive": {"Inactive", "Active", "Closed"},
	"Closed": {"Closed"},
}


class TalismaAcademicUnit(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_validate(self) -> None:
		if self.unit_code:
			self.unit_code = self.unit_code.strip().upper()

	def validate(self) -> None:
		self._validate_code()
		self._validate_institution_and_dates()
		self._validate_type_and_capabilities()
		self._validate_changes_and_lifecycle()

	def _validate_code(self) -> None:
		if not UNIT_CODE_PATTERN.fullmatch(self.unit_code or ""):
			frappe.throw(
				_("Unit Code must be 2 to 32 characters using only A-Z, 0-9, hyphen or underscore."),
				frappe.ValidationError,
			)

		duplicate = frappe.db.exists(
			self.doctype,
			{"institution": self.institution, "unit_code": self.unit_code, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(
				_("Unit Code {0} already exists for this Institution.").format(frappe.bold(self.unit_code)),
				frappe.UniqueValidationError,
			)

	def _validate_institution_and_dates(self) -> None:
		institution = frappe.db.get_value(
			"Talisma Institution", self.institution, ["status", "valid_from", "valid_to"], as_dict=True
		)
		if not institution:
			frappe.throw(_("Institution does not exist."), frappe.ValidationError)
		if self.is_new() and institution.status not in ALLOWED_INSTITUTION_STATUSES:
			frappe.throw(
				_("New Academic Units can only be created for Planned or Active Institutions."),
				frappe.ValidationError,
			)

		valid_from = getdate(self.valid_from)
		valid_to = getdate(self.valid_to) if self.valid_to else None
		institution_from = getdate(institution.valid_from)
		institution_to = getdate(institution.valid_to) if institution.valid_to else None
		if valid_to and valid_to < valid_from:
			frappe.throw(_("Valid To cannot be before Valid From."), frappe.ValidationError)
		if valid_from < institution_from:
			frappe.throw(_("Academic Unit validity cannot begin before Institution validity."), frappe.ValidationError)
		if institution_to and (not valid_to or valid_to > institution_to):
			frappe.throw(_("Academic Unit validity cannot extend beyond Institution validity."), frappe.ValidationError)
		if self.status == "Closed" and not valid_to:
			frappe.throw(_("Valid To is required for a Closed Academic Unit."), frappe.ValidationError)

	def _validate_type_and_capabilities(self) -> None:
		unit_type = frappe.db.get_value(
			"Talisma Academic Unit Type", self.unit_type, ["disabled", *CAPABILITY_FIELDS], as_dict=True
		)
		if not unit_type:
			frappe.throw(_("Academic Unit Type does not exist."), frappe.ValidationError)
		if unit_type.disabled and (self.is_new() or self.has_value_changed("unit_type")):
			frappe.throw(_("A disabled Academic Unit Type cannot be assigned."), frappe.ValidationError)
		for field in CAPABILITY_FIELDS:
			if self.get(field) and not unit_type.get(field):
				frappe.throw(
					_("{0} is not permitted by this Academic Unit Type.").format(self.meta.get_label(field)),
					frappe.ValidationError,
				)

	def _validate_changes_and_lifecycle(self) -> None:
		if self.is_new():
			return
		stored = frappe.db.get_value(
			self.doctype,
			self.name,
			["institution", "unit_code", "unit_name", "short_name", "unit_type", "status", "valid_from", "valid_to", *CAPABILITY_FIELDS],
			as_dict=True,
		)
		if self.institution != stored.institution:
			frappe.throw(_("Institution cannot be changed after creation."), frappe.ValidationError)
		if self.unit_code != stored.unit_code:
			frappe.throw(_("Unit Code cannot be changed after creation."), frappe.ValidationError)
		if self.status not in STATUS_TRANSITIONS[stored.status]:
			frappe.throw(
				_("Status cannot change from {0} to {1}.").format(stored.status, self.status),
				frappe.ValidationError,
			)
		if self.unit_type != stored.unit_type and stored.status != "Planned":
			frappe.throw(_("Unit Type can only change while the Academic Unit is Planned."), frappe.ValidationError)
		if stored.status == "Closed" and any(self.get(field) != stored.get(field) for field in CLOSED_IMMUTABLE_FIELDS):
			frappe.throw(_("A Closed Academic Unit cannot be changed through ordinary editing."), frappe.ValidationError)
		if stored.status in {"Active", "Inactive", "Closed"} and any(
			self.get(field) != stored.get(field) for field in CAPABILITY_FIELDS
		):
			frappe.throw(
				_("Capabilities cannot change after an Academic Unit leaves Planned status."),
				frappe.ValidationError,
			)
