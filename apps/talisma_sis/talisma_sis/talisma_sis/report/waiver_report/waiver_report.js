frappe.query_reports['Waiver Report'] = {
	filters: [
		{ fieldname: 'student', label: __('Student'), fieldtype: 'Link', options: 'Student' },
		{ fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date' },
		{ fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date' },
	],
};
