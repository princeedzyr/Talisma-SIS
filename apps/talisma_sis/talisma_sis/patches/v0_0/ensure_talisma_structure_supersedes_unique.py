# Copyright (c) 2026, Talisma and contributors

import frappe


def execute() -> None:
	if not frappe.db.sql(
		"""SELECT 1 FROM information_schema.STATISTICS
		WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tabTalisma Structure Version'
		AND COLUMN_NAME='supersedes' AND NON_UNIQUE=0 LIMIT 1"""
	):
		frappe.db.add_unique(
			"Talisma Structure Version", ["supersedes"], constraint_name="unique_talisma_structure_supersedes"
		)
