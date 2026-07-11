# Copyright (c) 2026, Talisma and contributors

import frappe


def execute() -> None:
	frappe.db.add_unique(
		"Talisma Unit Closure",
		["closure_build", "ancestor_unit", "descendant_unit"],
		constraint_name="unique_talisma_closure_path",
	)
	frappe.db.add_index(
		"Talisma Unit Closure",
		["closure_build", "ancestor_unit", "depth", "descendant_unit"],
		index_name="idx_talisma_closure_descendants",
	)
	frappe.db.add_index(
		"Talisma Unit Closure",
		["closure_build", "descendant_unit", "depth", "ancestor_unit"],
		index_name="idx_talisma_closure_ancestors",
	)
	frappe.db.add_index(
		"Talisma Unit Closure",
		["structure_version", "closure_build"],
		index_name="idx_talisma_closure_version_build",
	)
	frappe.db.add_index(
		"Talisma Unit Closure",
		["institution", "closure_build"],
		index_name="idx_talisma_closure_institution_build",
	)
	frappe.db.add_index(
		"Talisma Closure Build",
		["structure_version", "status"],
		index_name="idx_talisma_build_version_status",
	)
