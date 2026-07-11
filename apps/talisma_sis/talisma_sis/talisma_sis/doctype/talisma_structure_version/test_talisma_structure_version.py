# Copyright (c) 2026, Talisma and contributors

from uuid import UUID, uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from talisma_sis.talisma_sis.doctype.talisma_structure_version.talisma_structure_version import (
	MAX_STRUCTURE_DEPTH,
	validate_forest,
)


class TestTalismaStructureVersion(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_institution(self, **overrides):
		suffix = uuid4().hex[:8].upper()
		values = {
			"doctype": "Talisma Institution",
			"institution_code": f"INST_{suffix}",
			"institution_name": f"Institution {suffix}",
			"status": "Active",
			"valid_from": add_days(getdate(nowdate()), -30),
			"valid_to": add_days(getdate(nowdate()), 365),
			"default_timezone": "UTC",
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def make_type(self):
		suffix = uuid4().hex[:8].upper()
		return frappe.get_doc(
			{
				"doctype": "Talisma Academic Unit Type",
				"type_code": f"TYPE_{suffix}",
				"type_name": f"Type {suffix}",
			}
		).insert()

	def make_unit(self, institution, unit_type=None, **overrides):
		suffix = uuid4().hex[:8].upper()
		values = {
			"doctype": "Talisma Academic Unit",
			"institution": institution.name,
			"unit_code": f"UNIT_{suffix}",
			"unit_name": f"Unit {suffix}",
			"unit_type": (unit_type or self.make_type()).name,
			"status": "Active",
			"valid_from": institution.valid_from,
			"valid_to": institution.valid_to,
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def make_structure(self, institution, **overrides):
		suffix = uuid4().hex[:8].upper()
		values = {
			"doctype": "Talisma Structure Version",
			"institution": institution.name,
			"structure_code": f"STR_{suffix}",
			"structure_name": f"Structure {suffix}",
			"structure_purpose": "Academic Governance",
			"valid_from": nowdate(),
			"valid_to": add_days(getdate(nowdate()), 30),
			"change_summary": "Initial governed structure",
			"approval_reference": "TEST-APPROVAL",
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def place(self, structure, unit, parent=None, **overrides):
		values = {
			"doctype": "Talisma Unit Placement",
			"structure_version": structure.name,
			"academic_unit": unit.name,
			"parent_unit": parent.name if parent else None,
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def test_uuid_normalization_and_scoped_code_uniqueness(self):
		institution = self.make_institution()
		structure = self.make_structure(institution, structure_code=" structure-1 ").insert()
		self.assertEqual(UUID(structure.name).version, 4)
		self.assertEqual(structure.structure_code, "STRUCTURE-1")
		with self.assertRaises(frappe.UniqueValidationError):
			self.make_structure(institution, structure_code="structure-1").insert()

	def test_database_constraints_exist(self):
		constraints = {
			row[0]
			for row in frappe.db.sql(
				"""SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
				WHERE TABLE_SCHEMA=DATABASE() AND CONSTRAINT_NAME LIKE 'unique_talisma_structure%'"""
			)
		}
		self.assertEqual(
			constraints,
			{
				"unique_talisma_structure_scope_code",
				"unique_talisma_structure_supersedes",
				"unique_talisma_structure_unit",
			},
		)

	def test_valid_to_is_optional_in_draft_but_required_for_submit(self):
		institution = self.make_institution()
		structure = self.make_structure(institution, valid_to=None).insert()
		unit = self.make_unit(institution)
		self.place(structure, unit)
		with self.assertRaises(frappe.ValidationError):
			structure.submit()

	def test_valid_forest_submits_and_becomes_immutable(self):
		institution = self.make_institution()
		unit_type = self.make_type()
		root = self.make_unit(institution, unit_type)
		child = self.make_unit(institution, unit_type)
		second_root = self.make_unit(institution, unit_type)
		structure = self.make_structure(institution).insert()
		self.place(structure, root)
		child_placement = self.place(structure, child, root)
		self.place(structure, second_root)
		structure.submit()
		self.assertEqual(structure.docstatus, 1)
		child_placement.display_order = 2
		with self.assertRaises(frappe.ValidationError):
			child_placement.save()
		with self.assertRaises(frappe.ValidationError):
			structure.cancel()

	def test_empty_missing_parent_cycle_and_depth_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			validate_forest({"child": "missing"})
		with self.assertRaises(frappe.ValidationError):
			validate_forest({"one": "two", "two": "one"})
		chain = {"root": None}
		for depth in range(1, MAX_STRUCTURE_DEPTH + 1):
			chain[f"unit-{depth}"] = "root" if depth == 1 else f"unit-{depth - 1}"
		self.assertEqual(validate_forest(chain), MAX_STRUCTURE_DEPTH)
		chain[f"unit-{MAX_STRUCTURE_DEPTH + 1}"] = f"unit-{MAX_STRUCTURE_DEPTH}"
		with self.assertRaises(frappe.ValidationError):
			validate_forest(chain)
		institution = self.make_institution()
		with self.assertRaises(frappe.ValidationError):
			self.make_structure(institution).insert().submit()

	def test_overlapping_interval_rejected_and_adjacent_successor_allowed(self):
		institution = self.make_institution()
		unit_type = self.make_type()
		unit = self.make_unit(institution, unit_type)
		first = self.make_structure(institution, valid_from=nowdate(), valid_to=add_days(nowdate(), 10)).insert()
		self.place(first, unit)
		first.submit()
		overlap = self.make_structure(
			institution, valid_from=add_days(nowdate(), 9), valid_to=add_days(nowdate(), 20)
		).insert()
		self.place(overlap, unit)
		with self.assertRaises(frappe.ValidationError):
			overlap.submit()
		adjacent = self.make_structure(
			institution,
			valid_from=first.valid_to,
			valid_to=add_days(first.valid_to, 10),
			supersedes=first.name,
		).insert()
		self.place(adjacent, unit)
		adjacent.submit()
		self.assertEqual(adjacent.docstatus, 1)

	def test_placement_derives_institution_and_rejects_invalid_links(self):
		institution = self.make_institution()
		other = self.make_institution()
		unit = self.make_unit(institution)
		other_unit = self.make_unit(other)
		structure = self.make_structure(institution).insert()
		placement = self.place(structure, unit)
		self.assertEqual(UUID(placement.name).version, 4)
		self.assertEqual(placement.institution, institution.name)
		with self.assertRaises(frappe.ValidationError):
			self.place(structure, unit, unit)
		with self.assertRaises(frappe.ValidationError):
			self.place(structure, other_unit)
		with self.assertRaises(frappe.ValidationError):
			self.place(structure, self.make_unit(institution), display_order=-1)

	def test_permissions_and_excluded_scope(self):
		institution = self.make_institution()
		structure = self.make_structure(institution).insert()
		manager = self.make_user("structure-manager@example.com", "Talisma Institution Manager")
		viewer = self.make_user("structure-viewer@example.com", "Talisma Institution Viewer")
		approver = self.make_user("structure-approver@example.com", "Talisma Academic Structure Approver")
		self.assertTrue(frappe.has_permission(structure.doctype, "write", structure, user=manager.name))
		self.assertFalse(frappe.has_permission(structure.doctype, "submit", structure, user=manager.name))
		self.assertTrue(frappe.has_permission(structure.doctype, "read", structure, user=viewer.name))
		self.assertFalse(frappe.has_permission(structure.doctype, "write", structure, user=viewer.name))
		self.assertTrue(frappe.has_permission(structure.doctype, "submit", structure, user=approver.name))
		meta = frappe.get_meta(structure.doctype)
		for fieldname in ("is_active", "activation_status", "closure", "scope_grant"):
			self.assertFalse(meta.has_field(fieldname))
		self.assertFalse(frappe.db.exists("DocType", "Talisma Structure Closure"))

	def make_user(self, email, role):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Structure Test User", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles(role)
		return user
