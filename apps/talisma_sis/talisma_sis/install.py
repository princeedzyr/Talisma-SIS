"""Installation and migration gates for the supported application stack."""

from __future__ import annotations

import frappe
from frappe import _

from talisma_sis.version import UnsupportedStackError, assert_supported_stack


def before_install() -> None:
	"""Fail before schema installation when upstream applications are unsupported."""
	validate_runtime()


def validate_runtime() -> dict[str, str]:
	"""Validate the immutable compatibility tuple used for installs and migrations."""
	try:
		return assert_supported_stack()
	except UnsupportedStackError as exc:
		frappe.throw(str(exc), title=_("Unsupported Application Stack"))
