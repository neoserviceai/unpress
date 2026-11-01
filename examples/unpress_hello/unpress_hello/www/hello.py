"""The public page at /hello.

Two things a plugin page must do, and both are easy to forget:
  1. 404 when the plugin is off — the route guard does it centrally, but a page
     that can also be reached directly should check too;
  2. wear the site's chrome, so it does not read as a different website.
"""

import frappe

from unpress_hello.plugin import is_enabled


def get_context(context):
	if not is_enabled():
		raise frappe.DoesNotExistError

	context.no_cache = 1
	context.title = frappe._("Hello")

	# The shared page header (breadcrumb + title) is drawn by the site, above
	# this page's content. Set this to False only if the page opens on a
	# composition of its own — otherwise you get two titles stacked.
	context.show_page_header = True
	return context
