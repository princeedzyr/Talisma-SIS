frappe.query_reports['Program Fee Collection Report'] = {
	filters: [
		{ fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program' },
		{ fieldname: 'academic_year', label: __('Academic Year'), fieldtype: 'Link', options: 'Academic Year' },
		{ fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date' },
		{ fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date' },
	],
};
