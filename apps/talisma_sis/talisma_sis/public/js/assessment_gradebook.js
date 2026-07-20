frappe.ui.form.on('Assessment Gradebook', {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.page.set_primary_action(__('Publish Grade'), () => frappe.call({
				method: 'talisma_sis.assessment.publish_gradebook_action',
				args: { name: frm.doc.name },
				freeze: true,
				callback: () => frm.reload_doc(),
			}));
		}
		if (frm.doc.docstatus === 1 && frm.doc.transcript_status === 'Ready') {
			frm.add_custom_button(__('Mark Transcript Posted'), () => frappe.call({
				method: 'talisma_sis.assessment.mark_transcript_posted',
				args: { name: frm.doc.name },
				callback: () => frm.reload_doc(),
			}), __('Actions'));
		}
	},
	student(frm) { set_gradebook_filters(frm); },
	course(frm) { set_gradebook_filters(frm); },
});

function set_gradebook_filters(frm) {
	frm.set_query('student_group', () => ({
		filters: {
			course: frm.doc.course || undefined,
			academic_term: frm.doc.academic_term || undefined,
		},
	}));
}
