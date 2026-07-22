const student_list_settings = frappe.listview_settings.Student || {};

frappe.listview_settings.Student = {
	...student_list_settings,
	add_fields: [
		...new Set([
			...(student_list_settings.add_fields || []),
			'talisma_record_status',
		]),
	],
	disable_comment_count: true,
	get_indicator(doc) {
		const status = doc.talisma_record_status || 'Active';
		const colors = {
			Applicant: 'gray',
			Admitted: 'blue',
			Enrolled: 'blue',
			Active: 'green',
			'Leave of Absence': 'orange',
			Withdrawn: 'gray',
			Suspended: 'orange',
			Dismissed: 'red',
			Graduated: 'green',
			Deceased: 'gray',
		};

		return [
			__(status),
			colors[status] || 'gray',
			`talisma_record_status,=,${status}`,
		];
	},
};
