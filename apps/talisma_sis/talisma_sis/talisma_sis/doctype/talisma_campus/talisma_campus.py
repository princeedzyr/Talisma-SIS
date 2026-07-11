# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

import re
from uuid import uuid4
from zoneinfo import available_timezones

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, validate_url


CAMPUS_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{2,32}$")
ALLOWED_INSTITUTION_STATUSES = {"Planned", "Active"}


class TalismaCampus(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_validate(self) -> None:
		if self.campus_code:
			self.campus_code = self.campus_code.strip().upper()

		if self.institution and not self.timezone:
			self.timezone = frappe.db.get_value("Talisma Institution", self.institution, "default_timezone")

	def validate(self) -> None:
		self._validate_code()
		self._validate_immutable_fields()
		self._validate_institution_and_dates()
		self._validate_location()
		self._validate_website()
		self._validate_closed_status()

	def _validate_code(self) -> None:
		if not CAMPUS_CODE_PATTERN.fullmatch(self.campus_code or ""):
			frappe.throw(
				_("Campus Code must be 2 to 32 characters using only A-Z, 0-9, hyphen or underscore."),
				frappe.ValidationError,
			)

		duplicate = frappe.db.exists(
			self.doctype,
			{"institution": self.institution, "campus_code": self.campus_code, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(
				_("Campus Code {0} already exists for this Institution.").format(frappe.bold(self.campus_code)),
				frappe.UniqueValidationError,
			)

	def _validate_immutable_fields(self) -> None:
		if self.is_new():
			return

		stored = frappe.db.get_value(self.doctype, self.name, ["institution", "campus_code"], as_dict=True)
		if stored and self.institution != stored.institution:
			frappe.throw(_("Institution cannot be changed after creation."), frappe.ValidationError)
		if stored and self.campus_code != stored.campus_code:
			frappe.throw(_("Campus Code cannot be changed after creation."), frappe.ValidationError)

	def _validate_institution_and_dates(self) -> None:
		institution = frappe.db.get_value(
			"Talisma Institution",
			self.institution,
			["status", "valid_from", "valid_to"],
			as_dict=True,
		)
		if not institution:
			frappe.throw(_("Institution does not exist."), frappe.ValidationError)

		if self.is_new() and institution.status not in ALLOWED_INSTITUTION_STATUSES:
			frappe.throw(
				_("New Campuses can only be created for Planned or Active Institutions."),
				frappe.ValidationError,
			)

		valid_from = getdate(self.valid_from)
		valid_to = getdate(self.valid_to) if self.valid_to else None
		institution_from = getdate(institution.valid_from)
		institution_to = getdate(institution.valid_to) if institution.valid_to else None

		if valid_to and valid_to < valid_from:
			frappe.throw(_("Valid To cannot be before Valid From."), frappe.ValidationError)
		if valid_from < institution_from:
			frappe.throw(_("Campus validity cannot begin before Institution validity."), frappe.ValidationError)
		if institution_to and (not valid_to or valid_to > institution_to):
			frappe.throw(_("Campus validity cannot extend beyond Institution validity."), frappe.ValidationError)

	def _validate_location(self) -> None:
		if self.timezone not in available_timezones():
			frappe.throw(_("{0} is not a valid timezone.").format(frappe.bold(self.timezone)))
		if self.campus_type != "Virtual" and not self.address:
			frappe.throw(_("Address is required for a non-Virtual Campus."), frappe.ValidationError)

	def _validate_website(self) -> None:
		if self.website:
			validate_url(self.website, throw=True, valid_schemes=("http", "https"))

	def _validate_closed_status(self) -> None:
		if self.is_new():
			return
		stored_status = frappe.db.get_value(self.doctype, self.name, "status")
		if stored_status == "Closed" and self.status != "Closed":
			frappe.throw(_("A Closed Campus cannot be reopened through ordinary editing."), frappe.ValidationError)
