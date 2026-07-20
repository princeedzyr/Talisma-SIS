frappe.ui.form.on('Course', {
	setup(frm) {
		frm.set_query('course', 'talisma_prerequisites', () => ({
			filters: {
				talisma_program: frm.doc.talisma_program,
				name: ['!=', frm.doc.name || ''],
			},
		}));
	},
	talisma_repeatable(frm) {
		if (!frm.doc.talisma_repeatable) {
			frm.set_value('talisma_max_retake_attempts', 1);
		} else if ((frm.doc.talisma_max_retake_attempts || 0) < 2) {
			frm.set_value('talisma_max_retake_attempts', 2);
		}
	},
});
