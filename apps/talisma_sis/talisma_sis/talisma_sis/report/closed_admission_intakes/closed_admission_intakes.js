frappe.query_reports['Closed Admission Intakes'] = {
	filters: [
		{ fieldname: 'academic_year', label: __('Academic Year'), fieldtype: 'Link', options: 'Academic Year' },
		{ fieldname: 'academic_term', label: __('Academic Term'), fieldtype: 'Link', options: 'Academic Term' },
	],
};
