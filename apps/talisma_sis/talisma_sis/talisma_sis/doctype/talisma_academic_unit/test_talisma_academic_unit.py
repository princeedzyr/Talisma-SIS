# Copyright (c) 2026, Talisma and contributors
# For license information, please see license.txt

from uuid import UUID, uuid4

import frappe
from MySQLdb import IntegrityError
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from talisma_sis.patches.v0_0.add_talisma_academic_unit_unique_constraint import CONSTRAINT_NAME


class TestTalismaAcademicUnit(IntegrationTestCase):
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
			"valid_from": nowdate(),
			"default_timezone": "UTC",
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def make_type(self, **overrides):
		suffix = uuid4().hex[:8].upper()
		values = {
			"doctype": "Talisma Academic Unit Type",
			"type_code": f"TYPE_{suffix}",
			"type_name": f"Type {suffix}",
			"can_grant_credentials": 1,
			"can_own_programs": 1,
			"can_own_courses": 1,
		}
		values.update(overrides)
		return frappe.get_doc(values).insert()

	def make_unit(self, institution=None, unit_type=None, **overrides):
		institution = institution or self.make_institution()
		unit_type = unit_type or self.make_type()
		values = {
			"doctype": "Talisma Academic Unit",
			"institution": institution.name,
			"unit_code": "TEST_UNIT",
			"unit_name": "Test Unit",
			"unit_type": unit_type.name,
			"status": "Planned",
			"valid_from": institution.valid_from,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_uuid_normalization_and_scoped_uniqueness(self):
		institution = self.make_institution()
		unit_type = self.make_type()
		unit = self.make_unit(institution, unit_type, unit_code=" school-one ").insert()
		self.assertEqual(UUID(unit.name).version, 4)
		self.assertEqual(unit.unit_code, "SCHOOL-ONE")
		with self.assertRaises(frappe.UniqueValidationError):
			self.make_unit(institution, unit_type, unit_code="school-one").insert()
		other = self.make_unit(self.make_institution(), unit_type, unit_code="school-one").insert()
		self.assertNotEqual(unit.institution, other.institution)

	def test_database_constraint_exists_and_blocks_bypass(self):
		unit = self.make_unit().insert()
		constraint = frappe.db.sql(
			"""SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
			WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabTalisma Academic Unit'
			AND CONSTRAINT_TYPE = 'UNIQUE' AND CONSTRAINT_NAME = %s""",
			(CONSTRAINT_NAME,),
		)
		self.assertTrue(constraint)
		with self.assertRaises(IntegrityError):
			frappe.db.sql(
				"""INSERT INTO `tabTalisma Academic Unit`
				(name, creation, modified, owner, modified_by, docstatus, idx, institution,
				 unit_code, unit_name, unit_type, status, valid_from)
				VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, 0, %s,
				 %s, 'Duplicate', %s, 'Planned', %s)""",
				(str(uuid4()), unit.institution, unit.unit_code, unit.unit_type, unit.valid_from),
			)

	def test_immutable_fields_and_validity(self):
		unit = self.make_unit().insert()
		unit.institution = self.make_institution().name
		with self.assertRaises(frappe.ValidationError):
			unit.save()
		unit.reload()
		unit.unit_code = "NEW_CODE"
		with self.assertRaises(frappe.ValidationError):
			unit.save()
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(valid_to=add_days(getdate(nowdate()), -1)).insert()

	def test_unit_validity_must_fit_institution(self):
		institution = self.make_institution(
			valid_from=add_days(getdate(nowdate()), -5),
			valid_to=add_days(getdate(nowdate()), 5),
		)
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(institution, valid_from=add_days(institution.valid_from, -1)).insert()
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(institution, valid_to=None).insert()

	def test_institution_and_type_must_be_eligible(self):
		for status in ("Inactive", "Closed"):
			with self.subTest(status=status), self.assertRaises(frappe.ValidationError):
				self.make_unit(self.make_institution(status=status)).insert()
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(unit_type=self.make_type(disabled=1)).insert()

	def test_capabilities_cannot_exceed_type_or_change_after_planned(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_unit(unit_type=self.make_type(can_own_courses=0), can_own_courses=1).insert()
		unit = self.make_unit(status="Active", can_own_courses=1).insert()
		unit.can_own_courses = 0
		with self.assertRaises(frappe.ValidationError):
			unit.save()

	def test_planned_unit_can_narrow_capabilities_and_change_enabled_type(self):
		unit = self.make_unit(can_own_courses=1).insert()
		unit.can_own_courses = 0
		unit.unit_type = self.make_type().name
		unit.save()

		self.assertFalse(unit.can_own_courses)

	def test_lifecycle_and_closed_date_rules(self):
		unit = self.make_unit().insert()
		unit.status = "Inactive"
		with self.assertRaises(frappe.ValidationError):
			unit.save()
		unit.reload()
		unit.status = "Active"
		unit.save()
		unit.status = "Closed"
		with self.assertRaises(frappe.ValidationError):
			unit.save()
		unit.reload()
		unit.status = "Closed"
		unit.valid_to = nowdate()
		unit.save()
		unit.status = "Active"
		with self.assertRaises(frappe.ValidationError):
			unit.save()
		unit.reload()
		unit.unit_name = "Changed after closure"
		with self.assertRaises(frappe.ValidationError):
			unit.save()

	def test_no_hierarchy_or_mapping_fields_exist(self):
		meta = frappe.get_meta("Talisma Academic Unit")
		for fieldname in ("parent_unit", "campus", "company", "department", "cost_center", "successor_unit"):
			self.assertFalse(meta.has_field(fieldname))

	def test_permissions_and_change_tracking(self):
		unit = self.make_unit().insert()
		manager = self.make_user("unit-manager@example.com", "Talisma Institution Manager")
		viewer = self.make_user("unit-viewer@example.com", "Talisma Institution Viewer")
		unauthorized = self.make_user("unit-unauthorized@example.com")
		self.assertTrue(frappe.has_permission(unit.doctype, "create", user=manager.name))
		self.assertTrue(frappe.has_permission(unit.doctype, "write", unit, user=manager.name))
		self.assertTrue(frappe.has_permission(unit.doctype, "delete", unit, user=manager.name))
		self.assertTrue(frappe.has_permission(unit.doctype, "read", unit, user=viewer.name))
		self.assertFalse(frappe.has_permission(unit.doctype, "create", user=viewer.name))
		self.assertFalse(frappe.has_permission(unit.doctype, "write", unit, user=viewer.name))
		self.assertFalse(frappe.has_permission(unit.doctype, "delete", unit, user=viewer.name))
		self.assertFalse(frappe.has_permission(unit.doctype, "read", unit, user=unauthorized.name))
		self.assertTrue(frappe.get_meta(unit.doctype).track_changes)

	def test_unreferenced_unit_can_be_deleted(self):
		unit = self.make_unit().insert()
		frappe.delete_doc(unit.doctype, unit.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists(unit.doctype, unit.name))

	def make_user(self, email: str, role: str | None = None):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Academic Unit User", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		if role:
			user.add_roles(role)
		return user
