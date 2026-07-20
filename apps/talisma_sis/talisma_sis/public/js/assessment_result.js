frappe.ui.form.on('Assessment Result', {
	refresh(frm) {
		const status = frm.doc.talisma_result_status || 'Draft';
		frm.set_df_property('details', 'read_only', status === 'Locked');
		frm.set_df_property('talisma_change_reason', 'hidden', frm.doc.docstatus !== 1 || status === 'Locked');
		if (frm.doc.docstatus !== 1) return;
		if (status === 'Faculty Submitted') add_transition(frm, __('Department Approve'), 'approve_department');
		if (status === 'Department Approved') add_transition(frm, __('Registrar Approve'), 'approve_registrar');
		if (status === 'Registrar Approved') add_transition(frm, __('Lock Official Grade'), 'lock');
		if (status === 'Locked') add_transition(frm, __('Unlock for Correction'), 'unlock');
	},
});

function add_transition(frm, label, action) {
	frm.add_custom_button(label, () => {
		frappe.prompt(
			[{ fieldname: 'comment', fieldtype: 'Small Text', label: __('Approval Comment') }],
			(values) => frappe.call({
				method: 'talisma_sis.assessment.transition_assessment_result',
				args: { name: frm.doc.name, action, comment: values.comment },
				freeze: true,
				callback: () => frm.reload_doc(),
			}),
			label,
			__('Confirm'),
		);
	}, __('Workflow'));
}
