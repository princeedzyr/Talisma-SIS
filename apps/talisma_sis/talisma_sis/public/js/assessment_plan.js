frappe.ui.form.on('Assessment Plan', {
	course(frm) {
		load_course_assessment_criteria(frm);
	},
	maximum_assessment_score(frm) {
		load_course_assessment_criteria(frm);
	},
	validate(frm) {
		const criteria = frm.doc.assessment_criteria || [];
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
