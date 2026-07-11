# Copyright (c) 2026, Talisma and contributors

import hashlib
from contextlib import contextmanager
from uuid import uuid4

import frappe
from frappe import _
from frappe.utils import now_datetime

from talisma_sis.talisma_sis.doctype.talisma_structure_version.talisma_structure_version import validate_forest


FINGERPRINT_SCHEMA = "talisma-closure-v1"
BATCH_SIZE = 1000


@contextmanager
def _service_context():
	previous = getattr(frappe.flags, "in_talisma_closure_service", False)
	frappe.flags.in_talisma_closure_service = True
	try:
		yield
	finally:
		frappe.flags.in_talisma_closure_service = previous


def placement_fingerprint(structure_version: str, parent_by_unit: dict[str, str | None]) -> str:
	digest = hashlib.sha256()
	digest.update(f"{FINGERPRINT_SCHEMA}\n{structure_version}\n".encode())
	for unit, parent in sorted(parent_by_unit.items()):
		digest.update(f"{unit}\t{parent or ''}\n".encode())
	return digest.hexdigest()


def calculate_closure(parent_by_unit: dict[str, str | None]) -> list[tuple[str, str, int]]:
	validate_forest(parent_by_unit)
	rows: list[tuple[str, str, int]] = []
	for descendant in sorted(parent_by_unit):
		ancestor = descendant
		depth = 0
		while ancestor:
			rows.append((ancestor, descendant, depth))
			ancestor = parent_by_unit[ancestor]
			depth += 1
	return rows


def build_closure(structure_version: str, rebuild: bool = False) -> str:
	"""Synchronously materialize one submitted Structure Version."""
	lock_name = f"talisma:closure:{structure_version}"
	acquired = frappe.db.sql("SELECT GET_LOCK(%s, 10)", (lock_name,))[0][0]
	if acquired != 1:
		frappe.throw(_("Another Closure build is in progress for this Structure Version."), frappe.ValidationError)

	try:
		structure = _lock_submitted_structure(structure_version)
		placements = _load_placements(structure_version)
		parent_by_unit = {row.academic_unit: row.parent_unit for row in placements}
		if not parent_by_unit or len(parent_by_unit) != len(placements):
			frappe.throw(_("Closure materialization requires a complete submitted Structure."), frappe.ValidationError)
		validate_forest(parent_by_unit)
		fingerprint = placement_fingerprint(structure_version, parent_by_unit)

		ready = frappe.db.get_value(
			"Talisma Closure Build",
			{"structure_version": structure_version, "status": "Ready"},
			["name", "source_fingerprint"],
			as_dict=True,
		)
		if ready and ready.source_fingerprint == fingerprint and not rebuild:
			return ready.name
		if ready and ready.source_fingerprint != fingerprint:
			frappe.throw(_("Submitted Placements no longer match the Ready Closure fingerprint."), frappe.ValidationError)

		build = _create_build(structure, len(placements), fingerprint)
		frappe.db.savepoint("talisma_closure_rows")
		try:
			rows = calculate_closure(parent_by_unit)
			_insert_rows(build.name, structure, rows)
			_verify_expected(build.name, structure.name, structure.institution, parent_by_unit, fingerprint, rows)
			if ready:
				frappe.db.set_value("Talisma Closure Build", ready.name, "status", "Superseded", update_modified=True)
			frappe.db.set_value(
				"Talisma Closure Build",
				build.name,
				{"status": "Ready", "completed_on": now_datetime(), "closure_row_count": len(rows)},
				update_modified=True,
			)
			return build.name
		except Exception as exc:
			frappe.db.rollback(save_point="talisma_closure_rows")
			_mark_failed(build.name, exc)
			raise
	finally:
		frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock_name,))


def get_ready_build(structure_version: str) -> str:
	build = frappe.db.get_value(
		"Talisma Closure Build", {"structure_version": structure_version, "status": "Ready"}, "name"
	)
	if not build:
		frappe.throw(_("No Ready Closure build exists for this Structure Version."), frappe.ValidationError)
	return build


def get_descendants(build: str, ancestor_unit: str, include_self: bool = True) -> list[str]:
	_validate_query_build(build)
	filters = {"closure_build": build, "ancestor_unit": ancestor_unit}
	if not include_self:
		filters["depth"] = [">", 0]
	return frappe.get_all(
		"Talisma Unit Closure", filters=filters, pluck="descendant_unit", order_by="depth asc, descendant_unit asc"
	)


def get_ancestors(build: str, descendant_unit: str, include_self: bool = True) -> list[str]:
	_validate_query_build(build)
	filters = {"closure_build": build, "descendant_unit": descendant_unit}
	if not include_self:
		filters["depth"] = [">", 0]
	return frappe.get_all(
		"Talisma Unit Closure", filters=filters, pluck="ancestor_unit", order_by="depth asc, ancestor_unit asc"
	)


