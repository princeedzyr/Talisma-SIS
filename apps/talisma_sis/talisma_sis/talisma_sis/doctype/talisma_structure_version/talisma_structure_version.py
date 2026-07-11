# Copyright (c) 2026, Talisma and contributors

import re
from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


STRUCTURE_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{2,32}$")
MAX_STRUCTURE_DEPTH = 32
ALLOWED_INSTITUTION_STATUSES = {"Planned", "Active"}


def validate_forest(parent_by_unit: dict[str, str | None], max_depth: int = MAX_STRUCTURE_DEPTH) -> int:
	"""Validate a parent map and return its maximum depth."""
	units = set(parent_by_unit)
	missing = {parent for parent in parent_by_unit.values() if parent and parent not in units}
	if missing:
		frappe.throw(_("Every parent Unit must have a Placement in the same Structure Version."), frappe.ValidationError)

	maximum = 0
	for start in units:
		seen: set[str] = set()
		current = start
		depth = 0
		while current:
			if current in seen:
				frappe.throw(_("The Structure contains a cycle."), frappe.ValidationError)
			seen.add(current)
			current = parent_by_unit[current]
			if current:
				depth += 1
				if depth > max_depth:
					frappe.throw(_("Structure depth cannot exceed {0}.").format(max_depth), frappe.ValidationError)
		maximum = max(maximum, depth)
	return maximum


