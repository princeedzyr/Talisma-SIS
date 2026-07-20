frappe.ui.form.on('Student', {
	setup(frm) {
		frm.set_query('gender', () => ({
			query: 'talisma_sis.demo.gender_options_query',
		}));
		frm.set_df_property('gender', 'only_select', 1);
	},
	onload: sync_student_identity,
	refresh(frm) {
		sync_student_identity(frm);
		if (
			frappe.boot?.sitename !== 'demo.talisma.local' ||
			frm.is_new() ||
			!frappe.meta.has_field('Student', 'talisma_enrollment_tab')
		) return;
		load_student_360(frm);
	},
	first_name: sync_student_identity,
	middle_name: sync_student_identity,
	last_name: sync_student_identity,
});

function sync_student_identity(frm) {
	const full_name = [frm.doc.first_name, frm.doc.middle_name, frm.doc.last_name]
		.filter(Boolean)
		.join(' ');
	if (frm.doc.student_name !== full_name) {
		frm.doc.student_name = full_name;
		frm.refresh_field('student_name');
	}
	const student_number = frm.fields_dict.talisma_student_number;
	if (student_number) {
		student_number.set_value(frm.is_new() ? __('Assigned when saved') : frm.doc.name);
	}
}

function load_student_360(frm) {
	set_360_loading(frm);
	frappe.call({
		method: 'talisma_sis.student_360.get_student_360',
		args: { student: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			frm.student_360 = r.message;
			render_student_records(frm, r.message.student_records || {});
			render_degree_audit(frm, r.message.degree_audit || {});
			render_enrollment(frm, r.message.enrollment);
			render_courses(frm, r.message.course_registration);
			render_finance(frm, r.message.finance);
			bind_360_actions(frm);
		},
	});
}

function set_360_loading(frm) {
	[
		'talisma_current_enrollment_html',
		'talisma_enrollment_history_html',
		'talisma_course_registration_html',
		'talisma_fee_structure_html',
		'talisma_fee_details_html',
		'talisma_payment_summary_html',
		'talisma_payment_history_html',
		'talisma_scholarships_html',
		'talisma_waivers_html',
		'talisma_refunds_html',
		'talisma_profile_overview_html',
		'talisma_advisor_assignments_html',
		'talisma_academic_standing_html',
		'talisma_degree_audit_html',
		'talisma_student_holds_html',
		'talisma_privacy_preferences_html',
		'talisma_documents_html',
		'talisma_status_history_html',
	].forEach((fieldname) => set_html(frm, fieldname, loading_html()));
}

function render_student_records(frm, records) {
	const summary = records.summary || {};
	set_html(frm, 'talisma_profile_overview_html', stat_grid([
		['Record Status', status_badge(summary.record_status)],
		['Primary Program', summary.primary_program],
		['Academic Level', summary.academic_level],
		['Primary Advisor', summary.advisor],
		['Academic Standing', status_badge(summary.standing)],
		['Active Holds', summary.active_holds || 0],
		['Privacy Restriction', summary.privacy_restriction ? status_badge('Restricted') : status_badge('Not Restricted')],
	]));
	set_html(frm, 'talisma_advisor_assignments_html',
		`<div class="talisma-academic-profile-panel">${action_bar(__('Assign, edit, or end advisors without leaving this Student Profile.'), [
			action_button('add-advisor', __('Add Advisor'), 'primary'),
		])
		+ data_table(
			['Advisor', 'Assignment Scope', 'Status', 'Effective Dates', 'Role', 'Actions'],
			(records.advisors || []).map((row) => [
				`<div class="talisma-360-identity"><strong>${escape_html(text_value(row.advisor_name))}</strong><small>${escape_html(text_value(row.advisor_type))}</small></div>`,
				advisor_scope(row), status_badge(row.status),
				`${date_value(row.effective_from)} &ndash; ${date_value(row.effective_to)}`,
				row.primary_advisor ? status_badge('Primary') : status_badge('Supporting'),
				inline_actions([
					record_action_button('edit-advisor', __('Edit'), row.name),
					row.status === 'Active' ? record_action_button('end-advisor', __('End'), row.name) : '',
				]),
			]),
			__('No advisor assignments found.'),
		)}</div>`);
	set_html(frm, 'talisma_academic_standing_html',
		action_bar(__('Automatically calculated from course registrations and submitted grades.'), [])
		+ data_table(
			['Academic Term', 'Standing', 'Term GPA', 'Cumulative GPA', 'Attempted Credits', 'Earned Credits'],
			(records.standings || []).map((row) => [
				record_link('Talisma Student Academic Standing', row.name, row.academic_term),
				status_badge(row.standing), number_value(row.term_gpa, 3), number_value(row.cumulative_gpa, 3),
				number_value(row.attempted_credits, 2), number_value(row.earned_credits, 2),
			]),
			__('No academic-standing records found.'),
		));
	set_html(frm, 'talisma_student_holds_html',
		action_bar(__('Active holds can block registration, transcripts, graduation, or finance.'), [
			action_button('add-hold', __('Add'), 'primary'),
		])
		+ data_table(
			['Hold Type', 'Reason', 'Effective From', 'Effective To', 'Blocked Activities', 'Status'],
			(records.holds || []).map((row) => [
				record_link('Talisma Student Hold', row.name, row.hold_type), text_value(row.reason),
				date_value(row.effective_from), date_value(row.effective_to), hold_blocks(row), status_badge(row.status),
			]),
			__('No active administrative holds.'),
		));
	set_html(frm, 'talisma_privacy_preferences_html',
		action_bar(__('FERPA restrictions and directory-information consent.'), [
			action_button('add-privacy', __('Add'), 'primary'),
		])
		+ data_table(
			['FERPA Restriction', 'Directory Consent', 'Restriction Scope', 'Effective From', 'Effective To', 'Source'],
			(records.privacy || []).map((row) => [
				row.ferpa_restriction ? status_badge('Restricted') : status_badge('Not Restricted'),
				text_value(row.directory_information_consent), text_value(row.restriction_scope),
				date_value(row.effective_from), date_value(row.effective_to), text_value(row.consent_source),
			]),
			__('No privacy preferences recorded.'),
		));
	set_html(frm, 'talisma_documents_html',
		action_bar(__('Assign documents for students to upload from their portal.'), [
			action_button('add-document', __('Add Document'), 'primary'),
		])
		+ data_table(
			['Document', 'Required', 'Due Date', 'Status', 'Uploaded', 'File', 'Actions'],
			(records.documents || []).map((row) => [
				`<strong>${escape_html(text_value(row.document_type))}</strong>`,
				row.required ? __('Yes') : __('No'), date_value(row.due_date), status_badge(row.status),
				date_value(row.uploaded_on),
				row.document_file ? `<a href="${escape_html(row.document_file)}" target="_blank" rel="noopener">${escape_html(__('View'))}</a>` : '&mdash;',
				inline_actions([
					row.status === 'Submitted' ? record_action_button('verify-document', __('Verify'), row.name) : '',
					row.status === 'Submitted' ? record_action_button('reject-document', __('Reject'), row.name) : '',
					['Missing', 'Overdue'].includes(row.status) ? record_action_button('waive-document', __('Waive'), row.name) : '',
					record_action_button('open-document-record', __('Full Record'), row.name),
				]),
			]),
			__('No student documents have been assigned.'),
		));
	set_html(frm, 'talisma_status_history_html',
		`<div class="talisma-academic-profile-panel">${action_bar(__('Effective-dated lifecycle changes for this student.'), [])
		+ data_table(
			['Status', 'Reason', 'Academic Term', 'Effective From', 'Effective To', 'Source'],
			(records.statuses || []).map((row) => [
				record_link('Talisma Student Status History', row.name, row.status), text_value(row.reason),
				text_value(row.academic_term), date_value(row.effective_from), date_value(row.effective_to), text_value(row.source),
			]),
			__('No status history found.'),
		)}</div>`);
}

