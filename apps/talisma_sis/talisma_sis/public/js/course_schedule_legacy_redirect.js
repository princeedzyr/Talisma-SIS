frappe.ui.form.on('Course Schedule', {
	onload(frm) {
		if (frm.doc.student_group) {
			frappe.show_alert({
				message: __('Opening the class section in Class Scheduling…'),
				indicator: 'blue',
			});
			frappe.set_route('Form', 'Student Group', frm.doc.student_group);
			return;
		}

		frappe.set_route('List', 'Student Group');
	},
});
