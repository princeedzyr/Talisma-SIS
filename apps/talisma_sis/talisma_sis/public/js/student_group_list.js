// Student Group has its own Active/Inactive field. Suppress Frappe's duplicate
// Enabled/Disabled indicator column while preserving indicators for all other DocTypes.
if (!frappe.has_indicator.__talisma_student_group_override) {
	const original_has_indicator = frappe.has_indicator;
	const has_indicator = function (doctype) {
		if (doctype === 'Student Group') {
			return false;
		}
		return original_has_indicator.apply(this, arguments);
	};
	has_indicator.__talisma_student_group_override = true;
	frappe.has_indicator = has_indicator;
}
