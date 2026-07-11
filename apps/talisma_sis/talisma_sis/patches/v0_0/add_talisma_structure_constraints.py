# Copyright (c) 2026, Talisma and contributors

import frappe


def execute() -> None:
	frappe.db.add_unique(
		"Talisma Structure Version",
		["institution", "structure_purpose", "structure_code"],
		constraint_name="unique_talisma_structure_scope_code",
	)
	frappe.db.add_unique(
		"Talisma Structure Version", ["supersedes"], constraint_name="unique_talisma_structure_supersedes"
	)
	frappe.db.add_unique(
		"Talisma Unit Placement",
		["structure_version", "academic_unit"],
		constraint_name="unique_talisma_structure_unit",
	)
