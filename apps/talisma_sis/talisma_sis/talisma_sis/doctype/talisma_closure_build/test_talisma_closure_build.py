# Copyright (c) 2026, Talisma and contributors

from time import perf_counter
from unittest.mock import patch
from uuid import UUID, uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from talisma_sis.closure import (
	build_closure,
	calculate_closure,
	get_ancestors,
	get_descendants,
	get_ready_build,
	placement_fingerprint,
	verify_build,
)


class TestTalismaClosureBuild(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.flags.in_talisma_closure_service = False
		frappe.db.rollback()

	def make_institution(self):
		suffix = uuid4().hex[:8].upper()
		return frappe.get_doc(
			{
				"doctype": "Talisma Institution",
				"institution_code": f"INST_{suffix}",
				"institution_name": f"Institution {suffix}",
				"status": "Active",
				"valid_from": add_days(getdate(nowdate()), -30),
				"valid_to": add_days(getdate(nowdate()), 365),
				"default_timezone": "UTC",
			}
		).insert()

	def make_type(self):
		suffix = uuid4().hex[:8].upper()
		return frappe.get_doc(
			{
				"doctype": "Talisma Academic Unit Type",
				"type_code": f"TYPE_{suffix}",
				"type_name": f"Type {suffix}",
			}
		).insert()

	def make_unit(self, institution, unit_type):
		suffix = uuid4().hex[:8].upper()
		return frappe.get_doc(
			{
				"doctype": "Talisma Academic Unit",
				"institution": institution.name,
				"unit_code": f"UNIT_{suffix}",
				"unit_name": f"Unit {suffix}",
				"unit_type": unit_type.name,
				"status": "Active",
				"valid_from": institution.valid_from,
				"valid_to": institution.valid_to,
			}
		).insert()

	def make_submitted_structure(self, parent_indexes=(None, 0, 1, None)):
		institution = self.make_institution()
		unit_type = self.make_type()
		units = [self.make_unit(institution, unit_type) for _ in parent_indexes]
		suffix = uuid4().hex[:8].upper()
		structure = frappe.get_doc(
			{
				"doctype": "Talisma Structure Version",
				"institution": institution.name,
				"structure_code": f"STR_{suffix}",
				"structure_name": f"Structure {suffix}",
				"structure_purpose": "Academic Governance",
				"valid_from": nowdate(),
				"valid_to": add_days(getdate(nowdate()), 30),
				"change_summary": "Closure test structure",
				"approval_reference": "TEST-B4",
			}
		).insert()
		for index, parent_index in enumerate(parent_indexes):
			frappe.get_doc(
				{
					"doctype": "Talisma Unit Placement",
					"structure_version": structure.name,
					"academic_unit": units[index].name,
					"parent_unit": units[parent_index].name if parent_index is not None else None,
				}
			).insert()
		structure.submit()
		return structure, units

	def test_calculation_fingerprint_and_scale_boundary(self):
		forest = {"root": None, "child": "root", "grandchild": "child", "other-root": None}
		self.assertEqual(
			set(calculate_closure(forest)),
			{
				("root", "root", 0),
				("child", "child", 0),
				("root", "child", 1),
				("grandchild", "grandchild", 0),
				("child", "grandchild", 1),
				("root", "grandchild", 2),
				("other-root", "other-root", 0),
			},
		)
		self.assertEqual(
			placement_fingerprint("version", forest),
			placement_fingerprint("version", dict(reversed(list(forest.items())))),
		)
		wide = {"root": None} | {f"unit-{index}": "root" for index in range(9999)}
		started = perf_counter()
		rows = calculate_closure(wide)
		self.assertEqual(len(rows), 19999)
		self.assertLess(perf_counter() - started, 5)

	def test_build_query_idempotency_and_rebuild(self):
		structure, units = self.make_submitted_structure()
		build = build_closure(structure.name)
		self.assertEqual(UUID(build).version, 4)
		self.assertEqual(get_ready_build(structure.name), build)
		self.assertTrue(verify_build(build))
		self.assertEqual(build_closure(structure.name), build)
		self.assertEqual(get_descendants(build, units[0].name), [units[0].name, units[1].name, units[2].name])
		self.assertEqual(get_ancestors(build, units[2].name), [units[2].name, units[1].name, units[0].name])
		self.assertEqual(get_descendants(build, units[0].name, include_self=False), [units[1].name, units[2].name])

		replacement = build_closure(structure.name, rebuild=True)
		self.assertNotEqual(replacement, build)
		self.assertEqual(frappe.db.get_value("Talisma Closure Build", build, "status"), "Superseded")
		self.assertEqual(get_ready_build(structure.name), replacement)
		with self.assertRaises(frappe.ValidationError):
			get_descendants(build, units[0].name)

	def test_draft_and_direct_mutation_are_rejected(self):
		institution = self.make_institution()
		suffix = uuid4().hex[:8].upper()
		draft = frappe.get_doc(
			{
				"doctype": "Talisma Structure Version",
				"institution": institution.name,
				"structure_code": f"STR_{suffix}",
				"structure_name": "Draft Structure",
				"structure_purpose": "Academic Governance",
				"valid_from": nowdate(),
				"valid_to": add_days(getdate(nowdate()), 30),
				"change_summary": "Draft",
			}
		).insert()
		with self.assertRaises(frappe.ValidationError):
			build_closure(draft.name)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Talisma Closure Build",
					"structure_version": draft.name,
					"institution": institution.name,
					"status": "Building",
					"started_on": nowdate(),
					"expected_unit_count": 1,
					"source_fingerprint": "0" * 64,
				}
			).insert(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Talisma Unit Closure",
					"closure_build": str(uuid4()),
					"structure_version": draft.name,
					"institution": institution.name,
					"ancestor_unit": str(uuid4()),
					"descendant_unit": str(uuid4()),
					"depth": 0,
				}
			).insert(ignore_permissions=True, ignore_links=True)

	def test_lock_contention_fails_closed_without_creating_build(self):
		structure, _units = self.make_submitted_structure()
		original_sql = frappe.db.sql

		def contend(query, *args, **kwargs):
			if "GET_LOCK" in query:
				return ((0,),)
			return original_sql(query, *args, **kwargs)

		with patch.object(frappe.db, "sql", side_effect=contend):
			with self.assertRaises(frappe.ValidationError):
				build_closure(structure.name)
		self.assertFalse(frappe.db.exists("Talisma Closure Build", {"structure_version": structure.name}))

	def test_failed_build_retains_evidence_without_rows(self):
		structure, _units = self.make_submitted_structure()
		with patch("talisma_sis.closure._insert_rows", side_effect=RuntimeError("controlled failure")):
			with self.assertRaises(RuntimeError):
				build_closure(structure.name)
		build = frappe.db.get_value(
			"Talisma Closure Build", {"structure_version": structure.name}, ["name", "status", "failure_code"], as_dict=True
		)
		self.assertEqual(build.status, "Failed")
		self.assertEqual(build.failure_code, "RuntimeError")
		self.assertFalse(frappe.db.exists("Talisma Unit Closure", {"closure_build": build.name}))
		with self.assertRaises(frappe.ValidationError):
			get_ready_build(structure.name)

	def test_constraints_indexes_permissions_and_exclusions(self):
		indexes = {
			row[0]
			for row in frappe.db.sql(
				"""SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS
				WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN
				('tabTalisma Closure Build', 'tabTalisma Unit Closure')"""
			)
		}
		self.assertTrue(
			{
				"unique_talisma_closure_path",
				"idx_talisma_closure_descendants",
				"idx_talisma_closure_ancestors",
				"idx_talisma_closure_version_build",
				"idx_talisma_closure_institution_build",
				"idx_talisma_build_version_status",
			}.issubset(indexes)
		)
		for doctype in ("Talisma Closure Build", "Talisma Unit Closure"):
			meta = frappe.get_meta(doctype)
			self.assertFalse(meta.allow_import)
			self.assertFalse(meta.allow_rename)
			self.assertFalse(meta.is_submittable)
			for role in ("Talisma Institution Manager", "Talisma Institution Viewer", "Talisma Academic Structure Approver"):
				self.assertFalse(any(permission.role == role for permission in meta.permissions))
			for fieldname in ("is_active", "activation_status", "scope_grant", "cache_key"):
				self.assertFalse(meta.has_field(fieldname))
