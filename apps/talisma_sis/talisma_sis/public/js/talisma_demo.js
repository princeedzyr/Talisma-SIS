const TALISMA_MODULES = {
	Admissions: 'Manage applications, inquiries and admissions process.',
	'Student Records': 'Maintain student profiles, documents and history.',
	Registrar: 'Handle registration, courses and academic terms.',
	Academics: 'Manage curriculum, programs and academic structure.',
	'Faculty & Sections': 'Manage faculty information and class sections.',
	'Assessment & Grades': 'Create assessments and manage grades.',
	Attendance: 'Track attendance and student participation.',
	Reports: 'Generate reports and gain insights.',
};

const TALISMA_ACTIONS = [
	['New Applicant', 'Create and review an admission application', ['List', 'Student Applicant']],
	['Find a Student', 'Open the central student record', ['List', 'Student']],
	['Course Registration', 'Open a student 360 record to manage registration', ['List', 'Student']],
	['Academic Results', 'View grades and assessment outcomes', ['List', 'Assessment Result']],
];

const TALISMA_WORKSPACE_ROUTE = '/desk/bryan-university';
const TALISMA_SITES = new Set(['talisma.local', 'demo.talisma.local']);

if (TALISMA_SITES.has(frappe.boot?.sitename)) {
	document.body.classList.add('talisma-sis-demo');
}

function is_talisma_desktop() {
	return window.location.pathname.replace(/\/$/, '') === '/desk';
}

function create_element(class_name, html) {
	const element = document.createElement('section');
	element.className = class_name;
	element.innerHTML = html;
	return element;
}

function decorate_module_icons(grid, icons) {
	grid.classList.add('talisma-module-grid');
	icons.forEach((icon) => {
		const label = icon.dataset.id;
		icon.classList.add('talisma-module-card');
		if (!icon.querySelector('.talisma-module-description')) {
			const description = document.createElement('div');
			description.className = 'talisma-module-description';
			description.textContent = TALISMA_MODULES[label] || 'Open module';
			icon.append(description);
		}
	});
}

function make_dashboard_header() {
	return create_element(
		'talisma-dashboard-header',
		`<div class="talisma-dashboard-heading">
			<div>
				<h1>Welcome back!</h1>
				<p>Manage your institution with ease</p>
			</div>
		</div>`,
	);
}

function make_quick_actions() {
	const cards = TALISMA_ACTIONS.map(
		([title, description], index) =>
			`<button class="talisma-action-card" type="button" data-action="${index}">
				<span class="talisma-action-arrow">→</span>
				<strong>${title}</strong><small>${description}</small>
			</button>`,
	).join('');
	const section = create_element(
		'talisma-dashboard-lower',
		`<div class="talisma-quick-actions">
			<div class="talisma-section-heading"><div><span>Quick Actions</span><h2>Continue your work</h2></div></div>
			<div class="talisma-action-grid">${cards}</div>
		</div>
		<aside class="talisma-status-card">
			<div class="talisma-status-icon">✓</div>
			<div><span>Demo environment</span><h2>Ready for presentation</h2>
			<p>Fall 2026 sample data is loaded. Access remains controlled by Frappe roles and permissions.</p></div>
		</aside>`,
	);
	section.querySelectorAll('[data-action]').forEach((button) => {
		button.addEventListener('click', () => {
			const action = TALISMA_ACTIONS[Number(button.dataset.action)];
			frappe.set_route(...action[2]);
		});
	});
	return section;
}

function load_dashboard_summary(header) {
	if (header.dataset.loaded === '1') return;
	header.dataset.loaded = '1';
	frappe.call('talisma_sis.demo.dashboard_summary').then(({ message }) => {
		Object.entries(message || {}).forEach(([key, value]) => {
			const field = header.querySelector(`[data-summary="${key}"]`);
			if (field) field.textContent = Number(value).toLocaleString();
		});
	}).catch(() => {
		header.querySelectorAll('[data-summary]').forEach((field) => (field.textContent = '—'));
	});
}

function render_talisma_dashboard() {
	if (!is_talisma_desktop()) return;
	const icons = [...document.querySelectorAll('a.desktop-icon')].filter(
		(icon) => TALISMA_MODULES[icon.dataset.id],
	);
	if (icons.length !== Object.keys(TALISMA_MODULES).length) return;
	const grid = icons[0].parentElement;
	if (!grid) return;
	decorate_module_icons(grid, icons);
	grid.parentElement?.classList.add('talisma-desktop-home');

	let header = document.querySelector('.talisma-dashboard-header');
	if (!header) {
		header = make_dashboard_header();
		grid.before(header);
	}
	if (!document.querySelector('.talisma-dashboard-lower')) grid.after(make_quick_actions());
}

