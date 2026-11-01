"""The site's public address, and what depends on knowing it.

A container cannot infer where it is published. It only ever sees a plain HTTP
request on its own port, so every absolute URL Frappe builds — canonical tags,
the sitemap, `og:url`, links inside mail — comes out wrong the moment a real
domain and a TLS proxy sit in front. Measured on a fresh install before this
existed: the sitemap advertised `http://example.com:8000/contact`, wrong scheme
and an internal port that answers to nobody on the internet.

Someone has to tell the site its own address. The Docker entrypoint does it
from `UNPRESS_DOMAIN`; a bare-metal install calls `apply_public_url()` with
whatever the reverse proxy serves.
"""

import frappe

WEBSITE_SETTINGS = "Website Settings"

DEFAULT_ROBOTS = """User-agent: *
Allow: /

Sitemap: {public_url}/sitemap.xml"""


def apply_public_url(public_url: str) -> dict:
	"""Point the site at `public_url` and keep what derives from it in step.

	Idempotent: safe on every boot. Returns what it changed, so a caller can
	log something truthful rather than "done".
	"""
	public_url = (public_url or "").strip().rstrip("/")
	if not public_url.startswith(("http://", "https://")):
		frappe.throw("public_url must start with http:// or https://")

	changed = {}

	if frappe.conf.get("host_name") != public_url:
		# site_config, not Website Settings: `frappe.utils.get_url()` reads
		# `conf.host_name` first, and that is the value every absolute URL is
		# built from.
		from frappe.installer import update_site_config

		update_site_config("host_name", public_url)
		changed["host_name"] = public_url

	changed.update(_ensure_robots(public_url))
	return changed


def _ensure_robots(public_url: str) -> dict:
	"""Write a robots.txt naming the sitemap — only while there is none.

	Frappe serves an empty robots.txt by default: permissive, but it tells a
	crawler nothing about where the sitemap lives. An owner who writes their
	own must keep it, so this never overwrites a non-empty value.
	"""
	try:
		current = frappe.db.get_single_value(WEBSITE_SETTINGS, "robots_txt")
	except Exception:
		return {}

	if (current or "").strip():
		return {}

	robots = DEFAULT_ROBOTS.format(public_url=public_url)
	frappe.db.set_single_value(WEBSITE_SETTINGS, "robots_txt", robots)
	frappe.db.commit()
	return {"robots_txt": "written (was empty)"}


@frappe.whitelist()
def set_public_url(public_url: str) -> dict:
	"""Same thing from the Studio or an API client."""
	frappe.only_for("System Manager")
	return apply_public_url(public_url)
