from frappe.model.document import Document

from talisma_sis.assessment import cancel_gradebook, populate_gradebook, publish_gradebook


class AssessmentGradebook(Document):
	def validate(self):
		populate_gradebook(self)

	def before_submit(self):
		self.flags.publishing = True
		populate_gradebook(self)
		publish_gradebook(self)

	def on_cancel(self):
		cancel_gradebook(self)