function schedule_talisma_dashboard() {
	window.setTimeout(render_talisma_dashboard, 80);
	window.setTimeout(render_talisma_dashboard, 350);
}

function align_form_tab_to_top() {
	const main_section = document.querySelector('.main-section');
	if (main_section) main_section.scrollTo({ top: 0, behavior: 'auto' });
	window.scrollTo({ top: 0, behavior: 'auto' });
}

function align_university_workspace_to_top() {
	if (window.location.pathname.replace(/\/$/, '') !== TALISMA_WORKSPACE_ROUTE) return;
	window.requestAnimationFrame(() => {
		const main_section = document.querySelector('.main-section');
		if (main_section) main_section.scrollTo({ top: 0, behavior: 'auto' });
		window.scrollTo({ top: 0, behavior: 'auto' });
	});
}

function visible_field_input(control) {
	const inputs = control.querySelectorAll(
		'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [contenteditable="true"]',
	);
	return [...inputs].find((input) => input.getClientRects().length > 0);
}

function horizontal_field_order(root) {
	const ordered_inputs = [];
	const sections = [...root.querySelectorAll('.form-section')].filter(
		(section) => section.getClientRects().length > 0,
	);

	sections.forEach((section) => {
		const columns = [...section.querySelectorAll('.form-column')].filter(
			(column) =>
				column.closest('.form-section') === section && column.getClientRects().length > 0,
		);
		const column_inputs = columns.map((column) =>
			[...column.querySelectorAll('.frappe-control[data-fieldname]')]
				.filter(
					(control) =>
						control.closest('.form-column') === column &&
						!control.closest('.grid-row') &&
						control.getClientRects().length > 0,
				)
				.map(visible_field_input)
				.filter(Boolean),
		);
		const longest_column = Math.max(0, ...column_inputs.map((inputs) => inputs.length));

		for (let row = 0; row < longest_column; row += 1) {
			column_inputs.forEach((inputs) => {
				if (inputs[row]) ordered_inputs.push(inputs[row]);
			});
		}
	});

	return ordered_inputs;
}

function move_to_horizontal_field(event) {
	if (
		event.key !== 'Tab' ||
		event.defaultPrevented ||
		event.altKey ||
		event.ctrlKey ||
		event.metaKey
	) return;

	const control = event.target.closest?.('.frappe-control[data-fieldname]');
	if (!control || control.closest('.grid-row')) return;
	const root = control.closest('.form-page, .modal-content');
	if (!root) return;

	const inputs = horizontal_field_order(root);
	const current_index = inputs.findIndex(
		(input) => input === event.target || input.closest('.frappe-control') === control,
	);
	const next_input = inputs[current_index + (event.shiftKey ? -1 : 1)];
	if (current_index < 0 || !next_input) return;

	event.preventDefault();
	next_input.focus();
	if (typeof next_input.select === 'function' && next_input.matches('input, textarea')) {
		next_input.select();
	}
}

frappe.ready(() => {
	if (!TALISMA_SITES.has(frappe.boot?.sitename)) return;
	if (is_talisma_desktop()) {
		window.location.replace(TALISMA_WORKSPACE_ROUTE);
		return;
	}

	document.body.classList.add('talisma-sis-demo');
	if (!document.title.startsWith('Bryan University')) document.title = 'Bryan University | ' + document.title;
	const navbar = document.querySelector('.navbar .container');
	if (navbar && !navbar.querySelector('.talisma-brand')) {
		const brand = document.createElement('div');
		brand.className = 'talisma-brand';
		brand.innerHTML = '<img src="/assets/talisma_sis/talisma-mark.svg" alt=""><span>Bryan University</span>';
		navbar.prepend(brand);
	}

	document.addEventListener('click', (event) => {
		if (!event.target.closest('.form-tabs .nav-link')) return;
		window.setTimeout(align_form_tab_to_top, 0);
	});
	document.addEventListener('keydown', move_to_horizontal_field);

	schedule_talisma_dashboard();
	align_university_workspace_to_top();
	frappe.router?.on('change', () => {
		schedule_talisma_dashboard();
		align_university_workspace_to_top();
	});
	new MutationObserver(schedule_talisma_dashboard).observe(document.body, {
		childList: true,
		subtree: true,
	});
});
