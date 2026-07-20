frappe.ui.form.on('Degree', {
	refresh(frm) {
		if (frm.is_new()) {
			render_degree_programs(frm, []);
			return;
		}
		frappe.call({
			method: 'talisma_sis.academics.get_degree_programs',
			args: { degree: frm.doc.name },
			callback: (r) => render_degree_programs(frm, r.message || []),
		});
	},
});

function render_degree_programs(frm, programs) {
	const wrapper = frm.fields_dict.programs_html?.$wrapper;
	if (!wrapper) return;
	if (!programs.length) {
		wrapper.html('<div class="talisma-academics-empty">' + __('No Programs are linked to this Degree.') + '</div>');
		return;
	}
	const rows = programs.map((row) => '<tr>'
		+ '<td>' + escape_degree_value(row.program_code) + '</td>'
		+ '<td><a href="/desk/program/' + encodeURIComponent(row.name) + '">' + escape_degree_value(row.program_name) + '</a></td>'
		+ '<td>' + escape_degree_value(row.program_abbreviation) + '</td>'
		+ '</tr>').join('');
	wrapper.html('<div class="talisma-academics-table-wrap"><table class="table talisma-academics-table">'
		+ '<thead><tr><th>' + __('Program Code') + '</th><th>' + __('Program Name')
		+ '</th><th>' + __('Program Abbreviation') + '</th></tr></thead><tbody>'
		+ rows + '</tbody></table></div>');
}

function escape_degree_value(value) {
	return frappe.utils.escape_html(String(value || '—'));
}
