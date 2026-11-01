# SSO for the mutualized edition: the portal (or control-plane) hands the
# customer a short-lived signed link that logs them straight into their own
# Studio site. HMAC over (site, expiry) with a per-site secret stored in
# site_config (`unpress_sso_secret`). No password ever transits.
import hashlib
import hmac
import time
from urllib.parse import urlencode

import frappe
from frappe import _


def _secret():
	# get_site_config() reads the file fresh (conf may be cached from boot)
	secret = frappe.conf.get("unpress_sso_secret") or frappe.get_site_config().get("unpress_sso_secret")
	if not secret:
		frappe.throw(_("SSO not configured for this site (unpress_sso_secret missing)"))
	return secret.encode()


def _sign(payload: str) -> str:
	return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_login_url(base_url: str, ttl_seconds: int = 120, redirect: str = "/builder") -> str:
	"""Build a signed one-time login URL. Call this in the site context whose
	secret should sign it (e.g. from a control-plane routine per tenant)."""
	expiry = int(time.time()) + ttl_seconds
	payload = f"{frappe.local.site}:{expiry}"
	params = {"token": payload, "sig": _sign(payload), "redirect": redirect}
	return f"{base_url.rstrip('/')}/api/method/unpress_core.sso.login?{urlencode(params)}"


@frappe.whitelist(allow_guest=True)
def login(token: str, sig: str, redirect: str = "/builder"):
	"""Verify a signed token and open an Administrator session, then redirect
	into the Studio. Runs in the target site's context (resolved by Host)."""
	# constant-time signature check
	if not hmac.compare_digest(_sign(token), sig or ""):
		raise frappe.PermissionError("Invalid SSO signature")

	try:
		site, expiry = token.rsplit(":", 1)
		expiry = int(expiry)
	except (ValueError, AttributeError):
		raise frappe.PermissionError("Malformed SSO token")

	if site != frappe.local.site:
		raise frappe.PermissionError("SSO token issued for another site")
	if time.time() > expiry:
		raise frappe.PermissionError("SSO link expired")

	# safe redirect: same-site absolute path only
	if not redirect.startswith("/") or redirect.startswith("//"):
		redirect = "/builder"

	frappe.local.login_manager.login_as("Administrator")
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = redirect


@frappe.whitelist(allow_guest=True)
def whoami():
	"""Diagnostic: which Frappe site is serving this request (host routing)."""
	return {"site": frappe.local.site}
