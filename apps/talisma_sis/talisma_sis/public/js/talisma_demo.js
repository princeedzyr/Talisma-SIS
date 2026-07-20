frappe.ready(() => {
	document.body.classList.add('talisma-sis-demo');
	if (!document.title.startsWith('Talisma SIS')) document.title = 'Talisma SIS | ' + document.title;
	const navbar = document.querySelector('.navbar .container');
	if (navbar && !navbar.querySelector('.talisma-brand')) {
		const brand = document.createElement('div');
		brand.className = 'talisma-brand';
		brand.innerHTML = '<img src="/assets/talisma_sis/talisma-mark.svg" alt=""><span>Talisma SIS</span>';
		navbar.prepend(brand);
	}
});
