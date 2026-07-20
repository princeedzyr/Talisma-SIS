frappe.ui.form.on('Student Group', {
	setup(frm) {
		frm.set_query('academic_term', () => ({ filters: { term_end_date: ['>=', frappe.datetime.get_today()] } }));
		frm.set_query('talisma_primary_instructor', () => ({ filters: { status: 'Active' } }));
	},
	onload(frm) {
		if (frm.is_new()) {
			frm.set_value('group_based_on', 'Course');
			frm.set_value('talisma_delivery_method', frm.doc.talisma_delivery_method || 'In Person');
			frm.set_value('talisma_section_status', frm.doc.talisma_section_status || 'Planned');
		}
	},
	refresh(frm) {
		frm.set_df_property('group_based_on', 'read_only', 1);
		frm.set_df_property('max_strength', 'label', __('Capacity'));
		frm.set_df_property('max_strength', 'reqd', 1);
		frm.set_df_property('talisma_waitlist_capacity', 'reqd', Boolean(frm.doc.talisma_allow_waitlist));
	},
	academic_term(frm) {
		if (!frm.doc.academic_term) return;
		frappe.db.get_value('Academic Term', frm.doc.academic_term, ['term_start_date', 'term_end_date']).then((r) => {
			if (!frm.doc.talisma_class_start_date) frm.set_value('talisma_class_start_date', r.message?.term_start_date);
			if (!frm.doc.talisma_class_end_date) frm.set_value('talisma_class_end_date', r.message?.term_end_date);
		});
	},
	talisma_allow_waitlist(frm) {
		frm.set_df_property('talisma_waitlist_capacity', 'reqd', Boolean(frm.doc.talisma_allow_waitlist));
		if (!frm.doc.talisma_allow_waitlist) frm.set_value('talisma_waitlist_capacity', 0);
	},
	validate(frm) {
		if (Number(frm.doc.max_strength || 0) <= 0) frappe.throw(__('Capacity must be greater than zero.'));
		if (frm.doc.talisma_allow_waitlist && Number(frm.doc.talisma_waitlist_capacity || 0) <= 0) frappe.throw(__('Waitlist Capacity must be greater than zero.'));
		if (frm.doc.talisma_class_start_date && frm.doc.talisma_class_end_date && frm.doc.talisma_class_start_date > frm.doc.talisma_class_end_date) frappe.throw(__('Class Start Date must be on or before Class End Date.'));
	},
});

frappe.ui.form.on('Talisma Class Period', {
	start_time(frm, cdt, cdn) { validate_period(cdt, cdn); },
	end_time(frm, cdt, cdn) { validate_period(cdt, cdn); },
});

function validate_period(cdt, cdn) {
	const row = locals[cdt][cdn];
	if (row.start_time && row.end_time && row.end_time <= row.start_time) {
		frappe.model.set_value(cdt, cdn, 'end_time', null);
		frappe.msgprint(__('Period End Time must be later than Start Time.'));
	}
}