function advisor_scope(row) {
	if (!row.program && !row.academic_unit_name) return '&mdash;';
	const program = row.program || __('All Programs');
	const academicUnit = row.academic_unit_name || __('All Academic Units');
	return `<div class="talisma-360-identity"><strong>${escape_html(program)}</strong><small>${escape_html(academicUnit)}</small></div>`;
}

function render_degree_audit(frm, audit) {
	if (!audit.available) {
		set_html(frm, 'talisma_degree_audit_html', empty_html(audit.message || __('No degree audit is available.')));
		return;
	}
	const summary = audit.summary || {};
	const progress = Number(summary.progress_percent || 0);
	const curriculumButton = record_link(
		'Talisma Curriculum Version',
		audit.curriculum_version,
		audit.version_label || audit.curriculum_version,
	);
	set_html(
		frm,
		'talisma_degree_audit_html',
		action_bar(
			__('Progress is calculated from curriculum requirements and authoritative course attempts.'),
			[curriculumButton],
		)
		+ stat_grid([
			['Curriculum', audit.version_label],
			['Catalog Year', audit.catalog_year],
			['Completed Credits', number_value(summary.completed_credits, 1)],
			['In-Progress Credits', number_value(summary.in_progress_credits, 1)],
			['Remaining Credits', number_value(summary.remaining_credits, 1)],
			['Requirements Completed', `${summary.completed_requirements || 0} / ${summary.total_requirements || 0}`],
			['Graduation Eligible', summary.graduation_eligible ? status_badge('Eligible') : status_badge('Not Yet Eligible')],
		])
		+ `<div class="talisma-degree-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
			<div class="talisma-degree-progress__label"><span>${escape_html(__('Degree Progress'))}</span><strong>${progress.toFixed(1)}%</strong></div>
			<div class="talisma-degree-progress__track"><span style="width:${Math.min(100, Math.max(0, progress))}%"></span></div>
		</div>`
		+ data_table(
			['Requirement', 'Type', 'Target', 'Minimum Grade', 'Earned Credits', 'Status'],
			(audit.requirements || []).map((row) => [
				`<div class="talisma-360-identity"><strong>${escape_html(row.name)}</strong><small>${escape_html(row.code)}</small></div>`,
				text_value(row.type),
				requirement_target(row),
				text_value(row.minimum_grade),
				number_value(row.earned_credits, 1),
				status_badge(row.status),
			]),
			__('No active curriculum requirements were found.'),
		),
	);
}

function render_enrollment(frm, enrollment) {
	if (enrollment.restricted) {
		set_html(frm, 'talisma_current_enrollment_html', restricted_html());
		set_html(frm, 'talisma_enrollment_history_html', restricted_html());
		return;
	}
	const current = enrollment.current;
	set_html(
		frm,
		'talisma_current_enrollment_html',
		current
			? stat_grid([
				['Academic Unit', current.academic_unit_name],
				['Program', current.program_name],
				['Curriculum Version', current.program_version],
				['Expected Start Date', date_value(current.expected_start_date)],
				['Student Start Date', date_value(current.student_start_date)],
				['Enrollment Status', status_badge(current.enrollment_status)],
			])
			: empty_html(__('No active program enrollment is linked to this student.')),
	);
	set_html(
		frm,
		'talisma_enrollment_history_html',
		'<div class="talisma-enrollment-panel">' +
			action_bar(
			__('Create and maintain program enrollments without losing the Student context.'),
			[action_button('new-enrollment', __('Enroll Student'), 'primary')],
		) +
			data_table(
				['Program', 'Academic Unit', 'Academic Period', 'Status', 'Actions'],
				enrollment.records.map((row) => [
					enrollment_program_identity(row),
					`<strong>${escape_html(text_value(row.academic_unit_name))}</strong>`,
					enrollment_academic_period(row),
					enrollment_status_summary(row),
					row.docstatus === 0
						? inline_actions([record_action_button('edit-enrollment', __('Edit'), row.name)])
						: `<span class="talisma-360-readonly-state">${escape_html(__('Submitted'))}</span>`,
				]),
				__('No program enrollments found.'),
			) +
		'</div>',
	);
}

