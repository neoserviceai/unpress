import frappe
from werkzeug.exceptions import abort
from werkzeug.utils import redirect as _redirect


def set_home_after_login(login_manager):
	"""Land studio users in the Studio instead of the raw Frappe desk."""
	if frappe.session.user == "Guest":
		return
	if {"System Manager", "Website Manager"} & set(frappe.get_roles()):
		frappe.local.response["home_page"] = "/builder"


# Every way into the Frappe desk. /desk is the legacy alias and it does NOT
# go through /app — left out, it served the whole desk (594 KB of it) to
# anyone who typed the URL.
DESK_ROOTS = ("/app", "/apps", "/desk")


def desk_redirect():
	"""One-interface principle: the Studio user never sees the Frappe desk.

	Every desk entry point redirects to the Builder. Escape hatch for
	maintenance: **/desk?desk=1** — not /app?desk=1, because frappe answers
	/app with its own 301 to /desk and drops the query string on the way,
	so the flag never survives to the second request.

	frappe.redirect() only works inside website routes (path_resolver catches
	frappe.Redirect); in a before_request hook it surfaces as "Server Error
	301". An aborted werkzeug redirect becomes the response in app.py's
	HTTPException branch, which works for every route type including /app.
	"""
	path = frappe.request.path if frappe.request else ""
	if not any(path == root or path.startswith(root + "/") for root in DESK_ROOTS):
		return
	if frappe.form_dict.get("desk") == "1":
		return
	abort(_redirect("/builder"))
