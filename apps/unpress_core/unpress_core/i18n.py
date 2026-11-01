# Translation catalog for the Studio frontend.
# The Vue app has no build-time locale bundle: it asks for the catalog of the
# logged-in user's language at boot (cached client-side). Same contract as the
# other Frappe SPAs (lms, insights, mail).
import frappe


@frappe.whitelist(allow_guest=True)
def get_translations() -> dict:
	"""Every installed app's messages for the current language, merged."""
	language = frappe.local.lang or frappe.db.get_default("lang") or "en"
	if language == "en":
		# nothing to send: the source strings ARE English
		return {}
	return frappe.translate.get_all_translations(language)
