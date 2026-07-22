frappe.ui.form.on('Talisma Class Section', {
	setup(frm) {
		// CRN is a server-generated institutional identifier, not user input.
		frm.set_df_property('talisma_crn', 'reqd', false);
		frm.set_query('academic_term', () => ({ filters: { term_end_date: ['>=', frappe.datetime.get_today()] } }));
		frm.set_query('talisma_primary_instructor', () => ({ filters: { status: 'Active' } }));
		bind_weekday_picker(frm);
		$(frm.wrapper).on('grid-row-render.talisma-weekdays', (event, grid_row) => {
			style_weekday_cell(grid_row);
		});
	},
	onload(frm) {
		if (frm.is_new()) {
			frm.set_value('talisma_delivery_method', frm.doc.talisma_delivery_method || 'In Person');
			frm.set_value('talisma_section_status', frm.doc.talisma_section_status || 'Planned');
		}
	},
	refresh(frm) {
		frm.set_df_property('talisma_crn', 'reqd', false);
		frm.set_df_property('talisma_waitlist_capacity', 'reqd', Boolean(frm.doc.talisma_allow_waitlist));
		setTimeout(() => {
			(frm.fields_dict.talisma_periods?.grid?.grid_rows || []).forEach((grid_row) => {
				style_weekday_cell(grid_row);
			});
		}, 0);
	},
	academic_term(frm) {
		if (!frm.doc.academic_term) return;
		frappe.db.get_value('Academic Term', frm.doc.academic_term, ['term_start_date', 'term_end_date']).then((r) => {
			if (!frm.doc.talisma_class_start_date) frm.set_value('talisma_class_start_date', r.message?.term_start_date);
			if (!frm.doc.talisma_class_end_date) frm.set_value('talisma_class_end_date', r.message?.term_end_date);
		});
	},
	talisma_allow_waitlist(frm) {
		frm.set_df_property('talisma_waitlist_capacity', 'reqd', Boolean(frm.doc.talisma_allow_waitlist));
		if (!frm.doc.talisma_allow_waitlist) frm.set_value('talisma_waitlist_capacity', 0);
	},
	validate(frm) {
		if (Number(frm.doc.max_strength || 0) <= 0) frappe.throw(__('Capacity must be greater than zero.'));
		if (frm.doc.talisma_allow_waitlist && Number(frm.doc.talisma_waitlist_capacity || 0) <= 0) frappe.throw(__('Waitlist Capacity must be greater than zero.'));
		if (frm.doc.talisma_class_start_date && frm.doc.talisma_class_end_date && frm.doc.talisma_class_start_date > frm.doc.talisma_class_end_date) frappe.throw(__('Class Start Date must be on or before Class End Date.'));
	},
});

frappe.ui.form.on('Talisma Class Period', {
	talisma_periods_add(frm, cdt, cdn) {
		setTimeout(() => {
			const grid_row = frm.fields_dict.talisma_periods?.grid?.grid_rows_by_docname?.[cdn];
			style_weekday_cell(grid_row);
		}, 0);
	},
	start_time(frm, cdt, cdn) { validate_period(cdt, cdn); },
	end_time(frm, cdt, cdn) { validate_period(cdt, cdn); },
});

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function bind_weekday_picker(frm) {
	if (frm.__talisma_weekday_picker_bound) return;
	frm.__talisma_weekday_picker_bound = true;

	const open_from_event = (event) => {
		const cell = event.target.closest?.('.grid-row [data-fieldname="days"]');
		if (!cell || !frm.wrapper.contains(cell)) return;
		if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;

		const grid_row = $(cell).closest('.grid-row').data('grid_row');
		if (!grid_row?.doc || grid_row.doc.doctype !== 'Talisma Class Period') return;

		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation();
		open_weekday_picker(frm, grid_row.doc.doctype, grid_row.doc.name);
	};

	// Capture the event before Frappe turns this grid cell into a text editor.
	frm.wrapper.addEventListener('click', open_from_event, true);
	frm.wrapper.addEventListener('keydown', open_from_event, true);
}

function style_weekday_cell(grid_row) {
	if (!grid_row || grid_row.doc?.doctype !== 'Talisma Class Period') return;

	const $cell = grid_row.wrapper.find('[data-fieldname="days"]');
	const display_value = String(grid_row.doc.days || '').replace(/\n+/g, ', ');
	$cell
		.attr('role', 'button')
		.attr('tabindex', '0')
		.attr('title', __('Click to select meeting days'))
		.css('cursor', 'pointer');
	$cell.find('.static-area')
		.text(display_value || __('Select days'))
		.toggleClass('text-muted', !display_value);
}

function open_weekday_picker(frm, cdt, cdn) {
	const row = locals[cdt]?.[cdn];
	if (!row) return;

	const selected = new Set(
		String(row.days || '')
			.split(/[,\n]+/)
			.map((day) => day.trim())
			.filter(Boolean)
	);
	const dialog = new frappe.ui.Dialog({
		title: __('Select Meeting Days'),
		fields: [{
			fieldname: 'days',
			fieldtype: 'MultiCheck',
			label: __('Days'),
			columns: 1,
			sort_options: false,
			options: WEEKDAYS.map((day) => ({
				label: __(day),
				value: day,
				checked: selected.has(day),
			})),
		}],
		primary_action_label: __('Apply'),
		primary_action(values) {
			const days = Array.isArray(values.days) ? values.days : [];
			if (!days.length) {
				frappe.msgprint(__('Select at least one meeting day.'));
				return;
			}
			const ordered_days = WEEKDAYS.filter((day) => days.includes(day));
			frappe.model.set_value(cdt, cdn, 'days', ordered_days.join(', ')).then(() => {
				dialog.hide();
				frm.refresh_field('talisma_periods');
			});
		},
	});
	dialog.show();
}

function validate_period(cdt, cdn) {
	const row = locals[cdt][cdn];
	if (row.start_time && row.end_time && row.end_time <= row.start_time) {
		frappe.model.set_value(cdt, cdn, 'end_time', null);
		frappe.msgprint(__('Period End Time must be later than Start Time.'));
	}
}
