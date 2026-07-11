# Copyright (c) 2026, Talisma and contributors

from uuid import uuid4

import frappe
from frappe import _
from frappe.model.document import Document


class TalismaClosureBuild(Document):
	def autoname(self) -> None:
		self.name = str(uuid4())

	def before_insert(self) -> None:
		self._require_service()

	def validate(self) -> None:
		self._require_service()

	def on_trash(self) -> None:
		self._require_service()

	@staticmethod
	def _require_service() -> None:
		if not getattr(frappe.flags, "in_talisma_closure_service", False):
			frappe.throw(_("Closure Builds are managed only by the closure service."), frappe.PermissionError)
