frappe.ui.form.on('Student Admission', {
	setup(frm) {
		frm.set_query('talisma_academic_term', () => ({
			filters: { academic_year: frm.doc.academic_year },
		}));
	},

	academic_year(frm) {
		if (frm.doc.talisma_academic_term) frm.set_value('talisma_academic_term', null);
	},

	validate(frm) {
		const start = frm.doc.admission_start_date;
		const end = frm.doc.admission_end_date;
		const decision = frm.doc.talisma_decision_release_date;
		const confirmation = frm.doc.talisma_enrollment_confirmation_deadline;
		if (start && end && start >= end) {
			frappe.throw(__('Application Start Date must be before Application End Date.'));
		}
		if (end && decision && decision <= end) {
			frappe.throw(__('Decision Release Date must be after Application End Date.'));
		}
		if (decision && confirmation && confirmation <= decision) {
			frappe.throw(__('Enrollment Confirmation Deadline must be after Decision Release Date.'));
		}
	},
});

frappe.ui.form.on('Student Admission Program', {
	program(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.program) return;
		frappe.db.get_value('Program', row.program, ['talisma_degree', 'talisma_academic_unit'])
			.then((response) => {
				frappe.model.set_value(cdt, cdn, 'talisma_degree', response.message?.talisma_degree || null);
				frappe.model.set_value(cdt, cdn, 'talisma_academic_unit', response.message?.talisma_academic_unit || null);
			});
	},

	talisma_intake_capacity(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const capacity = Number(row.talisma_intake_capacity || 0);
		const filled = Number(row.talisma_seats_filled || 0);
		frappe.model.set_value(cdt, cdn, 'talisma_seats_available', Math.max(capacity - filled, 0));
		if (capacity > 0 && filled >= capacity && !['Closed', 'Cancelled'].includes(row.talisma_status)) {
			frappe.model.set_value(cdt, cdn, 'talisma_status', 'Full');
		}
	},
});
