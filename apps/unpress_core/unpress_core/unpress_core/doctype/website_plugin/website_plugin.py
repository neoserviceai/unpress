import frappe
from frappe.model.document import Document

from unpress_core import plugins


class WebsitePlugin(Document):
	def on_update(self):
		# the route guard reads this on every request from cache
		plugins.clear_cache()
		frappe.cache().delete_value("unpress_plugin_blocked_routes")
		# a plugin that just took over (or released) a public route changes what
		# the site serves
		frappe.clear_cache()

	def on_trash(self):
		plugins.clear_cache()
		frappe.cache().delete_value("unpress_plugin_blocked_routes")
