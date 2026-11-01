# Static site exporter — the "Studio ≠ Site" publish pipeline.
# Renders every published route server-side and writes a self-contained
# bundle (HTML + assets) deployable on any static host.
#
# Run: bench --site <site> execute unpress_core.exporter.export_site
import os
import re
import shutil

import frappe

# href/src/srcset/url(...) pointing at site-local assets
ASSET_RE = re.compile(
	r"""(?:src|href)=["'](/(?:files|assets)/[^"']+)["']|url\(['"]?(/(?:files|assets)/[^'")]+)['"]?\)"""
)


def _render_route(route):
	"""Render a route through the real website pipeline as Guest."""
	from frappe.utils import get_html_for_route

	frappe.set_user("Guest")
	try:
		return get_html_for_route(route)
	finally:
		frappe.set_user("Administrator")


def _resolve_asset(path):
	"""Map a site-absolute asset URL to a file on disk."""
	path = path.split("?")[0]
	if path.startswith("/files/"):
		return frappe.get_site_path("public", "files", *path[len("/files/") :].split("/"))
	if path.startswith("/assets/"):
		parts = path[len("/assets/") :].split("/")
		built = os.path.join(frappe.utils.get_bench_path(), "sites", "assets", *parts)
		if os.path.exists(built):
			return built
		# assets symlinks may be missing (no `bench build` yet): fall back to
		# the standard mapping /assets/<app>/* -> apps/<app>/<app>/public/*
		app, rest = parts[0], parts[1:]
		return os.path.join(frappe.utils.get_bench_path(), "apps", app, app, "public", *rest)
	return None


def export_site(output_dir=None):
	"""Export all published Builder Pages (and the home route) to a static bundle."""
	site = frappe.local.site
	output_dir = output_dir or frappe.get_site_path("private", "static-export", "dist")
	if os.path.exists(output_dir):
		shutil.rmtree(output_dir)
	os.makedirs(output_dir, exist_ok=True)

	# freshly published drafts may be shadowed by the website render cache
	from frappe.website.utils import clear_website_cache

	clear_website_cache()

	routes = frappe.get_all("Builder Page", {"published": 1}, pluck="route")
	home = frappe.db.get_single_value("Website Settings", "home_page")
	report = {"site": site, "pages": [], "assets": 0, "asset_failures": [], "output": output_dir}
	assets_seen = set()

	for route in routes:
		try:
			html = _render_route(route)
		except Exception as e:
			report["pages"].append({"route": route, "error": str(e)[:200]})
			continue

		# collect and copy referenced local assets
		for match in ASSET_RE.finditer(html):
			asset_url = match.group(1) or match.group(2)
			if asset_url in assets_seen:
				continue
			assets_seen.add(asset_url)
			src = _resolve_asset(asset_url)
			dest = os.path.join(output_dir, asset_url.lstrip("/").split("?")[0])
			if src and os.path.exists(src):
				os.makedirs(os.path.dirname(dest), exist_ok=True)
				shutil.copy2(src, dest)
				report["assets"] += 1
			else:
				report["asset_failures"].append(asset_url)

		# pretty URLs: route/index.html (home route also copied to /index.html)
		page_dir = os.path.join(output_dir, route)
		os.makedirs(page_dir, exist_ok=True)
		with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
			f.write(html)
		if route == home:
			with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
				f.write(html)
		report["pages"].append({"route": route, "ok": True, "bytes": len(html)})

	print(frappe.as_json(report, indent=1))
	return report
