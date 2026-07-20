from unittest import TestCase
from unittest.mock import Mock, patch

from talisma_sis.version import (
	UnsupportedStackError,
	assert_supported_stack,
	get_runtime_versions,
)


SUPPORTED = {
	"frappe": "16.25.0",
	"erpnext": "16.26.2",
	"education": "16.0.1",
}


class TestVersionContract(TestCase):
	def test_exact_supported_tuple_is_accepted(self):
		self.assertEqual(assert_supported_stack(SUPPORTED), SUPPORTED)

	def test_any_version_drift_is_rejected_with_actionable_evidence(self):
		with self.assertRaisesRegex(
			UnsupportedStackError,
			"Expected frappe 16.25.0, erpnext 16.26.2, education 16.0.1",
		):
			assert_supported_stack({**SUPPORTED, "education": "17.0.0-dev"})

	def test_missing_required_application_version_is_rejected(self):
		with self.assertRaisesRegex(UnsupportedStackError, "Missing required application versions: education"):
			assert_supported_stack({"frappe": "16.25.0", "erpnext": "16.26.2"})

	@patch("talisma_sis.version.import_module")
	def test_runtime_versions_come_from_application_packages(self, import_module):
		import_module.side_effect = [
			Mock(__version__="16.25.0"),
			Mock(__version__="16.26.2"),
			Mock(__version__="16.0.1"),
		]

		self.assertEqual(get_runtime_versions(), SUPPORTED)
