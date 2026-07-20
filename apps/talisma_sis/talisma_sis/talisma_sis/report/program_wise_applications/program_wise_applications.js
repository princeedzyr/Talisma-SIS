frappe.query_reports['Program-wise Applications'] = {
	filters: [
		{ fieldname: 'admission_intake', label: __('Admission Intake'), fieldtype: 'Link', options: 'Student Admission' },
		{ fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program' },
	],
};
