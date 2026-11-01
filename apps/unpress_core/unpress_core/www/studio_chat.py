import frappe


def get_context(context):
	context.no_cache = 1
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/studio-chat"
		raise frappe.Redirect
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context
