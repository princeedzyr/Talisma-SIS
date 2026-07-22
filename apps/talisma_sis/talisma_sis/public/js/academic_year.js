function set_academic_year_code(frm) {
	if (!frm.doc.talisma_academic_year_code && frm.doc.year_start_date) {
		const starting_year = String(frm.doc.year_start_date).slice(0, 4);
		frm.set_value('talisma_academic_year_code', `AY${starting_year}`);
	}
}

function show_academic_year_name(frm) {
	// Frappe hides a saved field-based autoname by default. Keep the institutional
	// name visible while preventing an edit that would diverge from the record ID.
	frm.set_df_property('academic_year_name', 'read_only', !frm.is_new());
	frm.set_df_property('academic_year_name', 'hidden', 0);
	frm.toggle_display('academic_year_name', true);
	frm.get_field('academic_year_name')?.$wrapper?.show();
}

frappe.ui.form.on('Academic Year', {
	refresh(frm) {
		show_academic_year_name(frm);
		set_academic_year_code(frm);
	},
	year_start_date(frm) {
		set_academic_year_code(frm);
	},
	validate(frm) {
		if (
			frm.doc.year_start_date
			&& frm.doc.year_end_date
			&& frappe.datetime.get_diff(frm.doc.year_end_date, frm.doc.year_start_date) <= 0
		) {
			frappe.throw(__('Year Start Date must be earlier than Year End Date.'));
		}
	},
});