function render_courses(frm, registration) {
	if (registration.restricted) {
		set_html(frm, 'talisma_course_registration_html', restricted_html());
		return;
	}
	set_html(
		frm,
		'talisma_course_registration_html',
		'<div class="talisma-course-registration-panel">' +
		action_bar(
			__('Register, change sections, drop, or withdraw without leaving this Student Profile.'),
			[action_button('register-courses', __('Register Courses'), 'primary')],
		) +
			data_table(
				['Course', 'Registration', 'Academic Period', 'Progress', 'Section', 'Actions'],
				registration.records.map((row) => [
					course_identity(row),
					course_registration_summary(row),
					course_academic_period(row),
					course_progress_summary(row),
					`<strong>${escape_html(text_value(row.section))}</strong>`,
					course_lifecycle_actions(row),
				]),
				__('No course registrations found.'),
			) +
		'</div>',
	);
}

function render_finance(frm, finance) {
	if (finance.restricted) {
		[
			'talisma_fee_structure_html',
			'talisma_fee_details_html',
			'talisma_payment_summary_html',
			'talisma_payment_history_html',
			'talisma_scholarships_html',
			'talisma_waivers_html',
			'talisma_refunds_html',
		].forEach((fieldname) => set_html(frm, fieldname, restricted_html()));
		return;
	}
	const summary = finance.summary || {};
	set_html(
		frm,
		'talisma_payment_summary_html',
		action_bar(
			__('Live values from submitted billing, payment, refund, and accounting records.'),
			[
				action_button('student-account-statement', __('Account Statement'), 'primary'),
				action_button('student-billing-report', __('Billing Report')),
			],
		) + stat_grid([
			['Total Charges', money(summary.total_charges, summary.currency)],
			['Total Payments', money(summary.total_payments, summary.currency)],
			['Total Scholarships', money(summary.total_scholarships, summary.currency)],
			['Total Waivers', money(summary.total_waivers, summary.currency)],
			['Total Refunds', money(summary.total_refunds, summary.currency)],
			['Outstanding Balance', money(summary.outstanding_balance, summary.currency)],
			['Last Payment Date', date_value(summary.last_payment_date)],
			['Next Due Date', date_value(summary.next_due_date)],
		]),
	);
	set_html(
		frm,
		'talisma_fee_structure_html',
		action_bar(
			__('Billing Statements are backed by ERPNext accounting records.'),
			[action_button('student-billing-report', __('Open Billing Statements'))],
		) +
			data_table(
				['Billing Statement', 'Program', 'Academic Period', 'Posting Date', 'Due Date', 'Status', 'Billed Amount', 'Outstanding Balance'],
				(finance.billing_statements || []).filter((row) => !row.is_refund).map((row) => [
					`<strong>${escape_html(text_value(row.name))}</strong>`,
					escape_html(text_value(row.program)),
					escape_html([row.academic_year, row.academic_term].filter(Boolean).join(' · ') || '—'),
					date_value(row.posting_date), date_value(row.due_date), status_badge(row.billing_status),
					money(row.net_charge, row.currency), money(row.outstanding_balance, row.currency),
				]),
				__('No Billing Statements found.'),
			) +
			data_table(
				['Billing Statement', 'Fee Category', 'Description', 'Amount', 'Scholarship Adjustment', 'Waiver Adjustment', 'Net Charge'],
				(finance.billing_components || []).filter((row) => !row.is_refund).map((row) => [
					escape_html(text_value(row.billing_statement)), escape_html(text_value(row.fee_category)),
					escape_html(text_value(row.description)), money(row.amount, row.currency),
					money(row.scholarship_adjustment, row.currency), money(row.waiver_adjustment, row.currency),
					money(row.net_charge, row.currency),
				]),
				__('No billed charge components found.'),
			),
	);
	set_html(
		frm,
		'talisma_fee_details_html',
		action_bar(__('Receipts and allocations from submitted Student Payments.'), [
			action_button('student-payment-report', __('Payment Report')),
		]) + data_table(
			['Payment Date', 'Payment Method', 'Reference Number', 'Amount Paid', 'Receipt Number', 'Status'],
			(finance.student_payments || []).filter((row) => row.payment_type !== 'Pay').map((row) => [
				date_value(row.payment_date), escape_html(text_value(row.payment_method)),
				escape_html(text_value(row.reference_number)), money(row.amount_paid, row.currency),
				`<strong>${escape_html(text_value(row.receipt_number))}</strong>`, status_badge(row.status),
			]),
			__('No Student Payments found.'),
		),
	);
	set_html(
		frm,
		'talisma_payment_history_html',
		data_table(
			['Date', 'Description', 'Activity', 'Charge', 'Credit', 'Balance'],
			(finance.account_activity || []).map((row) => [
				date_value(row.date), escape_html(text_value(row.description)), status_badge(row.activity_type),
				row.charge ? money(row.charge, row.currency) : '—',
				row.credit ? money(row.credit, row.currency) : '—', money(row.balance, row.currency),
			]),
			__('No account activity found.'),
		),
	);
	set_html(
		frm,
		'talisma_scholarships_html',
		data_table(
			['Date', 'Billing Statement', 'Fee Category', 'Description', 'Amount', 'Source'],
			(finance.scholarships || []).map((row) => [
				date_value(row.posting_date), escape_html(text_value(row.billing_statement)),
				escape_html(text_value(row.fee_category)), escape_html(text_value(row.description)),
				money(row.amount, row.currency), escape_html(text_value(row.source)),
			]),
			__('No scholarship adjustments found.'),
		),
	);
	set_html(
		frm,
		'talisma_waivers_html',
		empty_html(__('No waiver adjustments found. Waivers remain an accounting-backed extension point; no separate balance is maintained.')),
	);
	set_html(
		frm,
		'talisma_refunds_html',
		data_table(
			['Date', 'Refund', 'Original Billing Statement', 'Amount', 'Status'],
			(finance.refunds || []).map((row) => [
				date_value(row.posting_date), `<strong>${escape_html(text_value(row.name))}</strong>`,
				escape_html(text_value(row.return_against)), money(row.amount, row.currency), status_badge(row.status),
			]),
			__('No refunds found.'),
		),
	);
}

