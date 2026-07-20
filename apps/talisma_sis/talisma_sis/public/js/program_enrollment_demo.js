frappe.ui.form.on('Program Enrollment', {
	setup(frm) {
		frm.set_query('talisma_curriculum_version', () => ({
			filters: {
				program: frm.doc.program,
				status: 'Published',
			},
		}));
	},
	program(frm) {
		if (!frm.doc.program) {
			frm.set_value('talisma_curriculum_version', null);
			return;
		}
		frappe.db.get_value(
			'Talisma Curriculum Version',
			{ program: frm.doc.program, status: 'Published' },
			'name',
		).then((r) => frm.set_value('talisma_curriculum_version', r.message?.name || null));
	},
	refresh(frm) {
		if (
			frappe.boot?.sitename !== 'demo.talisma.local' ||
			frm.is_new() ||
			!frappe.meta.has_field('Program Enrollment', 'talisma_registration_status')
		) return;

		load_registration_summary(frm);
		if (frm.doc.docstatus !== 2) {
			frm.add_custom_button(
				__('Register Courses'),
				() => open_registration_dialog(frm),
				__('Registrar')
			);
		}
		frm.add_custom_button(
			__('View Course Registrations'),
			() => frappe.set_route('List', 'Course Enrollment', {
				program_enrollment: frm.doc.name,
			}),
			__('Registrar')
		);
	},
});

function load_registration_summary(frm) {
	frappe.call({
		method: 'talisma_sis.registrar.get_registration_summary',
		args: { program_enrollment: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			const summary = r.message;
			frm.dashboard.set_headline_alert(
				__('Registered for {0} of {1} program courses', [
					summary.registered_count,
					summary.courses.length,
				]),
				summary.registered_count ? 'green' : 'orange'
			);
		},
	});
}

function open_registration_dialog(frm) {
	frappe.call({
		method: 'talisma_sis.registrar.get_section_options',
		args: { program_enrollment: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			const summary = r.message;
			const available = summary.sections.filter((section) => !section.registered);
			if (!available.length) {
				frappe.msgprint(__('No additional open course sections are available.'));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __('Register Courses'),
				fields: [
					{
						fieldname: 'context',
						fieldtype: 'HTML',
						options: `<p><strong>${frappe.utils.escape_html(summary.student_name)}</strong><br>
							${frappe.utils.escape_html(summary.program)} &middot;
							${frappe.utils.escape_html(summary.academic_term || summary.academic_year)}</p>`,
					},
					{
						fieldname: 'sections',
						label: __('Open Course Sections'),
						fieldtype: 'MultiCheck',
						columns: 1,
						options: available.map((section) => ({
							label: `${section.course} · CRN ${section.talisma_crn} · ${section.talisma_meeting_days} ${section.talisma_start_time}`,
							value: section.name,
						})),
					},
				],
				primary_action_label: __('Register Selected'),
				primary_action(values) {
					if (!values.sections?.length) {
						frappe.msgprint(__('Select at least one course section.'));
						return;
					}
					frappe.call({
						method: 'talisma_sis.registrar.register_sections',
						args: { program_enrollment: frm.doc.name, sections: values.sections },
						freeze: true,
						freeze_message: __('Registering courses...'),
						callback(result) {
							if (!result.message) return;
							dialog.hide();
							frappe.show_alert({
								message: result.message.created.length
									? __('Course registration completed')
									: __('Courses were already registered'),
								indicator: 'green',
							});
							frm.reload_doc();
						},
					});
				},
			});
			dialog.show();
		},
	});
}
