import frappe

from talisma_sis.student_documents import portal_documents, student_for_user


no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/student-documents"
		raise frappe.Redirect
	student = student_for_user()
	if not student:
		frappe.throw("Your user account is not linked to a Student record.", frappe.PermissionError)
	student_doc = frappe.get_doc("Student", student)
	context.title = "My Documents"
	context.student = student
	context.student_name = student_doc.student_name
	context.documents = portal_documents(student)
	context.no_cache = 1
	return context