function bind_360_actions(frm) {
	frm.$wrapper.off('click.student360').on(
		'click.student360',
		'[data-student-action]',
		(event) => {
			const { studentAction: action, doctype, name } = event.currentTarget.dataset;
			if (action === 'open-record') {
				frappe.set_route('Form', doctype, name);
			} else if (action === 'open-document-record') {
				open_student_document_record_dialog(frm, name);
			} else if (action === 'new-enrollment') {
				open_program_enrollment_dialog(frm);
			} else if (action === 'edit-enrollment') {
				open_program_enrollment_dialog(frm, name);
			} else if (action === 'student-account-statement') {
				open_student_finance_report('Student Account Statement', frm.doc.name);
			} else if (action === 'student-billing-report') {
				open_student_finance_report('Student Billing Report', frm.doc.name);
			} else if (action === 'student-payment-report') {
				open_student_finance_report('Student Payment Report', frm.doc.name);
			} else if (action === 'register-courses') {
				open_student_registration_dialog(frm);
			} else if (action === 'course-actions') {
				open_course_action_dialog(frm, name);
			} else if (action === 'add-hold') {
				open_student_hold_dialog(frm);
			} else if (action === 'add-privacy') {
				open_privacy_preference_dialog(frm);
			} else if (action === 'add-advisor') {
				open_advisor_dialog(frm);
			} else if (action === 'edit-advisor') {
				open_advisor_dialog(frm, name);
			} else if (action === 'end-advisor') {
				end_advisor_assignment(frm, name);
			} else if (action === 'add-document') {
				open_student_document_dialog(frm);
			} else if (action === 'verify-document') {
				review_student_document(frm, name, 'Verified');
			} else if (action === 'reject-document') {
				reject_student_document(frm, name);
			} else if (action === 'waive-document') {
				review_student_document(frm, name, 'Waived');
			} else if (action === 'drop-course') {
				change_course_status(frm, name, 'Drop');
			} else if (action === 'withdraw-course') {
				change_course_status(frm, name, 'Withdraw');
			} else if (action === 'swap-section') {
				open_swap_section_dialog(frm, name);
			} else if (action === 'new-linked') {
				frappe.new_doc(doctype, { student: frm.doc.name });
			} else if (action === 'view-linked') {
				frappe.set_route('List', doctype, { student: frm.doc.name });
			}
		},
	);
}

function open_student_finance_report(report_name, student) {
	frappe.route_options = { student };
	frappe.set_route('query-report', report_name);
}

function with_student_action_context(frm, callback) {
	if (frm.student_action_context) {
		callback(frm.student_action_context);
		return;
	}
	frappe.call({
		method: 'talisma_sis.student_workflows.get_student_action_context',
		args: { student: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			frm.student_action_context = r.message;
			callback(r.message);
		},
	});
}

function open_advisor_dialog(frm, assignmentName = null) {
	with_student_action_context(frm, (context) => {
		const row = (frm.student_360?.student_records?.advisors || [])
			.find((item) => item.name === assignmentName) || {};
		let dialog;
		dialog = new frappe.ui.Dialog({
			title: assignmentName ? __('Edit Advisor Assignment') : __('Add Advisor'),
			fields: [
				{ fieldtype: 'HTML', options: student_context_html(frm) },
				{ fieldname: 'advisor', label: __('Advisor'), fieldtype: 'Link', options: 'Instructor', reqd: 1, default: row.advisor },
				{ fieldname: 'advisor_type', label: __('Advisor Type'), fieldtype: 'Select', options: ['Academic', 'Faculty', 'International Student', 'Athletic', 'Student Success'], reqd: 1, default: row.advisor_type || 'Academic' },
				{
					fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program', default: row.program || context.program,
					onchange() {
						const program = dialog.get_value('program');
						if (!program) return;
						frappe.db.get_value('Program', program, 'talisma_academic_unit').then((r) => {
							dialog.set_value('academic_unit', r.message?.talisma_academic_unit || null);
						});
					},
				},
				{ fieldname: 'academic_unit', label: __('Academic Unit'), fieldtype: 'Link', options: 'Talisma Academic Unit', default: row.academic_unit },
				{ fieldname: 'primary_advisor', label: __('Primary Advisor'), fieldtype: 'Check', default: row.primary_advisor ?? 1 },
				{ fieldname: 'status', label: __('Status'), fieldtype: 'Select', options: ['Active', 'Ended'], reqd: 1, default: row.status || 'Active' },
				{ fieldname: 'effective_from', label: __('Effective From'), fieldtype: 'Date', reqd: 1, default: row.effective_from || context.today },
				{ fieldname: 'effective_to', label: __('Effective To'), fieldtype: 'Date', default: row.effective_to, depends_on: "eval:doc.status == 'Ended'" },
				{ fieldname: 'end_reason', label: __('End Reason'), fieldtype: 'Small Text', default: row.end_reason, depends_on: "eval:doc.status == 'Ended'" },
			],
			primary_action_label: assignmentName ? __('Save Changes') : __('Assign Advisor'),
			primary_action(values) {
				frappe.call({
					method: 'talisma_sis.student_workflows.save_advisor_assignment',
					args: { student: frm.doc.name, assignment: assignmentName, values },
					freeze: true,
					freeze_message: __('Saving advisor assignment...'),
					callback(r) {
						if (!r.message) return;
						dialog.hide();
						frappe.show_alert({ message: __('Advisor assignment saved'), indicator: 'green' });
						load_student_360(frm);
					},
				});
			},
		});
		dialog.fields_dict.advisor.get_query = () => ({ filters: { status: 'Active' } });
		dialog.show();
	});
}

function end_advisor_assignment(frm, assignmentName) {
	frappe.prompt(
		[
			{ fieldname: 'effective_to', label: __('Effective To'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.get_today() },
			{ fieldname: 'end_reason', label: __('End Reason'), fieldtype: 'Small Text', reqd: 1 },
		],
		(values) => {
			frappe.call({
				method: 'talisma_sis.student_workflows.save_advisor_assignment',
				args: {
					student: frm.doc.name,
					assignment: assignmentName,
					values: { status: 'Ended', effective_to: values.effective_to, end_reason: values.end_reason },
				},
				freeze: true,
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({ message: __('Advisor assignment ended'), indicator: 'green' });
					load_student_360(frm);
				},
			});
		},
		__('End Advisor Assignment'),
		__('End Assignment'),
	);
}

