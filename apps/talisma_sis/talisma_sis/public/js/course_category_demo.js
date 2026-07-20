frappe.ui.form.on('Course Category', {
	setup(frm) {
		frm.set_query('course', 'courses', () => ({
			filters: { talisma_program: frm.doc.program },
		}));
	},
	program(frm) {
		if (frm.doc.courses?.length) {
			frm.clear_table('courses');
			frm.refresh_field('courses');
		}
	},
});
