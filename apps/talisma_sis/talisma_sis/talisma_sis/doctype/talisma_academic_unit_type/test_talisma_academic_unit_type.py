# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

from uuid import UUID, uuid4

import frappe
from frappe.tests import IntegrationTestCase


class TestTalismaAcademicUnitType(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_type(self, **overrides):
		suffix = uuid4().hex[:8].upper()
		values = {
			"doctype": "Talisma Academic Unit Type",
			"type_code": f"TYPE_{suffix}",
			"type_name": f"Test Type {suffix}",
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_uuid_code_normalization_and_global_uniqueness(self):
		unit_type = self.make_type(type_code=" college ").insert()
		self.assertEqual(UUID(unit_type.name).version, 4)
		self.assertEqual(unit_type.type_code, "COLLEGE")
		with self.assertRaises(frappe.UniqueValidationError):
			self.make_type(type_code="college").insert()

	def test_invalid_and_changed_code_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_type(type_code="bad code").insert()
		unit_type = self.make_type().insert()
		unit_type.type_code = "NEW_CODE"
		with self.assertRaises(frappe.ValidationError):
			unit_type.save()

	def test_referenced_type_configuration_is_immutable_but_can_be_disabled(self):
		unit_type = self.make_type(can_own_programs=1).insert()
		institution = self.make_institution()
		frappe.get_doc(
			{
				"doctype": "Talisma Academic Unit",
				"institution": institution.name,
				"unit_code": "UNIT",
				"unit_name": "Unit",
				"unit_type": unit_type.name,
				"valid_from": institution.valid_from,
			}
		).insert()

		unit_type.type_name = "Changed"
		with self.assertRaises(frappe.ValidationError):
			unit_type.save()
		unit_type.reload()
		unit_type.disabled = 1
		unit_type.save()

	def test_permissions_match_accepted_roles(self):
		manager = self.make_user("unit-type-manager@example.com", "Talisma Institution Manager")
		viewer = self.make_user("unit-type-viewer@example.com", "Talisma Institution Viewer")
		self.assertTrue(frappe.has_permission("Talisma Academic Unit Type", "read", user=manager.name))
		self.assertFalse(frappe.has_permission("Talisma Academic Unit Type", "create", user=manager.name))
		self.assertTrue(frappe.has_permission("Talisma Academic Unit Type", "read", user=viewer.name))
		self.assertFalse(frappe.has_permission("Talisma Academic Unit Type", "write", user=viewer.name))
		self.assertTrue(frappe.get_meta("Talisma Academic Unit Type").track_changes)

	def test_unreferenced_type_can_be_deleted(self):
		unit_type = self.make_type().insert()
		frappe.delete_doc(unit_type.doctype, unit_type.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists(unit_type.doctype, unit_type.name))

	def make_institution(self):
		suffix = uuid4().hex[:8].upper()
		return frappe.get_doc(
			{
				"doctype": "Talisma Institution",
				"institution_code": f"INST_{suffix}",
				"institution_name": f"Institution {suffix}",
				"status": "Active",
				"valid_from": frappe.utils.nowdate(),
				"default_timezone": "UTC",
			}
		).insert()

	def make_user(self, email: str, role: str):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Unit Type User", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles(role)
		return user
