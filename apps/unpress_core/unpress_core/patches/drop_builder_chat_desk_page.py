import frappe


def execute():
	"""The AI chat now lives in the builder SPA, not in a desk page.

	The Studio bounces /app to /builder anyway, so this page was already
	unreachable — but removing the files leaves the record behind.
	"""
	if frappe.db.exists("Page", "builder-chat"):
		frappe.delete_doc("Page", "builder-chat", force=True, ignore_missing=True)