function open_student_document_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Add Student Document'),
		fields: [
			{ fieldtype: 'HTML', options: student_context_html(frm) },
			{
				fieldname: 'document_type', label: __('Document Type'), fieldtype: 'Link',
				options: 'Talisma Student Document Type', reqd: 1,
				get_query: () => ({ filters: { active: 1 } }),
			},
			{ fieldname: 'required', label: __('Required'), fieldtype: 'Check', default: 1 },
			{ fieldname: 'due_date', label: __('Due Date'), fieldtype: 'Date' },
		],
		primary_action_label: __('Add Document'),
		primary_action(values) {
			frappe.call({
				method: 'talisma_sis.student_documents.assign_document_requirement',
				args: { student: frm.doc.name, ...values },
				freeze: true,
				freeze_message: __('Adding student document...'),
				callback(r) {
					if (!r.message) return;
					dialog.hide();
					frappe.show_alert({ message: __('Student document added'), indicator: 'green' });
					load_student_360(frm);
				},
			});
		},
	});
	dialog.show();
}

function open_student_document_record_dialog(frm, documentName) {
	frappe.call({
		method: 'talisma_sis.student_documents.get_student_document',
		args: { document: documentName },
		freeze: true,
		freeze_message: __('Loading student document...'),
		callback(r) {
			if (!r.message) return;
			const record = r.message;
			const dialog = new frappe.ui.Dialog({
				title: __('Student Document'),
				size: 'large',
				fields: [
					{ fieldtype: 'HTML', options: student_context_html(frm) },
					{ fieldname: 'document_type', label: __('Document Type'), fieldtype: 'Data', read_only: 1 },
					{ fieldname: 'required', label: __('Required'), fieldtype: 'Check' },
					{ fieldname: 'due_date', label: __('Due Date'), fieldtype: 'Date' },
					{
						fieldname: 'status', label: __('Status'), fieldtype: 'Select', reqd: 1,
						options: 'Missing\nOverdue\nSubmitted\nVerified\nRejected\nExpired\nWaived',
					},
					{ fieldname: 'document_file', label: __('Uploaded Document'), fieldtype: 'Attach' },
					{ fieldname: 'expiry_date', label: __('Expiry Date'), fieldtype: 'Date' },
					{ fieldtype: 'Section Break', label: __('Review and Notes') },
					{ fieldname: 'rejection_reason', label: __('Rejection Reason'), fieldtype: 'Small Text' },
					{ fieldname: 'notes', label: __('Internal Notes'), fieldtype: 'Small Text' },
					{ fieldtype: 'Section Break', label: __('Audit Information') },
					{ fieldname: 'uploaded_by', label: __('Uploaded By'), fieldtype: 'Data', read_only: 1 },
					{ fieldname: 'uploaded_on', label: __('Uploaded On'), fieldtype: 'Datetime', read_only: 1 },
					{ fieldtype: 'Column Break' },
					{ fieldname: 'verified_by', label: __('Reviewed By'), fieldtype: 'Data', read_only: 1 },
					{ fieldname: 'verified_on', label: __('Reviewed On'), fieldtype: 'Datetime', read_only: 1 },
				],
				primary_action_label: __('Save'),
				primary_action(values) {
					frappe.call({
						method: 'talisma_sis.student_documents.update_student_document',
						args: {
							document: documentName,
							required: values.required,
							due_date: values.due_date,
							status: values.status,
							document_file: values.document_file,
							expiry_date: values.expiry_date,
							rejection_reason: values.rejection_reason,
							notes: values.notes,
						},
						freeze: true,
						freeze_message: __('Saving student document...'),
						callback(saveResponse) {
							if (!saveResponse.message) return;
							dialog.hide();
							frappe.show_alert({ message: __('Student document updated'), indicator: 'green' });
							load_student_360(frm);
						},
					});
				},
			});
			dialog.show();
			dialog.set_values(record);
		},
	});
}

function open_student_hold_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Add Administrative Hold'),
		fields: [
			{ fieldtype: 'HTML', options: student_context_html(frm) },
			{ fieldname: 'hold_type', label: __('Hold Type'), fieldtype: 'Select', options: ['Advising', 'Financial', 'Registrar', 'Disciplinary', 'Health', 'International Student', 'Other'], reqd: 1 },
			{ fieldname: 'reason', label: __('Hold Reason'), fieldtype: 'Small Text', reqd: 1 },
			{ fieldname: 'owning_department', label: __('Owning Department'), fieldtype: 'Link', options: 'Department' },
			{ fieldname: 'effective_from', label: __('Effective From'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.get_today() },
			{ fieldname: 'effective_to', label: __('Effective To'), fieldtype: 'Date' },
			{ fieldtype: 'Section Break', label: __('Blocked Activities') },
			{ fieldname: 'blocks_registration', label: __('Registration'), fieldtype: 'Check', default: 1 },
			{ fieldname: 'blocks_transcript', label: __('Transcript'), fieldtype: 'Check' },
			{ fieldname: 'blocks_graduation', label: __('Graduation'), fieldtype: 'Check' },
			{ fieldname: 'blocks_financial_activity', label: __('Financial Activity'), fieldtype: 'Check' },
		],
		primary_action_label: __('Add Hold'),
		primary_action(values) {
			frappe.call({
				method: 'talisma_sis.student_workflows.add_student_hold',
				args: { student: frm.doc.name, values },
				freeze: true,
				freeze_message: __('Adding administrative hold...'),
				callback(r) {
					if (!r.message) return;
					dialog.hide();
					frappe.show_alert({ message: __('Administrative hold added'), indicator: 'green' });
					load_student_360(frm);
				},
			});
		},
	});
	dialog.show();
}

