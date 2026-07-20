frappe.ui.form.on('Program', {
	setup(frm) {
		frm.set_query('course', 'courses', () => ({
			filters: { talisma_program: frm.doc.name },
		}));
	},
});
