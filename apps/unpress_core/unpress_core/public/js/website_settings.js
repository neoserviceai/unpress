// Client script for Website Settings: show link to Website Header Footer Config
frappe.ui.form.on("Website Settings", {
	refresh(frm) {
		frm.set_intro(
			__('Menu and theme are managed in {0}.',
				['<a href="/app/website-header-footer-config">' + __('Website Header Footer Config') + '</a>']
			),
			'blue'
		);
	}
});
