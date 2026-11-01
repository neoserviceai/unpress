"""The page a visitor lands on when the address is wrong — or not built yet.

Frappe's own 404 blocks the navbar and the footer, so it arrives as a bare
sentence on a grey field: the visitor loses the site at the exact moment they
need a way back into it.

It also cannot tell apart the two things that produce a 404 on a young site.
One is a wrong address. The other is a link the site deliberately carries for a
section that is coming — the shop menu on an Unpress site, which the generator
writes because the site will have one. That second case deserves a different
sentence and no apology.
"""

import frappe
from frappe import _

no_cache = 1

# Routes an app we have not installed yet will own. The generator writes these
# links on purpose, so the site keeps them and says what they are.
RESERVED = {
	"all-products": {"app": "webshop", "label": "Shop"},
	"cart": {"app": "webshop", "label": "Cart"},
	"orders": {"app": "webshop", "label": "Orders"},
	"wishlist": {"app": "webshop", "label": "Wishlist"},
	"me": {"app": "webshop", "label": "My Account"},
}


def _translatable_labels():
	"""Extraction markers — never called. Keep in sync with RESERVED."""
	_("Shop")
	_("Cart")
	_("Orders")
	_("Wishlist")
	_("My Account")


def get_context(context):
	path = (frappe.request.path if frappe.request else "").strip("/")
	root = path.split("/", 1)[0] if path else ""

	reserved = RESERVED.get(root)
	if reserved:
		try:
			installed = set(frappe.get_installed_apps())
		except Exception:
			installed = set()
		# once the app is really there, a 404 under its route is a genuine 404
		if reserved["app"] in installed:
			reserved = None

	context.no_cache = 1
	# This page is its own opening statement, centred on the page: the shared
	# band above it would print the same words a second time.
	context.show_page_header = False
	context.is_reserved = bool(reserved)
	context.reserved_label = _(reserved["label"]) if reserved else ""
	context.title = _("Coming soon") if reserved else _("Page not found")

	# the menu, so the visitor has somewhere to go from here
	try:
		from unpress_core.hf_utils.header_footer import get_header_footer_config

		config = get_header_footer_config()
		context.menu_items = list(config.menu_items or []) if config else []
	except Exception:
		context.menu_items = []

	return context
