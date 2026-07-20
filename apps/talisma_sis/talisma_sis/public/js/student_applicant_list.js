frappe.listview_settings['Student Applicant'] = {
	add_fields: [
		'talisma_application_stage', 'talisma_eligibility_status',
		'talisma_application_fee_status', 'application_status', 'paid',
	],
	get_indicator(doc) {
		const stage = doc.talisma_application_stage || doc.application_status || 'Draft';
		const colors = {
			Draft: 'gray', Submitted: 'blue', 'Under Review': 'orange',
			'Decision Pending': 'purple', Approved: 'green', Waitlisted: 'orange',
			Rejected: 'red', Admitted: 'green', Withdrawn: 'gray',
		};
		return [__(stage), colors[stage] || 'blue', `talisma_application_stage,=,${stage}`];
	},
};