class TalismaStructureVersion(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_validate(self) -> None:
		if self.structure_code:
			self.structure_code = self.structure_code.strip().upper()

	def validate(self) -> None:
		self._validate_code()
		self._validate_identity()
		self._validate_draft_dates()

	def before_submit(self) -> None:
		if not self.valid_to:
			frappe.throw(_("Valid To is required before submission."), frappe.ValidationError)
		if not self.approval_reference:
			frappe.throw(_("Approval Reference is required before submission."), frappe.ValidationError)

		lock_name = f"talisma:structure:{self.institution}:academic"
		acquired = frappe.db.sql("SELECT GET_LOCK(%s, 10)", (lock_name,))[0][0]
		if acquired != 1:
			frappe.throw(_("Another Structure submission is in progress for this Institution."), frappe.ValidationError)
		try:
			# This row lock remains until commit and closes the advisory-lock release window.
			frappe.db.sql(
				"SELECT name FROM `tabTalisma Institution` WHERE name=%s FOR UPDATE",
				(self.institution,),
			)
			self._validate_submission()
		finally:
			frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock_name,))

	def before_cancel(self) -> None:
		frappe.throw(_("Submitted Structure Versions cannot be cancelled; create a successor version."), frappe.ValidationError)

	def on_trash(self) -> None:
		if frappe.db.exists("Talisma Unit Placement", {"structure_version": self.name}):
			frappe.throw(_("Delete Draft Unit Placements before deleting the Structure Version."), frappe.LinkExistsError)

	def _validate_code(self) -> None:
		if not STRUCTURE_CODE_PATTERN.fullmatch(self.structure_code or ""):
			frappe.throw(
				_("Structure Code must be 2 to 32 characters using only A-Z, 0-9, hyphen or underscore."),
				frappe.ValidationError,
			)
		duplicate = frappe.db.exists(
			self.doctype,
			{
				"institution": self.institution,
				"structure_purpose": self.structure_purpose,
				"structure_code": self.structure_code,
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(_("Structure Code already exists for this Institution and purpose."), frappe.UniqueValidationError)

	def _validate_identity(self) -> None:
		if self.is_new():
			return
		stored = frappe.db.get_value(
			self.doctype, self.name, ["institution", "structure_code", "structure_purpose"], as_dict=True
		)
		for field in ("institution", "structure_code", "structure_purpose"):
			if stored and self.get(field) != stored.get(field):
				frappe.throw(_("{0} cannot change after creation.").format(self.meta.get_label(field)), frappe.ValidationError)

	def _validate_draft_dates(self) -> None:
		if self.valid_to and getdate(self.valid_to) <= getdate(self.valid_from):
			frappe.throw(_("Valid To must be later than Valid From."), frappe.ValidationError)

	def _validate_submission(self) -> None:
		self._validate_institution_interval()
		self._validate_supersedes()
		self._validate_no_overlap()
		placements = frappe.get_all(
			"Talisma Unit Placement",
			filters={"structure_version": self.name},
			fields=["institution", "academic_unit", "parent_unit"],
		)
		if not placements:
			frappe.throw(_("At least one Unit Placement is required before submission."), frappe.ValidationError)

		parent_by_unit = {row.academic_unit: row.parent_unit for row in placements}
		if len(parent_by_unit) != len(placements):
			frappe.throw(_("Each Academic Unit may appear only once in a Structure Version."), frappe.ValidationError)
		validate_forest(parent_by_unit)
		self._validate_placement_units(placements)

	def _validate_institution_interval(self) -> None:
		institution = frappe.db.get_value(
			"Talisma Institution", self.institution, ["status", "valid_from", "valid_to"], as_dict=True
		)
		if not institution or institution.status not in ALLOWED_INSTITUTION_STATUSES:
			frappe.throw(_("Submitted Structures require a Planned or Active Institution."), frappe.ValidationError)
		start, end = getdate(self.valid_from), getdate(self.valid_to)
		if start < getdate(institution.valid_from) or (institution.valid_to and end > getdate(institution.valid_to)):
			frappe.throw(_("Structure validity must fit within Institution validity."), frappe.ValidationError)

	def _validate_no_overlap(self) -> None:
		overlap = frappe.db.sql(
			"""SELECT name FROM `tabTalisma Structure Version`
			WHERE docstatus=1 AND institution=%s AND structure_purpose=%s AND name<>%s
			AND valid_from < %s AND valid_to > %s LIMIT 1""",
			(self.institution, self.structure_purpose, self.name, self.valid_to, self.valid_from),
		)
		if overlap:
			frappe.throw(_("A submitted Structure Version already overlaps this interval."), frappe.ValidationError)

	def _validate_supersedes(self) -> None:
		if not self.supersedes:
			return
		previous = frappe.db.get_value(
			self.doctype,
			self.supersedes,
			["institution", "structure_purpose", "docstatus", "valid_to"],
			as_dict=True,
		)
		if not previous or previous.docstatus != 1:
			frappe.throw(_("Supersedes must reference a submitted Structure Version."), frappe.ValidationError)
		if previous.institution != self.institution or previous.structure_purpose != self.structure_purpose:
			frappe.throw(_("Superseded Structure must have the same Institution and purpose."), frappe.ValidationError)
		if getdate(previous.valid_to) > getdate(self.valid_from):
			frappe.throw(_("A successor cannot begin before the superseded Structure ends."), frappe.ValidationError)
		fork = frappe.db.exists(self.doctype, {"supersedes": self.supersedes, "name": ["!=", self.name]})
		if fork:
			frappe.throw(_("The superseded Structure already has a successor."), frappe.ValidationError)

	def _validate_placement_units(self, placements) -> None:
		unit_names = {row.academic_unit for row in placements}
		unit_names.update(row.parent_unit for row in placements if row.parent_unit)
		units = {
			row.name: row
			for row in frappe.get_all(
				"Talisma Academic Unit",
				filters={"name": ["in", list(unit_names)]},
				fields=["name", "institution", "valid_from", "valid_to"],
			)
		}
		for placement in placements:
			if placement.institution != self.institution:
				frappe.throw(_("Every Placement must use the Structure Institution."), frappe.ValidationError)
			unit = units.get(placement.academic_unit)
			if not unit or unit.institution != self.institution:
				frappe.throw(_("Every placed Unit must belong to the Structure Institution."), frappe.ValidationError)
			if getdate(unit.valid_from) > getdate(self.valid_from):
				frappe.throw(_("Unit validity must cover the Structure interval."), frappe.ValidationError)
			if unit.valid_to and getdate(unit.valid_to) < getdate(self.valid_to):
				frappe.throw(_("Unit validity must cover the Structure interval."), frappe.ValidationError)
