frappe.ui.form.on('Program', {
	refresh(frm) {
		frm.toggle_display('department', false);
		frm.toggle_display('courses', false);
		frm.toggle_display('program_name', true);
		frm.set_df_property('program_name', 'read_only', !frm.is_new());
		render_curriculum_requirements(frm);
	},

	talisma_default_curriculum_version(frm) {
		render_curriculum_requirements(frm);
	},
});

function render_curriculum_requirements(frm) {
	const field = frm.fields_dict.talisma_curriculum_requirements_html;
	if (!field) return;
	const wrapper = field.$wrapper;
	if (frm.is_new() || !frm.doc.name) {
		wrapper.html(empty_state(__('Save the Program to display its curriculum requirements.')));
		return;
	}

	wrapper.html(empty_state(__('Loading curriculum requirements…')));
	frappe.call({
		method: 'talisma_sis.curriculum.get_program_curriculum_requirements',
		args: { program: frm.doc.name },
		callback(r) {
			const data = r.message || {};
			if (!data.version) {
				wrapper.html(empty_state(__('No Curriculum Version is linked to this Program.')));
				return;
			}
			wrapper.html(curriculum_table(data));
		},
		error() {
			wrapper.html(empty_state(__('Unable to load curriculum requirements.')));
		},
	});
}

function curriculum_table(data) {
	const esc = (value) => frappe.utils.escape_html(String(value == null ? '' : value));
	const version = data.version;
	const rows = data.requirements || [];
	const heading = `
		<div class="d-flex flex-wrap align-items-center justify-content-between mb-3" style="gap: 8px;">
			<div>
				<div class="text-muted small">${data.is_default ? __('Selected Default Curriculum Version') : __('Linked Curriculum Version')}</div>
				<div class="font-weight-bold">${esc(version.version_label || version.name)}</div>
			</div>
			<div class="text-muted small">${esc(version.catalog_year)} · ${esc(version.status)}</div>
		</div>`;
	if (!rows.length) return heading + empty_state(__('No curriculum requirements are defined in this version.'));

	const body = rows.map((row, index) => `
		<tr>
			<td>${index + 1}</td>
			<td>${esc(row.requirement_code)}</td>
			<td>${esc(row.requirement_type)}</td>
			<td>${esc(row.course || '—')}</td>
			<td>${esc(row.sequence)}</td>
			<td>${row.active ? `<span class="indicator-pill green">${__('Active')}</span>` : `<span class="indicator-pill gray">${__('Inactive')}</span>`}</td>
		</tr>`).join('');
	return `${heading}
		<div class="talisma-academics-table-wrap">
			<table class="table talisma-academics-table">
				<thead><tr>
					<th>${__('No.')}</th>
					<th>${__('Requirement Code')}</th>
					<th>${__('Requirement Type')}</th>
					<th>${__('Course Name')}</th>
					<th>${__('Sequence')}</th>
					<th>${__('Active')}</th>
				</tr></thead>
				<tbody>${body}</tbody>
			</table>
		</div>`;
}

function empty_state(message) {
	return `<div class="text-muted border rounded text-center p-4">${frappe.utils.escape_html(message)}</div>`;
}
