# Copyright (c) 2026, Talisma and contributors

import frappe


CONSTRAINT_NAME = "unique_talisma_campus_institution_code"


def execute() -> None:
	frappe.db.add_unique(
		"Talisma Campus",
		["institution", "campus_code"],
		constraint_name=CONSTRAINT_NAME,
	)
