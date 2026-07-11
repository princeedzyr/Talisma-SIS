# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

import re
from uuid import uuid4
from zoneinfo import available_timezones

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_url


INSTITUTION_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{2,32}$")


class TalismaInstitution(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_validate(self) -> None:
		if self.institution_code:
			self.institution_code = self.institution_code.strip().upper()

	def validate(self) -> None:
		self._validate_institution_code()
		self._validate_dates()
		self._validate_timezone()
		self._validate_website()

	def _validate_institution_code(self) -> None:
		if not INSTITUTION_CODE_PATTERN.fullmatch(self.institution_code or ""):
			frappe.throw(
				_("Institution Code must be 2 to 32 characters using only A-Z, 0-9, hyphen or underscore."),
				frappe.ValidationError,
			)

		if not self.is_new():
			stored_code = frappe.db.get_value(self.doctype, self.name, "institution_code")
			if stored_code and self.institution_code != stored_code:
				frappe.throw(_("Institution Code cannot be changed after creation."), frappe.ValidationError)

	def _validate_dates(self) -> None:
		if self.valid_to and self.valid_to < self.valid_from:
			frappe.throw(_("Valid To cannot be before Valid From."), frappe.ValidationError)

	def _validate_timezone(self) -> None:
		if self.default_timezone not in available_timezones():
			frappe.throw(_("{0} is not a valid timezone.").format(frappe.bold(self.default_timezone)))

	def _validate_website(self) -> None:
		if self.website:
			validate_url(self.website, throw=True, valid_schemes=("http", "https"))
