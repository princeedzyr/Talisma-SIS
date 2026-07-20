frappe.ui.form.on('Student Applicant', {
	setup(frm) {
		frm.set_query('gender', () => ({ query: 'talisma_sis.demo.gender_options_query' }));
		frm.set_df_property('gender', 'only_select', 1);
		frm.set_query('student_admission', () => ({
			query: 'talisma_sis.admissions.open_admission_intake_query',
		}));
		frm.set_query('program', () => ({
			query: 'talisma_sis.admissions.admission_program_query',
			filters: { admission_intake: frm.doc.student_admission },
		}));
	},

	student_admission(frm) {
		frm.set_value('program', null);
		if (!frm.doc.student_admission) return;
		apply_intake_defaults(frm);
	},

	program(frm) {
		if (!frm.doc.student_admission || !frm.doc.program) return;
		apply_intake_defaults(frm, frm.doc.program);
	},

	refresh(frm) {
		if (!frappe.meta.has_field('Student Applicant', 'talisma_application_stage')) return;
		configure_application_form(frm);
		remove_legacy_decision_buttons(frm);
		if (!frm.is_new()) add_workflow_actions(frm);
		if (frm.doc.talisma_converted_student) {
			frm.dashboard.set_headline_alert(
				__('Admitted as student {0}', [frm.doc.talisma_converted_student]), 'green'
			);
		} else {
			frm.dashboard.set_headline_alert(
				__('Application stage: {0}', [frm.doc.talisma_application_stage || 'Draft']),
				stage_indicator(frm.doc.talisma_application_stage)
			);
		}
	},
});

function configure_application_form(frm) {
	const stage = frm.doc.talisma_application_stage || 'Draft';
	const locked = !frm.is_new() && stage !== 'Draft';
	['student_admission', 'program'].forEach((fieldname) => {
		frm.set_df_property(fieldname, 'read_only', locked ? 1 : 0);
	});
	[
		'academic_year', 'academic_term', 'talisma_campus', 'talisma_degree',
		'talisma_academic_unit', 'talisma_application_fee', 'talisma_application_stage',
	].forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));
	const administrator = frappe.session.user === 'Administrator' || frappe.user.has_role('System Manager');
	frm.set_df_property('talisma_capacity_override', 'hidden', administrator ? 0 : 1);
	frm.set_df_property('talisma_admin_override_section', 'hidden', administrator ? 0 : 1);
	frm.set_df_property('talisma_transfer_audit_section', 'hidden', frm.doc.talisma_transferred_on ? 0 : 1);
}

function remove_legacy_decision_buttons(frm) {
	['Approve', 'Reject', 'Re-Open'].forEach((label) => frm.remove_custom_button(__(label)));
}

function add_workflow_actions(frm) {
	const stage = frm.doc.talisma_application_stage || 'Draft';
	const add = (label, target, options = {}) => {
		frm.add_custom_button(__(label), () => {
			if (options.decision) {
				prompt_decision(frm, target, options.conditions);
			} else {
				transition_application(frm, target);
			}
		}, __('Admissions'));
	};

	if (stage === 'Draft') add('Submit Application', 'Submitted');
	if (stage === 'Submitted') {
		add('Start Review', 'Under Review');
		add_review_action(frm);
	}
	if (stage === 'Under Review') {
		add_review_action(frm);
		add('Send to Decision', 'Decision Pending');
	}
	if (stage === 'Decision Pending') {
		add('Approve Offer', 'Approved', { decision: true, conditions: true });
		add('Add to Waitlist', 'Waitlisted', { decision: true });
		add('Reject Application', 'Rejected', { decision: true });
	}
	if (stage === 'Waitlisted') {
		add('Return to Decision', 'Decision Pending');
		add('Approve Offer', 'Approved', { decision: true, conditions: true });
		add('Reject Application', 'Rejected', { decision: true });
	}
	if (stage === 'Approved' && !frm.doc.talisma_converted_student) add_admit_action(frm);
	if (['Draft', 'Submitted', 'Under Review', 'Decision Pending', 'Waitlisted', 'Approved'].includes(stage)) {
		add('Withdraw Application', 'Withdrawn');
	}
	if (
		!['Admitted', 'Rejected', 'Withdrawn'].includes(stage)
		&& (frappe.session.user === 'Administrator' || frappe.user.has_role('System Manager'))
	) add_transfer_action(frm);
}

