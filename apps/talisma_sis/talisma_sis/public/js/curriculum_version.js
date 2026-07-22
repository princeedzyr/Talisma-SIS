frappe.ui.form.on('Talisma Curriculum Version', {
	refresh(frm) {
		// Keep the business-facing identifier visible while preserving field-based naming.
		frm.toggle_display('curriculum_code', true);
		frm.set_df_property('curriculum_code', 'read_only', !frm.is_new());
	},
});
