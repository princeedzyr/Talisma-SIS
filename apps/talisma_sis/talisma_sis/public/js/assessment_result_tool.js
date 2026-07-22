frappe.ui.form.on('Assessment Result Tool', {
	setup(frm) {
		frm.add_fetch('assessment_plan', 'talisma_class_section', 'talisma_class_section');
		frm.add_fetch('talisma_class_section', 'legacy_student_group', 'student_group');
	},
	talisma_class_section(frm) {
		if (!frm.doc.talisma_class_section) {
			frm.set_value('student_group', null);
			return;
		}
		frappe.db.get_value('Talisma Class Section', frm.doc.talisma_class_section, 'legacy_student_group').then((r) => {
			frm.set_value('student_group', r.message?.legacy_student_group || frm.doc.talisma_class_section);
			frm.trigger('assessment_plan');
		});
	},
});