function open_privacy_preference_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Add FERPA & Privacy Preference'),
		fields: [
			{ fieldtype: 'HTML', options: student_context_html(frm) },
			{ fieldname: 'ferpa_restriction', label: __('FERPA Restriction'), fieldtype: 'Check' },
			{ fieldname: 'directory_information_consent', label: __('Directory Information Consent'), fieldtype: 'Select', options: ['Not Recorded', 'Granted', 'Restricted', 'Revoked'], reqd: 1, default: 'Not Recorded' },
			{ fieldname: 'restriction_scope', label: __('Restriction Scope'), fieldtype: 'Small Text', depends_on: 'eval:doc.ferpa_restriction == 1' },
			{ fieldname: 'effective_from', label: __('Effective From'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.get_today() },
			{ fieldname: 'effective_to', label: __('Effective To'), fieldtype: 'Date' },
			{ fieldname: 'consent_source', label: __('Consent Source'), fieldtype: 'Select', options: ['Student Portal', 'Signed Form', 'Registrar', 'System Migration'], default: 'Registrar' },
			{ fieldname: 'consent_document', label: __('Consent Document'), fieldtype: 'Attach' },
			{ fieldname: 'emergency_disclosure_permission', label: __('Emergency Disclosure Permission'), fieldtype: 'Check' },
		],
		primary_action_label: __('Add Preference'),
		primary_action(values) {
			frappe.call({
				method: 'talisma_sis.student_workflows.add_privacy_preference',
				args: { student: frm.doc.name, values },
				freeze: true,
				freeze_message: __('Saving privacy preference...'),
				callback(r) {
					if (!r.message) return;
					dialog.hide();
					frappe.show_alert({ message: __('Privacy preference added'), indicator: 'green' });
					load_student_360(frm);
				},
			});
		},
	});
	dialog.show();
}

function review_student_document(frm, documentName, status, rejectionReason = null) {
	frappe.call({
		method: 'talisma_sis.student_documents.review_student_document',
		args: { document: documentName, status, rejection_reason: rejectionReason },
		freeze: true,
		callback(r) {
			if (!r.message) return;
			frappe.show_alert({ message: __('Document status updated'), indicator: 'green' });
			load_student_360(frm);
		},
	});
}

function reject_student_document(frm, documentName) {
	frappe.prompt(
		[{ fieldname: 'reason', label: __('Rejection Reason'), fieldtype: 'Small Text', reqd: 1 }],
		(values) => review_student_document(frm, documentName, 'Rejected', values.reason),
		__('Reject Student Document'),
		__('Reject'),
	);
}

function open_program_enrollment_dialog(frm, enrollmentName = null) {
	with_student_action_context(frm, (context) => {
		const row = (frm.student_360?.enrollment?.records || [])
			.find((item) => item.name === enrollmentName) || {};
		let dialog;
		dialog = new frappe.ui.Dialog({
			title: enrollmentName ? __('Edit Program Enrollment') : __('Enroll Student in Program'),
			fields: [
				{ fieldtype: 'HTML', options: student_context_html(frm) },
				{
					fieldname: 'program', label: __('Program'), fieldtype: 'Link', options: 'Program', reqd: 1, default: row.program || null,
					onchange() {
						const program = dialog.get_value('program');
						if (!program) return;
						frappe.db.get_value('Talisma Curriculum Version', { program, status: 'Published' }, 'name').then((r) => {
							dialog.set_value('talisma_curriculum_version', r.message?.name || null);
						});
					},
				},
				{ fieldname: 'talisma_curriculum_version', label: __('Curriculum Version'), fieldtype: 'Link', options: 'Talisma Curriculum Version', reqd: 1, default: row.program_version || null },
				{ fieldname: 'academic_year', label: __('Academic Year'), fieldtype: 'Link', options: 'Academic Year', reqd: 1, default: row.academic_year || null },
				{ fieldname: 'academic_term', label: __('Academic Term'), fieldtype: 'Link', options: 'Academic Term', default: row.academic_term || null },
				{ fieldname: 'talisma_campus', label: __('Campus'), fieldtype: 'Link', options: 'Talisma Campus', default: row.campus || null },
				{ fieldname: 'enrollment_date', label: __('Enrollment Date'), fieldtype: 'Date', reqd: 1, default: row.student_start_date || context.today },
			],
			primary_action_label: enrollmentName ? __('Save Changes') : __('Create Enrollment'),
			primary_action(values) {
				frappe.call({
					method: 'talisma_sis.student_workflows.save_program_enrollment',
					args: { student: frm.doc.name, program_enrollment: enrollmentName, values },
					freeze: true,
					freeze_message: __('Saving program enrollment...'),
					callback(r) {
						if (!r.message) return;
						dialog.hide();
						frappe.show_alert({ message: __('Program enrollment saved'), indicator: 'green' });
						frm.student_action_context = null;
						load_student_360(frm);
					},
				});
			},
		});
		dialog.fields_dict.talisma_curriculum_version.get_query = () => ({
			filters: { program: dialog.get_value('program'), status: 'Published' },
		});
		dialog.fields_dict.academic_term.get_query = () => ({
			filters: { academic_year: dialog.get_value('academic_year') },
		});
		dialog.show();
	});
}

function change_course_status(frm, enrollmentName, action) {
	frappe.prompt(
		[
			{ fieldname: 'effective_date', label: __('Effective Date'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.get_today() },
			{ fieldname: 'reason', label: __('Reason'), fieldtype: 'Small Text', reqd: 1 },
		],
		(values) => {
			frappe.call({
				method: 'talisma_sis.registrar.change_course_enrollment_status',
				args: { student: frm.doc.name, course_enrollment: enrollmentName, action, ...values },
				freeze: true,
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({ message: action === 'Drop' ? __('Course dropped') : __('Course withdrawn'), indicator: 'green' });
					load_student_360(frm);
				},
			});
		},
		__(`${action} Course`),
		__(action),
	);
}

function open_swap_section_dialog(frm, enrollmentName) {
	const row = (frm.student_360?.course_registration?.records || [])
		.find((item) => item.name === enrollmentName);
	if (!row?.program_enrollment) return;
	frappe.call({
		method: 'talisma_sis.registrar.get_section_options',
		args: { program_enrollment: row.program_enrollment },
		callback(r) {
			const options = (r.message?.sections || [])
				.filter((section) => section.course === row.course_code && section.name !== row.course_section && !section.registered)
				.map((section) => ({
					label: `${section.course} &middot; CRN ${section.talisma_crn} &middot; ${section.talisma_meeting_days || ''} ${section.talisma_start_time || ''}`,
					value: section.name,
				}));
			if (!options.length) {
				frappe.msgprint(__('No other open sections are available for this course.'));
				return;
			}
			const dialog = new frappe.ui.Dialog({
				title: __('Swap Course Section'),
				fields: [
					{ fieldtype: 'HTML', options: student_context_html(frm) },
					{ fieldname: 'new_section', label: __('New Section'), fieldtype: 'Select', options, reqd: 1 },
				],
				primary_action_label: __('Swap Section'),
				primary_action(values) {
					frappe.call({
						method: 'talisma_sis.registrar.swap_course_section',
						args: { student: frm.doc.name, course_enrollment: enrollmentName, new_section: values.new_section },
						freeze: true,
						callback(result) {
							if (!result.message) return;
							dialog.hide();
							frappe.show_alert({ message: __('Course section changed'), indicator: 'green' });
							load_student_360(frm);
						},
					});
				},
			});
			dialog.show();
		},
	});
}

