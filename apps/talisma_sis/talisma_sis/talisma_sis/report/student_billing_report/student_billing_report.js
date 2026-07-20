frappe.query_reports['Student Billing Report'] = {
	filters: [
		{ fieldname: 'student', label: __('Student'), fieldtype: 'Link', options: 'Student' },
		{ fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program' },
		{ fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date' },
		{ fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date' },
		{ fieldname: 'status', label: __('Billing Status'), fieldtype: 'Select', options: '\nPaid\nUnpaid\nOverdue\nPartly Paid' },
	],
};
