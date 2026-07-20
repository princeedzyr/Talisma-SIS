frappe.query_reports['Program Capacity Report'] = {
	filters: [
		{ fieldname: 'admission_intake', label: __('Admission Intake'), fieldtype: 'Link', options: 'Student Admission' },
		{ fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program' },
		{ fieldname: 'academic_year', label: __('Academic Year'), fieldtype: 'Link', options: 'Academic Year' },
		{ fieldname: 'program_status', label: __('Program Status'), fieldtype: 'Select', options: '\nOpen\nClosed\nFull\nCancelled' },
	],
};
