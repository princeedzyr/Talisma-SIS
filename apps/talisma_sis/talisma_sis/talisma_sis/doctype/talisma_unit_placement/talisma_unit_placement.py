# Copyright (c) 2026, Talisma and contributors

from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document


class TalismaUnitPlacement(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_validate(self) -> None:
		if not self.structure_version:
			return
		structure = frappe.db.get_value(
			"Talisma Structure Version", self.structure_version, ["institution", "docstatus"], as_dict=True
		)
		if not structure:
			frappe.throw(_("Structure Version does not exist."), frappe.ValidationError)
		if self.institution and self.institution != structure.institution:
			frappe.throw(_("Placement Institution must match the Structure Version."), frappe.ValidationError)
		self.institution = structure.institution

	def validate(self) -> None:
		self._validate_draft_structure()
		self._validate_unit_links()
		self._validate_immutable_links()
		if self.display_order is not None and self.display_order < 0:
			frappe.throw(_("Display Order cannot be negative."), frappe.ValidationError)

	def on_trash(self) -> None:
		self._validate_draft_structure()

	def _validate_draft_structure(self) -> None:
		docstatus = frappe.db.get_value("Talisma Structure Version", self.structure_version, "docstatus")
		if docstatus != 0:
			frappe.throw(_("Placements can change only while the Structure Version is Draft."), frappe.ValidationError)

	def _validate_unit_links(self) -> None:
		if self.academic_unit == self.parent_unit:
			frappe.throw(_("An Academic Unit cannot be its own parent."), frappe.ValidationError)
		for field in ("academic_unit", "parent_unit"):
			unit_name = self.get(field)
			if not unit_name:
				continue
			institution = frappe.db.get_value("Talisma Academic Unit", unit_name, "institution")
			if not institution or institution != self.institution:
				frappe.throw(_("Placed Units must belong to the Structure Institution."), frappe.ValidationError)

	def _validate_immutable_links(self) -> None:
		if self.is_new():
			return
		stored = frappe.db.get_value(
			self.doctype,
			self.name,
			["structure_version", "institution", "academic_unit", "parent_unit"],
			as_dict=True,
		)
		for field in ("structure_version", "institution", "academic_unit", "parent_unit"):
			if stored and self.get(field) != stored.get(field):
				frappe.throw(_("{0} cannot change after Placement creation.").format(self.meta.get_label(field)), frappe.ValidationError)
