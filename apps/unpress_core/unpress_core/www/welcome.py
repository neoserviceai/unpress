"""The front door of a site that has no pages yet.

Frappe falls back to the login form when `Website Settings.home_page` is empty,
which is what a fresh install has. Measured on a from-scratch install: the root
of a brand-new site served `<title>Login</title>`. That is wrong twice over — a
visitor who was given the address sees an administration form and learns
nothing, and the owner sees a product that opens on a password box rather than
on a website.

This page holds the root until there is something to put there. Generation sets
`home_page` to the site's real home, so it takes over on its own and this is
never seen again.
"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	context.no_cache = 1
	# It is its own opening statement, centred: the shared band would print the
	# same words a second time.
	context.show_page_header = False
	context.title = _("Coming soon")

	# Offer the way in only to whoever can actually use it. A visitor does not
	# need to be told where the administration lives.
	context.can_build = frappe.session.user != "Guest"
	return context
