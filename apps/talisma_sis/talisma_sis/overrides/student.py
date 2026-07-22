import frappe
from education.education.doctype.student.student import Student as EducationStudent
from frappe import _


class Student(EducationStudent):
	"""Keep Education's Customer synchronization with Student-facing messages."""

	def update_linked_customer(self):
		customer = frappe.get_doc("Customer", self.customer)
		if self.customer_group:
			customer.customer_group = self.customer_group
		customer.customer_name = self.student_name
		customer.image = self.image
		customer.save()

		frappe.msgprint(_("Student {0} updated").format(self.student_name or self.name), alert=True)

	def create_customer(self):
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": self.student_name,
				"customer_group": self.customer_group
				or frappe.db.get_single_value("Selling Settings", "customer_group"),
				"customer_type": "Individual",
				"image": self.image,
			}
		).insert()

		frappe.db.set_value("Student", self.name, "customer", customer.name)
		frappe.msgprint(_("Student {0} created").format(self.student_name or self.name), alert=True)
