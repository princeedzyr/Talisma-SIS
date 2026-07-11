# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

from uuid import UUID, uuid4

import frappe
from MySQLdb import IntegrityError
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from talisma_sis.patches.v0_0.add_talisma_campus_unique_constraint import CONSTRAINT_NAME


IGNORE_TEST_RECORD_DEPENDENCIES = ["Address"]


class TestTalismaCampus(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_institution(self, **overrides):
		suffix = uuid4().hex[:8].upper()
		values = {
			"doctype": "Talisma Institution",
			"institution_code": f"INST_{suffix}",
			"institution_name": f"Test Institution {suffix}",
			"status": "Active",
			"valid_from": nowdate(),
			"default_timezone": "UTC",
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def make_campus(self, institution=None, **overrides):
		institution = institution or self.make_institution()
		values = {
			"doctype": "Talisma Campus",
			"institution": institution.name,
			"campus_code": "TEST_CAMPUS",
			"campus_name": "Test Campus",
			"campus_type": "Virtual",
			"status": "Planned",
			"valid_from": institution.valid_from,
			"timezone": "UTC",
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def make_address(self):
		country = frappe.db.get_value("Country", {}, "name")
		return frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "Campus Test Address",
				"address_type": "Office",
				"address_line1": "1 Test Street",
				"city": "Test City",
				"country": country,
			}
		).insert(ignore_permissions=True)

	def test_uuid4_code_normalization_and_timezone_default(self):
		institution = self.make_institution(default_timezone="Asia/Kolkata")
		campus = self.make_campus(
			institution,
			campus_code=" test-campus ",
			timezone=None,
		).insert()

		self.assertEqual(UUID(campus.name).version, 4)
		self.assertEqual(campus.campus_code, "TEST-CAMPUS")
		self.assertEqual(campus.timezone, "Asia/Kolkata")

	def test_invalid_code_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_campus(campus_code="invalid code").insert()

	def test_code_is_unique_within_institution(self):
		institution = self.make_institution()
		self.make_campus(institution).insert()

		with self.assertRaises(frappe.UniqueValidationError):
			self.make_campus(institution, campus_name="Duplicate Campus").insert()

	def test_same_code_is_allowed_in_different_institutions(self):
		first = self.make_campus(self.make_institution()).insert()
		second = self.make_campus(self.make_institution()).insert()

		self.assertNotEqual(first.institution, second.institution)
		self.assertEqual(first.campus_code, second.campus_code)

	def test_database_constraint_blocks_validation_bypass(self):
		campus = self.make_campus().insert()
		duplicate_name = str(uuid4())

		with self.assertRaises(IntegrityError):
			frappe.db.sql(
				"""INSERT INTO `tabTalisma Campus`
					(name, creation, modified, owner, modified_by, docstatus, idx,
					 institution, campus_code, campus_name, campus_type, status, valid_from, timezone)
				VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, 0,
					%s, %s, 'Constraint Bypass', 'Virtual', 'Planned', %s, 'UTC')""",
				(duplicate_name, campus.institution, campus.campus_code, campus.valid_from),
			)

	def test_composite_unique_constraint_exists(self):
		constraint = frappe.db.sql(
			"""SELECT CONSTRAINT_NAME
			FROM information_schema.TABLE_CONSTRAINTS
			WHERE TABLE_SCHEMA = DATABASE()
				AND TABLE_NAME = 'tabTalisma Campus'
				AND CONSTRAINT_TYPE = 'UNIQUE'
				AND CONSTRAINT_NAME = %s""",
			(CONSTRAINT_NAME,),
		)

		self.assertTrue(constraint)

	def test_institution_and_code_are_immutable(self):
		campus = self.make_campus().insert()
		campus.institution = self.make_institution().name

		with self.assertRaises(frappe.ValidationError):
			campus.save()

		campus.reload()
		campus.campus_code = "NEW_CODE"
		with self.assertRaises(frappe.ValidationError):
			campus.save()

	def test_campus_interval_must_be_valid(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_campus(valid_to=add_days(getdate(nowdate()), -1)).insert()

	def test_campus_interval_must_fit_institution(self):
		institution = self.make_institution(
			valid_from=add_days(getdate(nowdate()), -5),
			valid_to=add_days(getdate(nowdate()), 5),
		)

		with self.assertRaises(frappe.ValidationError):
			self.make_campus(institution, valid_from=add_days(institution.valid_from, -1)).insert()

		with self.assertRaises(frappe.ValidationError):
			self.make_campus(institution, valid_to=None).insert()

	def test_new_campus_rejects_inactive_or_closed_institution(self):
		for status in ("Inactive", "Closed"):
			institution = self.make_institution(status=status)
			with self.subTest(status=status), self.assertRaises(frappe.ValidationError):
				self.make_campus(institution).insert()

	def test_physical_types_require_address_and_virtual_does_not(self):
		institution = self.make_institution()
		for campus_type in ("Main", "Satellite", "Learning Center", "Other"):
			with self.subTest(campus_type=campus_type), self.assertRaises(frappe.ValidationError):
				self.make_campus(institution, campus_type=campus_type).insert()

		self.make_campus(institution, campus_type="Virtual").insert()

	def test_physical_campus_accepts_standard_address(self):
		campus = self.make_campus(campus_type="Main", address=self.make_address().name).insert()

		self.assertTrue(campus.name)

	def test_invalid_timezone_and_website_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_campus(timezone="Not/A_Timezone").insert()

		with self.assertRaises(frappe.ValidationError):
			self.make_campus(website="ftp://example.com").insert()

	def test_closed_campus_cannot_be_reopened(self):
		campus = self.make_campus(status="Closed").insert()
		campus.status = "Active"

		with self.assertRaises(frappe.ValidationError):
			campus.save()

	def test_permissions_match_accepted_roles(self):
		campus = self.make_campus().insert()
		manager = self.make_user("campus-manager@example.com", "Talisma Institution Manager")
		viewer = self.make_user("campus-viewer@example.com", "Talisma Institution Viewer")
		unauthorized = self.make_user("campus-unauthorized@example.com")

		self.assertTrue(frappe.has_permission(campus.doctype, "read", campus, user=manager.name))
		self.assertTrue(frappe.has_permission(campus.doctype, "write", campus, user=manager.name))
		self.assertTrue(frappe.has_permission(campus.doctype, "create", user=manager.name))
		self.assertTrue(frappe.has_permission(campus.doctype, "delete", campus, user=manager.name))

		self.assertTrue(frappe.has_permission(campus.doctype, "read", campus, user=viewer.name))
		self.assertFalse(frappe.has_permission(campus.doctype, "write", campus, user=viewer.name))
		self.assertFalse(frappe.has_permission(campus.doctype, "create", user=viewer.name))
		self.assertFalse(frappe.has_permission(campus.doctype, "delete", campus, user=viewer.name))
		self.assertFalse(frappe.has_permission(campus.doctype, "read", campus, user=unauthorized.name))

	def test_change_tracking_and_unreferenced_deletion(self):
		self.assertTrue(frappe.get_meta("Talisma Campus").track_changes)
		campus = self.make_campus().insert()

		frappe.delete_doc(campus.doctype, campus.name, ignore_permissions=True)

		self.assertFalse(frappe.db.exists(campus.doctype, campus.name))

	def make_user(self, email: str, role: str | None = None):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Campus Test User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		if role:
			user.add_roles(role)
		return user
