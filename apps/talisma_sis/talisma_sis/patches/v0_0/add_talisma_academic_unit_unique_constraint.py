# Copyright (c) 2026, Talisma and contributors

import frappe


CONSTRAINT_NAME = "unique_talisma_academic_unit_institution_code"


def execute() -> None:
	frappe.db.add_unique(
		"Talisma Academic Unit",
		["institution", "unit_code"],
		constraint_name=CONSTRAINT_NAME,
	)