function open_student_registration_dialog(frm) {
	const enrollment = frm.student_360?.enrollment?.current;
	if (!enrollment) {
		frappe.msgprint(__('Create an active Program Enrollment before registering courses.'));
		return;
	}
	frappe.call({
		method: 'talisma_sis.registrar.get_section_options',
		args: { program_enrollment: enrollment.name },
		callback(r) {
			const response = r.message || {};
			if (!(response.terms || []).length) {
				frappe.msgprint(__('No academic terms with eligible course sections are available.'));
				return;
			}
			let dialog;
			dialog = new frappe.ui.Dialog({
				title: __('Register Courses'),
				fields: [
					{ fieldtype: 'HTML', options: student_context_html(frm) },
					{
						fieldname: 'academic_term',
						label: __('Academic Term'),
						fieldtype: 'Select',
						options: response.terms,
						default: response.academic_term,
						reqd: 1,
						onchange() {
							const academicTerm = dialog?.get_value('academic_term');
							if (academicTerm) load_registration_sections(dialog, enrollment.name, academicTerm);
						},
					},
					{
						fieldname: 'sections',
						label: __('Open Course Sections'),
						fieldtype: 'MultiCheck',
						columns: 1,
						options: registration_section_options(response.sections),
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
						args: {
							program_enrollment: enrollment.name,
							sections: values.sections,
						},
						freeze: true,
						freeze_message: __('Registering courses...'),
						callback(result) {
							if (!result.message) return;
							dialog.hide();
							frappe.show_alert({
								message: __('Course registration completed'),
								indicator: 'green',
							});
							load_student_360(frm);
						},
					});
				},
			});
			dialog.show();
			update_registration_section_field(dialog, response.sections);
		},
	});
}

function load_registration_sections(dialog, programEnrollment, academicTerm) {
	frappe.call({
		method: 'talisma_sis.registrar.get_section_options',
		args: { program_enrollment: programEnrollment, academic_term: academicTerm },
		freeze: true,
		freeze_message: __('Loading course sections...'),
		callback(r) {
			update_registration_section_field(dialog, r.message?.sections || []);
		},
	});
}

function update_registration_section_field(dialog, sections) {
	const field = dialog.fields_dict.sections;
	field.df.options = registration_section_options(sections);
	field.df.description = field.df.options.length
		? __('Select one or more course sections offered in this term.')
		: __('No additional open course sections are available for this term.');
	dialog.set_value('sections', []);
	field.refresh();
}

function registration_section_options(sections) {
	return (sections || [])
		.filter((section) => !section.registered)
		.map((section) => ({
			label: `${section.course} · CRN ${section.talisma_crn} · ${section.talisma_meeting_days || ''} ${section.talisma_start_time || ''}`,
			value: section.name,
		}));
}

function set_html(frm, fieldname, html) {
	frm.fields_dict[fieldname]?.$wrapper.html(html);
}

function action_bar(message, buttons) {
	return `<div class="talisma-360-actionbar"><span>${escape_html(message)}</span><div>${buttons.join('')}</div></div>`;
}

function action_button(action, label, style = 'default') {
	return `<button type="button" class="btn btn-${style} btn-sm" data-student-action="${action}">${escape_html(label)}</button>`;
}

function linked_action_bar(message, doctype) {
	return action_bar(message, [
		linked_action_button('new-linked', __('Add'), doctype, 'primary'),
		linked_action_button('view-linked', __('Open List'), doctype),
	]);
}

function linked_action_button(action, label, doctype, style = 'default') {
	return '<button type="button" class="btn btn-' + style + ' btn-sm" data-student-action="'
		+ escape_html(action) + '" data-doctype="' + escape_html(doctype) + '">'
		+ escape_html(label) + '</button>';
}

function record_action_button(action, label, name, doctype = '', style = 'default') {
	return '<button type="button" class="btn btn-' + style + ' btn-xs" data-student-action="'
		+ escape_html(action) + '" data-name="' + escape_html(name || '') + '" data-doctype="'
		+ escape_html(doctype) + '">' + escape_html(label) + '</button>';
}

function inline_actions(buttons) {
	return `<div class="talisma-360-inline-actions">${buttons.filter(Boolean).join('')}</div>`;
}

function record_link(doctype, name, label) {
	if (!name) return '—';
	return `<button type="button" class="talisma-360-link" data-student-action="open-record" data-doctype="${escape_html(doctype)}" data-name="${escape_html(name)}">${escape_html(label || name)}</button>`;
}

function course_identity(row) {
	return `<div class="talisma-360-identity"><strong>${escape_html(text_value(row.course_name))}</strong><small>${escape_html(text_value(row.course_code))}</small></div>`;
}

function course_lifecycle_actions(row) {
	return row.completion_status === 'In Progress'
		? inline_actions([record_action_button('course-actions', __('Action'), row.name, '', 'primary')])
		: `<span class="talisma-360-readonly-state">${escape_html(__('No actions available'))}</span>`;
}

function course_registration_summary(row) {
	return `<div class="talisma-360-detail-stack"><strong>${escape_html(__('Attempt'))} ${escape_html(text_value(row.attempt_number))}</strong><small>${escape_html(text_value(row.credit_hours))} ${escape_html(__('Credits'))}</small></div>`;
}

function course_academic_period(row) {
	return `<div class="talisma-360-detail-stack"><strong>${escape_html(text_value(row.effective_term))}</strong><small>${escape_html(__('Registered'))}: ${escape_html(date_value(row.registration_date))}</small></div>`;
}

