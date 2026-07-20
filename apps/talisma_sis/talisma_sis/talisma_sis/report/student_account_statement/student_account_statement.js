frappe.query_reports['Student Account Statement'] = {
	filters: [
		{ fieldname: 'student', label: __('Student'), fieldtype: 'Link', options: 'Student', reqd: 1 },
		{ fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date' },
		{ fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date' },
	],
};