def verify_build(build: str) -> bool:
	record = _validate_query_build(build)
	placements = _load_placements(record.structure_version)
	parent_by_unit = {row.academic_unit: row.parent_unit for row in placements}
	expected = calculate_closure(parent_by_unit)
	fingerprint = placement_fingerprint(record.structure_version, parent_by_unit)
	_verify_expected(build, record.structure_version, record.institution, parent_by_unit, fingerprint, expected)
	return True


def _lock_submitted_structure(structure_version: str):
	rows = frappe.db.sql(
		"""SELECT name, institution, docstatus FROM `tabTalisma Structure Version`
		WHERE name=%s FOR UPDATE""",
		(structure_version,),
		as_dict=True,
	)
	if not rows or rows[0].docstatus != 1:
		frappe.throw(_("Closure materialization requires a submitted Structure Version."), frappe.ValidationError)
	return rows[0]


def _load_placements(structure_version: str):
	return frappe.get_all(
		"Talisma Unit Placement",
		filters={"structure_version": structure_version},
		fields=["institution", "academic_unit", "parent_unit"],
		order_by="academic_unit asc",
	)


def _create_build(structure, expected_count: int, fingerprint: str):
	with _service_context():
		return frappe.get_doc(
			{
				"doctype": "Talisma Closure Build",
				"structure_version": structure.name,
				"institution": structure.institution,
				"status": "Building",
				"started_on": now_datetime(),
				"expected_unit_count": expected_count,
				"source_fingerprint": fingerprint,
			}
		).insert(ignore_permissions=True)


def _insert_rows(build: str, structure, rows: list[tuple[str, str, int]]) -> None:
	values = [
		(
			str(uuid4()), now_datetime(), now_datetime(), "Administrator", "Administrator", 0, index,
			build, structure.name, structure.institution, ancestor, descendant, depth,
		)
		for index, (ancestor, descendant, depth) in enumerate(rows, start=1)
	]
	for offset in range(0, len(values), BATCH_SIZE):
		frappe.db.bulk_insert(
			"Talisma Unit Closure",
			fields=[
				"name", "creation", "modified", "owner", "modified_by", "docstatus", "idx",
				"closure_build", "structure_version", "institution", "ancestor_unit", "descendant_unit", "depth",
			],
			values=values[offset : offset + BATCH_SIZE],
		)


def _verify_expected(
	build: str,
	structure_version: str,
	institution: str,
	parent_by_unit,
	fingerprint: str,
	expected_rows,
) -> None:
	fresh_placements = _load_placements(structure_version)
	fresh_parent_by_unit = {row.academic_unit: row.parent_unit for row in fresh_placements}
	if fresh_parent_by_unit != parent_by_unit or placement_fingerprint(structure_version, fresh_parent_by_unit) != fingerprint:
		frappe.throw(_("Closure source fingerprint changed during materialization."), frappe.ValidationError)
	stored = frappe.get_all(
			"Talisma Unit Closure",
			filters={"closure_build": build},
			fields=["structure_version", "institution", "ancestor_unit", "descendant_unit", "depth"],
		)
	if any(row.structure_version != structure_version or row.institution != institution for row in stored):
		frappe.throw(_("Closure scope verification failed."), frappe.ValidationError)
	actual = {
		(row.ancestor_unit, row.descendant_unit, row.depth)
		for row in stored
	}
	if actual != set(expected_rows):
		frappe.throw(_("Closure integrity verification failed."), frappe.ValidationError)
	if len({descendant for ancestor, descendant, depth in actual if ancestor == descendant and depth == 0}) != len(parent_by_unit):
		frappe.throw(_("Closure self-row verification failed."), frappe.ValidationError)
	if any(depth < 0 or (ancestor != descendant and depth == 0) for ancestor, descendant, depth in actual):
		frappe.throw(_("Closure depth verification failed."), frappe.ValidationError)


def _validate_query_build(build: str):
	record = frappe.db.get_value(
		"Talisma Closure Build", build, ["name", "structure_version", "institution", "status", "source_fingerprint"], as_dict=True
	)
	if not record or record.status != "Ready":
		frappe.throw(_("Closure queries require a Ready build."), frappe.ValidationError)
	structure_institution = frappe.db.get_value("Talisma Structure Version", record.structure_version, "institution")
	if structure_institution != record.institution:
		frappe.throw(_("Closure build Institution does not match its Structure Version."), frappe.ValidationError)
	return record


def _mark_failed(build: str, exc: Exception) -> None:
	code = exc.__class__.__name__[:140]
	summary = _("Closure generation failed during {0}.").format(code)
	frappe.db.set_value(
		"Talisma Closure Build",
		build,
		{"status": "Failed", "completed_on": now_datetime(), "failure_code": code, "failure_summary": summary},
		update_modified=True,
	)
