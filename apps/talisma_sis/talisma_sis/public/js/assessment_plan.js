frappe.ui.form.on('Assessment Plan', {
	setup(frm) {
		frm.set_query('talisma_class_section', () => ({ filters: { disabled: 0 } }));
	},
	talisma_class_section(frm) {
		if (!frm.doc.talisma_class_section) return;
		frappe.db.get_value(
			'Talisma Class Section',
			frm.doc.talisma_class_section,
			['legacy_student_group', 'program', 'course', 'academic_year', 'academic_term']
		).then((r) => {
			const section = r.message || {};
			frm.set_value({
				student_group: section.legacy_student_group || frm.doc.talisma_class_section,
				program: section.program,
				course: section.course,
				academic_year: section.academic_year,
				academic_term: section.academic_term,
			});
		});
	},
	course(frm) {
		load_course_assessment_criteria(frm);
	},
	maximum_assessment_score(frm) {
		load_course_assessment_criteria(frm);
	},
	validate(frm) {
		const criteria = frm.doc.assessment_criteria || [];
		normalize_single_criterion(frm);
		const weightage = criteria.reduce((total, row) => total + Number(row.talisma_weightage || 0), 0);
		const maximum = criteria.reduce((total, row) => total + Number(row.maximum_score || 0), 0);
		if (criteria.length && Math.abs(weightage - 100) > 0.01) {
			frappe.throw(__('Assessment Criteria Weightage must total 100%. Current total: {0}%.', [weightage]));
		}
		if (Math.abs(maximum - Number(frm.doc.maximum_assessment_score || 0)) > 0.01) {
			frappe.throw(__('Criterion Maximum Scores must equal the Maximum Assessment Score.'));
		}
	},
});

frappe.ui.form.on('Assessment Plan Criteria', {
	assessment_criteria(frm) {
		normalize_single_criterion(frm);
	},
	talisma_weightage(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!Number(frm.doc.maximum_assessment_score || 0)) return;
		frappe.model.set_value(
			cdt,
			cdn,
			'maximum_score',
			Number(frm.doc.maximum_assessment_score) * Number(row.talisma_weightage || 0) / 100
		);
	},
});

function normalize_single_criterion(frm) {
	const criteria = frm.doc.assessment_criteria || [];
	if (criteria.length !== 1 || Number(criteria[0].talisma_weightage || 0)) return;
	criteria[0].talisma_weightage = 100;
	criteria[0].maximum_score = Number(frm.doc.maximum_assessment_score || 0);
	frm.refresh_field('assessment_criteria');
}

function load_course_assessment_criteria(frm) {
	if (!frm.doc.course || !Number(frm.doc.maximum_assessment_score || 0)) return;
	frappe.call({
		method: 'education.education.api.get_assessment_criteria',
		args: { course: frm.doc.course },
		callback(r) {
			if (!r.message?.length) return;
			frm.clear_table('assessment_criteria');
			for (const criterion of r.message) {
				const row = frm.add_child('assessment_criteria');
				row.assessment_criteria = criterion.assessment_criteria;
				row.talisma_weightage = criterion.weightage;
				row.maximum_score = Number(frm.doc.maximum_assessment_score) * Number(criterion.weightage) / 100;
			}
			frm.refresh_field('assessment_criteria');
		},
	});
}
