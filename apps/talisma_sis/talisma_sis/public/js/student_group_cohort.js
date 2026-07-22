frappe.ui.form.on('Student Group', {
	refresh(frm) {
		frm.set_intro(
			__('Student Groups are logical groups for cohorts, advising, activities, scholarships, and communication. Course sections and instructors belong in Class Scheduling.'),
			'blue'
		);
		renderSelectionGrid(frm, frm.__cohort_candidates || []);
	},

	validate(frm) {
		if (frm.doc.group_based_on === 'Course' || frm.doc.course) {
			frappe.throw(__('Student Groups are logical cohorts. Use Class Scheduling for course sections.'));
		}
		const seen = new Set();
		for (const row of frm.doc.students || []) {
			if (row.student && seen.has(row.student)) {
				frappe.throw(__('Student {0} is already a member of this group.', [row.student]));
			}
			if (row.student) seen.add(row.student);
		}
	},

	talisma_load_students(frm) {
		const filters = {
			talisma_cohort_campus: frm.doc.talisma_cohort_campus,
			academic_year: frm.doc.academic_year,
			academic_term: frm.doc.academic_term,
			talisma_academic_unit: frm.doc.talisma_academic_unit,
			program: frm.doc.program,
		};
		if (!Object.values(filters).some(Boolean)) {
			frappe.msgprint(__('Select at least one filter before loading students.'));
			return;
		}
		frappe.call({
			method: 'talisma_sis.class_scheduling.get_cohort_students',
			args: filters,
			freeze: true,
			freeze_message: __('Loading active students…'),
			callback(r) {
				frm.__cohort_candidates = r.message || [];
				renderSelectionGrid(frm, frm.__cohort_candidates);
			},
		});
	},

	talisma_add_selected_students(frm) {
		const selected = Array.from(
			frm.fields_dict.talisma_cohort_selection_html.$wrapper.find('.cohort-student-select:checked')
		).map((input) => input.value);
		const existing = new Set((frm.doc.students || []).map((row) => row.student));
		let added = 0;
		for (const student of frm.__cohort_candidates || []) {
			if (!selected.includes(student.student) || existing.has(student.student)) continue;
			const row = frm.add_child('students');
			row.student = student.student;
			row.student_name = student.student_name;
			row.talisma_program = student.program || frm.doc.program;
			row.talisma_academic_term = student.academic_term || frm.doc.academic_term;
			row.talisma_enrollment_status = student.enrollment_status || '';
			row.active = 1;
			existing.add(student.student);
			added += 1;
		}
		frm.refresh_field('students');
		frappe.show_alert({ message: __('{0} student(s) added to Group Members.', [added]), indicator: 'green' });
	},
});

function renderSelectionGrid(frm, students) {
	const field = frm.fields_dict.talisma_cohort_selection_html;
	if (!field) return;
	const existing = new Set((frm.doc.students || []).map((row) => row.student));
	const rows = students.map((student) => `
		<tr>
			<td><input type="checkbox" class="cohort-student-select" value="${frappe.utils.escape_html(student.student)}" ${existing.has(student.student) ? 'disabled' : ''}></td>
			<td><a href="/app/student/${encodeURIComponent(student.student)}" target="_blank">${frappe.utils.escape_html(student.student)}</a></td>
			<td>${frappe.utils.escape_html(student.student_name || '')}</td>
			<td>${frappe.utils.escape_html(student.program || '—')}</td>
			<td>${frappe.utils.escape_html(student.academic_term || '—')}</td>
			<td>${frappe.utils.escape_html(student.enrollment_status || 'Active')}</td>
		</tr>
	`).join('');
	field.$wrapper.html(`
		<div class="cohort-selection-panel">
			<div class="row cohort-selection-filters">
				<div class="col-sm-4" data-cohort-filter="talisma_cohort_campus"></div>
				<div class="col-sm-4" data-cohort-filter="academic_year"></div>
				<div class="col-sm-4" data-cohort-filter="academic_term"></div>
				<div class="col-sm-4" data-cohort-filter="talisma_academic_unit"></div>
				<div class="col-sm-4" data-cohort-filter="program"></div>
			</div>
			<div class="cohort-selection-toolbar">
				<button class="btn btn-primary btn-sm cohort-load-students">${__('Load Students')}</button>
				<button class="btn btn-default btn-sm cohort-add-students">${__('Add Selected Students')}</button>
				<span class="text-muted cohort-selection-count">${students.length} ${__('matching students')}</span>
			</div>
			<div class="cohort-selection-table-wrapper">
				<table class="table table-bordered table-hover">
					<thead><tr><th>${__('Select')}</th><th>${__('Student Number')}</th><th>${__('Student Name')}</th><th>${__('Program')}</th><th>${__('Academic Term')}</th><th>${__('Enrollment Status')}</th></tr></thead>
					<tbody>${rows || `<tr><td colspan="6" class="text-muted">${__('Choose filters and click Load Students.')}</td></tr>`}</tbody>
				</table>
			</div>
		</div>
	`);
	mountSelectionFilters(frm, field.$wrapper);
	field.$wrapper.find('.cohort-load-students').on('click', () => frm.trigger('talisma_load_students'));
	field.$wrapper.find('.cohort-add-students').on('click', () => frm.trigger('talisma_add_selected_students'));
}

function mountSelectionFilters(frm, wrapper) {
	const filters = [
		{ fieldname: 'talisma_cohort_campus', label: __('Campus'), options: 'Talisma Campus' },
		{ fieldname: 'academic_year', label: __('Academic Year'), options: 'Academic Year' },
		{ fieldname: 'academic_term', label: __('Academic Term'), options: 'Academic Term' },
		{ fieldname: 'talisma_academic_unit', label: __('Academic Unit'), options: 'Talisma Academic Unit' },
		{ fieldname: 'program', label: __('Program'), options: 'Program' },
	];
	frm.__cohort_filter_controls = {};
	for (const filter of filters) {
		const parent = wrapper.find(`[data-cohort-filter="${filter.fieldname}"]`).get(0);
		if (!parent) continue;
		let control;
		control = frappe.ui.form.make_control({
			parent,
			df: {
				fieldtype: 'Link',
				fieldname: filter.fieldname,
				label: filter.label,
				options: filter.options,
				onchange: () => frm.set_value(filter.fieldname, control.get_value()),
			},
			render_input: true,
		});
		control.set_value(frm.doc[filter.fieldname] || '');
		frm.__cohort_filter_controls[filter.fieldname] = control;
	}
}
