frappe.ui.form.on('Course Schedule', {
	onload(frm) {
		if (frm.doc.talisma_class_section) {
			frappe.show_alert({
				message: __('Opening the class section in Class Scheduling…'),
				indicator: 'blue',
			});
			frappe.set_route('Form', 'Talisma Class Section', frm.doc.talisma_class_section);
			return;
		}

		if (frm.doc.student_group) {
			frappe.db.get_value(
				'Talisma Class Section',
				{ legacy_student_group: frm.doc.student_group },
				'name'
			).then((r) => {
				if (r.message?.name) {
					frappe.set_route('Form', 'Talisma Class Section', r.message.name);
				} else {
					frappe.set_route('List', 'Talisma Class Section');
				}
			});
			return;
		}

		frappe.set_route('List', 'Talisma Class Section');
	},
});