function course_progress_summary(row) {
	const grade = row.grade
		? `${row.grade}${row.grade_points === null || row.grade_points === undefined ? '' : ` · ${row.grade_points} ${__('points')}`}`
		: __('Not graded');
	return `<div class="talisma-360-status-summary">${status_badge(row.completion_status)}<small>${escape_html(__('Grade'))}: <strong>${escape_html(grade)}</strong></small></div>`;
}

function open_course_action_dialog(frm, enrollmentName) {
	const row = (frm.student_360?.course_registration?.records || [])
		.find((item) => item.name === enrollmentName);
	if (!row) return;
	const options = [];
	if (row.course_section) options.push({ label: __('Change Section'), value: 'Change Section' });
	options.push(
		{ label: __('Drop Course'), value: 'Drop' },
		{ label: __('Withdraw from Course'), value: 'Withdraw' },
	);
	const dialog = new frappe.ui.Dialog({
		title: __('Course Action'),
		fields: [
			{ fieldtype: 'HTML', options: student_context_html(frm) },
			{
				fieldtype: 'HTML',
				options: `<div class="talisma-dialog-record-summary"><span>${escape_html(__('Course'))}</span><strong>${escape_html(text_value(row.course_name))}</strong><small>${escape_html(text_value(row.course_code))} · ${escape_html(text_value(row.effective_term))} · ${escape_html(__('Section'))} ${escape_html(text_value(row.section))}</small></div>`,
			},
			{ fieldname: 'action', label: __('Action'), fieldtype: 'Select', options, reqd: 1 },
		],
		primary_action_label: __('Continue'),
		primary_action(values) {
			dialog.hide();
			if (values.action === 'Change Section') {
				open_swap_section_dialog(frm, enrollmentName);
			} else if (values.action === 'Drop') {
				change_course_status(frm, enrollmentName, 'Drop');
			} else if (values.action === 'Withdraw') {
				change_course_status(frm, enrollmentName, 'Withdraw');
			}
		},
	});
	dialog.show();
}

function student_context_html(frm) {
	return `<div class="talisma-dialog-context"><span>${escape_html(__('Student'))}</span><strong>${escape_html(frm.doc.student_name || frm.doc.name)}</strong><small>${escape_html(frm.doc.name)}</small></div>`;
}

function grade_identity(row) {
	if (!row.grade) return '—';
	const points = row.grade_points === null || row.grade_points === undefined
		? ''
		: ' · ' + row.grade_points + ' ' + __('points');
	return '<strong>' + escape_html(row.grade) + '</strong><small class="talisma-360-grade-points">' + escape_html(points) + '</small>';
}

function enrollment_program_identity(row) {
	const version = row.program_version
		? `${escape_html(__('Curriculum'))}: ${escape_html(row.program_version)}`
		: escape_html(__('No curriculum version'));
	return `<div class="talisma-360-identity"><strong>${escape_html(text_value(row.program_name))}</strong><small>${version}</small></div>`;
}

function enrollment_academic_period(row) {
	return `<div class="talisma-360-identity talisma-360-period"><strong>${escape_html(text_value(row.academic_term))}</strong><small>${escape_html(__('Start Date'))}: ${escape_html(date_value(row.student_start_date))}</small></div>`;
}

function enrollment_status_summary(row) {
	const type = row.primary_program ? __('Primary Program') : __('Additional Program');
	return `<div class="talisma-360-status-summary">${status_badge(row.enrollment_status)}<small>${escape_html(type)}</small></div>`;
}

function stat_grid(items) {
	return `<div class="talisma-360-stats">${items
		.map(([label, value]) => `<div><span>${escape_html(__(label))}</span><strong>${value && String(value).startsWith('<') ? value : escape_html(text_value(value))}</strong></div>`)
		.join('')}</div>`;
}

function data_table(headers, rows, empty_message) {
	if (!rows.length) return empty_html(empty_message);
	return `<div class="talisma-360-table-wrap"><table class="table table-bordered talisma-360-table">
		<thead><tr>${headers.map((header) => `<th>${escape_html(__(header))}</th>`).join('')}</tr></thead>
		<tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
	</table></div>`;
}

function status_badge(status) {
	if (!status) return '—';
	const normalized = String(status).toLowerCase();
	const tone = normalized.includes('cancel')
		? 'red'
		: (normalized.includes('not started') || normalized.includes('not yet')
			? 'gray'
			: (normalized.includes('outstanding') || normalized.includes('planned') || normalized.includes('progress') ? 'orange' : 'green'));
	return `<span class="indicator-pill ${tone}">${escape_html(status)}</span>`;
}

function money(value, currency) {
	if (value === null || value === undefined) return '—';
	return frappe.format(value, {
		fieldtype: 'Currency',
		options: currency || frappe.defaults.get_default('currency'),
	});
}

function date_value(value) {
	return value ? frappe.datetime.str_to_user(value) : '—';
}

function text_value(value) {
	return value === null || value === undefined || value === '' ? '—' : String(value);
}

function number_value(value, precision) {
	if (value === null || value === undefined || value === '') return '—';
	return Number(value).toFixed(precision);
}

function hold_blocks(row) {
	const labels = [];
	if (row.blocks_registration) labels.push(__('Registration'));
	if (row.blocks_transcript) labels.push(__('Transcript'));
	if (row.blocks_graduation) labels.push(__('Graduation'));
	if (row.blocks_financial_activity) labels.push(__('Financial Activity'));
	return labels.length ? labels.join(', ') : '—';
}

function requirement_target(row) {
	if (row.type === 'Required Course') return text_value(row.course);
	if (row.type === 'Course Group') {
		return `${text_value(row.course_category)} (${row.minimum_courses || 0} ${__('courses')})`;
	}
	return `${number_value(row.minimum_credits, 1)} ${__('credits')}`;
}

function empty_html(message) {
	return `<div class="talisma-360-empty">${escape_html(message)}</div>`;
}

function restricted_html() {
	return empty_html(__('You do not have permission to view these linked records.'));
}

function loading_html() {
	return empty_html(__('Loading student information…'));
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value ?? ''));
}
