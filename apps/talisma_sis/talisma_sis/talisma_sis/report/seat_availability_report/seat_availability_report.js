frappe.query_reports['Seat Availability Report'] = {
	filters: [
		{ fieldname: 'admission_intake', label: __('Admission Intake'), fieldtype: 'Link', options: 'Student Admission' },
		{ fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program' },
		{ fieldname: 'academic_year', label: __('Academic Year'), fieldtype: 'Link', options: 'Academic Year' },
	],
};