function add_review_action(frm) {
	frm.add_custom_button(__('Review Eligibility'), () => {
		frappe.prompt([
			{
				fieldname: 'status', label: __('Eligibility Status'), fieldtype: 'Select',
				options: 'Eligible\nConditionally Eligible\nIneligible', reqd: 1,
				default: frm.doc.talisma_eligibility_status === 'Pending' ? null : frm.doc.talisma_eligibility_status,
			},
			{
				fieldname: 'notes', label: __('Review Notes'), fieldtype: 'Small Text', reqd: 1,
				default: frm.doc.talisma_eligibility_notes,
			},
		], (values) => {
			frappe.call({
				method: 'talisma_sis.admissions.review_application_eligibility',
				args: { applicant_name: frm.doc.name, status: values.status, notes: values.notes },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		}, __('Eligibility Review'), __('Save Review'));
	}, __('Admissions'));
}

function prompt_decision(frm, target_stage, allow_conditions) {
	const fields = [{
		fieldname: 'reason', label: __('Decision Reason'), fieldtype: 'Small Text', reqd: 1,
	}];
	if (allow_conditions) fields.push({
		fieldname: 'conditions', label: __('Admission Conditions'), fieldtype: 'Small Text',
		description: __('Leave blank for an unconditional offer.'),
	});
	frappe.prompt(fields, (values) => {
		transition_application(frm, target_stage, values.reason, values.conditions);
	}, __('Record Admission Decision'), __('Confirm'));
}

function transition_application(frm, target_stage, reason = null, conditions = null) {
	frappe.call({
		method: 'talisma_sis.admissions.transition_application',
		args: { applicant_name: frm.doc.name, target_stage, reason, conditions },
		freeze: true,
		freeze_message: __('Updating application workflow...'),
		callback: () => frm.reload_doc(),
	});
}

function add_admit_action(frm) {
	frm.add_custom_button(__('Admit and Create Student'), () => {
		frappe.prompt({
			fieldname: 'decision_note', label: __('Admission Note'), fieldtype: 'Small Text',
			default: frm.doc.talisma_decision_note,
		}, (values) => admit_applicant(frm, values.decision_note), __('Confirm Admission'), __('Admit'));
	}, __('Admissions'));
}

function add_transfer_action(frm) {
	frm.add_custom_button(__('Transfer Application'), () => {
		const dialog = new frappe.ui.Dialog({
			title: __('Transfer Application'),
			fields: [
				{ fieldname: 'admission_intake', label: __('New Admission Intake'), fieldtype: 'Link', options: 'Student Admission', reqd: 1 },
				{ fieldname: 'program', label: __('New Program'), fieldtype: 'Link', options: 'Program', reqd: 1 },
				{ fieldname: 'reason', label: __('Transfer Reason'), fieldtype: 'Small Text', reqd: 1 },
			],
			primary_action_label: __('Transfer'),
			primary_action(values) {
				dialog.hide();
				frappe.call({
					method: 'talisma_sis.admissions.transfer_application',
					args: { applicant_name: frm.doc.name, ...values },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			},
		});
		dialog.fields_dict.admission_intake.get_query = () => ({
			query: 'talisma_sis.admissions.open_admission_intake_query',
		});
		dialog.fields_dict.program.get_query = () => ({
			query: 'talisma_sis.admissions.admission_program_query',
			filters: { admission_intake: dialog.get_value('admission_intake') },
		});
		dialog.show();
	}, __('Admissions'));
}

function apply_intake_defaults(frm, program = null) {
	frappe.call({
		method: 'talisma_sis.admissions.get_application_defaults',
		args: { admission_intake: frm.doc.student_admission, program },
		callback(r) {
			if (!r.message) return;
			const values = {
				academic_year: r.message.academic_year,
				academic_term: r.message.academic_term,
				talisma_campus: r.message.campus,
			};
			if (program) Object.assign(values, {
				talisma_degree: r.message.degree,
				talisma_academic_unit: r.message.academic_unit,
				talisma_application_fee: r.message.application_fee,
			});
			frm.set_value(values);
		},
	});
}

function admit_applicant(frm, decision_note) {
	frappe.call({
		method: 'talisma_sis.admissions.admit_applicant',
		args: { applicant_name: frm.doc.name, decision_note },
		freeze: true,
		freeze_message: __('Creating student and program enrollment...'),
		callback(r) {
			if (!r.message) return;
			frappe.show_alert({ message: __('Applicant admitted successfully'), indicator: 'green' });
			frm.reload_doc().then(() => frappe.set_route('Form', 'Program Enrollment', r.message.program_enrollment));
		},
	});
}

function stage_indicator(stage) {
	if (['Approved', 'Admitted'].includes(stage)) return 'green';
	if (['Rejected', 'Withdrawn'].includes(stage)) return 'red';
	if (stage === 'Waitlisted') return 'orange';
	return 'blue';
}
