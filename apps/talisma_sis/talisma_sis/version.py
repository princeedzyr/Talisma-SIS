"""Supported upstream application tuples for Bryan University SIS."""

from __future__ import annotations

from importlib import import_module
from typing import Mapping


APP_MODULES = ("frappe", "erpnext", "education")

SUPPORTED_STACKS = (
	{
		"frappe": "16.25.0",
		"erpnext": "16.26.2",
		"education": "16.0.1",
	},
)


class UnsupportedStackError(RuntimeError):
	"""Raised when the runtime does not match an approved version tuple."""


def get_runtime_versions() -> dict[str, str]:
	"""Return the direct package versions used by the running Bench process."""
	versions: dict[str, str] = {}
	for app in APP_MODULES:
		module = import_module(app)
		version = getattr(module, "__version__", None)
		if not version:
			raise UnsupportedStackError(f"{app} does not expose an application version")
		versions[app] = str(version)
	return versions


def assert_supported_stack(versions: Mapping[str, str] | None = None) -> dict[str, str]:
	"""Validate and return the exact approved Frappe/ERPNext/Education tuple."""
	actual = dict(versions or get_runtime_versions())
	missing = [app for app in APP_MODULES if not actual.get(app)]
	if missing:
		raise UnsupportedStackError(
			"Missing required application versions: " + ", ".join(sorted(missing))
		)

	if any(all(actual[app] == expected[app] for app in APP_MODULES) for expected in SUPPORTED_STACKS):
		return {app: actual[app] for app in APP_MODULES}

	expected_text = " or ".join(_format_stack(stack) for stack in SUPPORTED_STACKS)
	raise UnsupportedStackError(
		f"Unsupported Bryan University SIS application stack. "
		f"Expected {expected_text}; found {_format_stack(actual)}."
	)


def _format_stack(versions: Mapping[str, str]) -> str:
	return ", ".join(f"{app} {versions.get(app, '<missing>')}" for app in APP_MODULES)
