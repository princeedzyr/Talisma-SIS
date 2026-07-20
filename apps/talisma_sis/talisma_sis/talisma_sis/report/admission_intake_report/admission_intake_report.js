frappe.query_reports['Admission Intake Report'] = {
	filters: [
		{ fieldname: 'academic_year', label: __('Academic Year'), fieldtype: 'Link', options: 'Academic Year' },
		{ fieldname: 'academic_term', label: __('Academic Term'), fieldtype: 'Link', options: 'Academic Term' },
		{ fieldname: 'status', label: __('Status'), fieldtype: 'Select', options: '\nDraft\nPlanned\nOpen\nClosed\nCancelled\nArchived' },
	],
};
