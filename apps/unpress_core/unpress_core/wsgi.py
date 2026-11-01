# Production WSGI entrypoint that also serves /assets and public /files.
# Frappe's app serves the API and rendered pages; in a standard deployment
# nginx serves the static parts. When gunicorn is fronted by Caddy only
# (dev16 studio-web, the single-site image), we do it here:
# - /assets is bench-global -> SharedDataMiddleware
# - /files is PER SITE (resolved from the Host header, falling back to the
#   default site) -> tiny custom middleware. Frappe itself only handles
#   /private/files, never public files.
import json
import mimetypes
import os

from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.wsgi import wrap_file

import frappe.app

# gunicorn runs with --chdir sites, so the bench root is cwd's parent —
# that beats guessing an absolute path (dev16 uses workspace/frappe-bench,
# the single image plain frappe-bench). FRAPPE_BENCH_PATH still wins.
_BENCH = os.environ.get("FRAPPE_BENCH_PATH") or (
	os.path.dirname(os.getcwd())
	if os.path.basename(os.getcwd()) == "sites"
	else "/home/frappe/workspace/frappe-bench"
)
_SITES = os.path.join(_BENCH, "sites")


def _default_site():
	try:
		with open(os.path.join(_SITES, "currentsite.txt")) as f:
			site = f.read().strip()
			if site:
				return site
	except OSError:
		pass
	try:
		with open(os.path.join(_SITES, "common_site_config.json")) as f:
			return json.load(f).get("default_site")
	except OSError:
		return None


class PerSiteFiles:
	"""Serve public /files/<name> from sites/<site>/public/files, and pin
	unknown hosts to the default site.

	frappe v16 resolves the site as: X-Frappe-Site-Name header (nginx's job
	in a classic deployment) or the raw Host — currentsite.txt is no longer
	consulted. Without nginx, any host that is not literally a site name
	(e.g. localhost:8080 on the single-site install) 404s. Injecting the
	header for unknown hosts restores serve-default behaviour while leaving
	real multi-tenant Host routing untouched.
	"""

	def __init__(self, app):
		self.app = app

	def __call__(self, environ, start_response):
		host = (environ.get("HTTP_HOST") or "").split(":")[0]
		if (
			host
			and not environ.get("HTTP_X_FRAPPE_SITE_NAME")
			and not os.path.isdir(os.path.join(_SITES, host))
		):
			default = _default_site()
			if default:
				environ["HTTP_X_FRAPPE_SITE_NAME"] = default

		path = environ.get("PATH_INFO", "")
		if path.startswith("/files/"):
			host = (environ.get("HTTP_HOST") or "").split(":")[0]
			site = host if os.path.isdir(os.path.join(_SITES, host, "public")) else _default_site()
			if site:
				base = os.path.realpath(os.path.join(_SITES, site, "public"))
				full = os.path.realpath(os.path.join(base, path.lstrip("/")))
				# realpath + prefix check kills path traversal
				if full.startswith(base + os.sep) and os.path.isfile(full):
					mime = mimetypes.guess_type(full)[0] or "application/octet-stream"
					headers = [
						("Content-Type", mime),
						("Content-Length", str(os.path.getsize(full))),
						("Cache-Control", "public, max-age=3600"),
					]
					start_response("200 OK", headers)
					return wrap_file(environ, open(full, "rb"))
		return self.app(environ, start_response)


application = PerSiteFiles(
	SharedDataMiddleware(
		frappe.app.application,
		{"/assets": os.path.join(_SITES, "assets")},
	)
)
