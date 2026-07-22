frappe.ui.form.on('Course', {
	setup(frm) {
		frm.set_query('course', 'talisma_prerequisites', () => ({
			filters: frm.doc.talisma_program
				? { talisma_program: frm.doc.talisma_program, name: ['!=', frm.doc.name || ''] }
				: { name: ['!=', frm.doc.name || ''] },
		}));
	},
	refresh(frm) {
		frm.remove_custom_button(__('Add to Programs'));
		frm.toggle_display('course_name', false);
		if (!frm.doc.talisma_course_name && frm.doc.course_name) {
			frm.set_value('talisma_course_name', frm.doc.course_name);
		}
	},
	talisma_course_name(frm) {
		if (frm.doc.talisma_course_name !== frm.doc.course_name) {
			frm.set_value('course_name', frm.doc.talisma_course_name);
		}
	},
	talisma_repeatable(frm) {
		if (!frm.doc.talisma_repeatable) {
			frm.set_value('talisma_max_retake_attempts', 1);
		} else {
			if ((frm.doc.talisma_max_retake_attempts || 0) < 2) {
				frm.set_value('talisma_max_retake_attempts', 2);
			}
			if (!frm.doc.talisma_gpa_attempt_policy) {
				frm.set_value('talisma_gpa_attempt_policy', 'Highest Grade Counts');
			}
		}
	},
});
