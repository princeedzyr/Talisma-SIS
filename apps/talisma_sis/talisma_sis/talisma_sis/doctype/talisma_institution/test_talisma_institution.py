# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

from uuid import UUID

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate


IGNORE_TEST_RECORD_DEPENDENCIES = ["Language", "Country", "Address"]


class TestTalismaInstitution(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_institution(self, **overrides):
		values = {
			"doctype": "Talisma Institution",
			"institution_code": "TEST_INST",
			"institution_name": "Test Institution",
			"status": "Planned",
			"valid_from": nowdate(),
			"default_timezone": "UTC",
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_uuid4_name_and_code_normalization(self):
		institution = self.make_institution(institution_code=" test-inst ").insert()

		self.assertEqual(UUID(institution.name).version, 4)
		self.assertEqual(institution.institution_code, "TEST-INST")

	def test_invalid_code_is_rejected(self):
		institution = self.make_institution(institution_code="invalid code")

		with self.assertRaises(frappe.ValidationError):
			institution.insert()

	def test_duplicate_code_is_rejected(self):
		self.make_institution().insert()

		with self.assertRaises(frappe.UniqueValidationError):
			self.make_institution(institution_name="Duplicate Institution").insert()

	def test_code_is_immutable(self):
		institution = self.make_institution().insert()
		institution.institution_code = "NEW_CODE"

		with self.assertRaises(frappe.ValidationError):
			institution.save()

	def test_invalid_date_interval_is_rejected(self):
		institution = self.make_institution(
			valid_from=getdate(nowdate()),
			valid_to=add_days(getdate(nowdate()), -1),
		)

		with self.assertRaises(frappe.ValidationError):
			institution.insert()

	def test_invalid_timezone_is_rejected(self):
		institution = self.make_institution(default_timezone="Not/A_Timezone")

		with self.assertRaises(frappe.ValidationError):
			institution.insert()

	def test_invalid_website_scheme_is_rejected(self):
		institution = self.make_institution(website="ftp://example.com")

		with self.assertRaises(frappe.ValidationError):
			institution.insert()

	def test_manager_and_viewer_permissions(self):
		institution = self.make_institution().insert()
		manager = self._make_user("institution-manager@example.com", "Talisma Institution Manager")
		viewer = self._make_user("institution-viewer@example.com", "Talisma Institution Viewer")

		self.assertTrue(frappe.has_permission(institution.doctype, "read", institution, user=manager.name))
		self.assertTrue(frappe.has_permission(institution.doctype, "write", institution, user=manager.name))
		self.assertTrue(frappe.has_permission(institution.doctype, "create", user=manager.name))
		self.assertTrue(frappe.has_permission(institution.doctype, "delete", institution, user=manager.name))

		self.assertTrue(frappe.has_permission(institution.doctype, "read", institution, user=viewer.name))
		self.assertFalse(frappe.has_permission(institution.doctype, "write", institution, user=viewer.name))
		self.assertFalse(frappe.has_permission(institution.doctype, "create", user=viewer.name))
		self.assertFalse(frappe.has_permission(institution.doctype, "delete", institution, user=viewer.name))

	def test_change_tracking_is_enabled(self):
		self.assertTrue(frappe.get_meta("Talisma Institution").track_changes)

	def test_unreferenced_institution_can_be_deleted(self):
		institution = self.make_institution().insert()

		frappe.delete_doc(institution.doctype, institution.name, ignore_permissions=True)

		self.assertFalse(frappe.db.exists(institution.doctype, institution.name))

	def _make_user(self, email: str, role: str):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Institution Test User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		user.add_roles(role)
		return user
