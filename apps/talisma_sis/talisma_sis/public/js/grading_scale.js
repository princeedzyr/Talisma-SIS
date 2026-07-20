frappe.ui.form.on('Grading Scale', {
	validate(frm) {
		validate_grade_definitions(frm);
	},
});

frappe.ui.form.on('Grading Scale Interval', {
	grade_code(frm) {
		validate_grade_definitions(frm, false);
	},
	threshold(frm) {
		validate_grade_definitions(frm, false);
	},
	talisma_maximum_score(frm) {
		validate_grade_definitions(frm, false);
	},
	talisma_grade_points(frm) {
		validate_grade_definitions(frm, false);
	},
});

function validate_grade_definitions(frm, throw_on_error = true) {
	const rows = frm.doc.intervals || [];
	const seen = new Map();
	const errors = [];

	for (const [index, row] of rows.entries()) {
		const rowNumber = index + 1;
		const letterGrade = (row.grade_code || '').trim();
		const gradeName = (row.grade_description || '').trim();
		const minimum = Number(row.threshold);
		const maximum = Number(row.talisma_maximum_score);
		const points = Number(row.talisma_grade_points);

		if (!letterGrade) errors.push(__('Row {0}: Letter Grade is required.', [rowNumber]));
		if (!gradeName) errors.push(__('Row {0}: Name is required.', [rowNumber]));
		const key = letterGrade.toLocaleLowerCase();
		if (letterGrade && seen.has(key)) {
			errors.push(__('Letter Grade {0} appears more than once (rows {1} and {2}).', [letterGrade, seen.get(key), rowNumber]));
		}
		seen.set(key, rowNumber);
		if (!Number.isFinite(minimum) || minimum < 0 || minimum > 100 || !Number.isFinite(maximum) || maximum < 0 || maximum > 100) {
			errors.push(__('Row {0}: scores must be between 0 and 100.', [rowNumber]));
		} else if (minimum > maximum) {
			errors.push(__('Row {0}: Minimum Score cannot be greater than Maximum Score.', [rowNumber]));
		}
		if (!Number.isFinite(points) || points < 0) {
			errors.push(__('Row {0}: Grade Points must be zero or greater.', [rowNumber]));
		}
	}

	const sorted = [...rows].sort((a, b) => Number(b.threshold || 0) - Number(a.threshold || 0));
	for (let index = 0; index < sorted.length - 1; index += 1) {
		const higher = sorted[index];
		const lower = sorted[index + 1];
		if (Number(lower.talisma_maximum_score) >= Number(higher.threshold)) {
			errors.push(__('Score ranges overlap: {0} ({1}–{2}) and {3} ({4}–{5}).', [
				higher.grade_code, higher.threshold, higher.talisma_maximum_score,
				lower.grade_code, lower.threshold, lower.talisma_maximum_score,
			]));
		}
	}

	if (errors.length && throw_on_error) frappe.throw(errors.join('<br>'));
	if (!errors.length && rows.some((row, index) => row.name !== sorted[index].name)) {
		frm.doc.intervals = sorted;
		frm.refresh_field('intervals');
	}
	return errors;
}
