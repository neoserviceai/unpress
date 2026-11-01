"""The plugin registry.

Frappe has no notion of "installed but off". `frappe.get_hooks()` is
unconditional: the moment an app is in `installed_apps`, its hooks, routes,
assets and doctypes are live, and the only real switch — `bench uninstall-app`
— **drops the module's tables**. That is the wrong trade for a site owner who
just wants to hide a feature: turning the blog off should not delete the
articles.

So a plugin here is not an install. It is a row that says *this capability
exists on this bench, and the owner wants it on or off*. Turning it off:

- hides its entry in the Studio (`get_capabilities` feeds the `v-if`);
- refuses its whitelisted endpoints (`guard`);
- 404s the web routes it owns (`route_guard`, wired to `before_request`).

What it deliberately does NOT do is unload hooks or drop data. A disabled
plugin is dormant, not gone, and turning it back on is instant.

This is also the seam the community store will plug into: a hub-installed
plugin is the same row with `source = "Hub"`.
"""

import frappe
from frappe import _
from werkzeug.exceptions import abort

REGISTRY_DOCTYPE = "Website Plugin"

# What ships with the product. A built-in is seeded on migrate when the app
# that provides it is actually installed — the manifest describes intent, the
# bench decides reality.
#
# `route_prefix` is what the plugin owns on the public site. It is used both to
# 404 the routes when the plugin is off and to keep the site generator from
# creating a Builder page on top of them.
BUILT_INS = (
	{
		"plugin_name": "blog",
		"title": "Blog",
		"description": "Articles, categories and an RSS feed, on /blog.",
		"app_name": "blog",
		# The capability exists wherever this doctype does — and on Frappe v15
		# it comes from the CORE, not from an app. Testing only for the app
		# hid the Articles screen on every v15 site, including sites that had a
		# working blog with published posts. What matters is whether the
		# feature is usable, not where it came from.
		"witness_doctype": "Blog Post",
		"icon": "lucide-newspaper",
		"route_prefix": "blog",
		"is_core": 0,
	},
	{
		"plugin_name": "wp_migrator",
		"title": "WordPress Import",
		"description": "Import an existing WordPress or Elementor site.",
		"app_name": "wp_migrator",
		"icon": "lucide-download",
		"route_prefix": "",
		"is_core": 0,
	},
)

BUILT_IN_BY_NAME = {p["plugin_name"]: p for p in BUILT_INS}


def _translatable_labels():
	"""Extraction markers — never called.

	The manifest above stores English, because it is written into database rows
	that outlive any one request's language. The labels are wrapped at the use
	site (`_(v)`); gettext cannot see through a variable, so the literals are
	listed here for the POT file. Keep in sync with BUILT_INS.
	"""
	_("Blog")
	_("Articles, categories and an RSS feed, on /blog.")
	_("WordPress Import")
	_("Import an existing WordPress or Elementor site.")


_CACHE_KEY = "unpress_plugin_state"


def _state() -> dict:
	"""{plugin_name: enabled} for this site, cached.

	Read on every request by the route guard, so it must not hit the database
	each time. `clear_cache` runs from the doctype's on_update.
	"""
	cached = frappe.cache().get_value(_CACHE_KEY)
	if cached is not None:
		return cached

	state = {}
	if frappe.db.exists("DocType", REGISTRY_DOCTYPE):
		for row in frappe.get_all(REGISTRY_DOCTYPE, fields=["plugin_name", "enabled"]):
			state[row.plugin_name] = bool(row.enabled)

	frappe.cache().set_value(_CACHE_KEY, state)
	return state


def clear_cache():
	frappe.cache().delete_value(_CACHE_KEY)


def is_enabled(plugin_name: str) -> bool:
	"""True unless a registry row says otherwise.

	Defaulting to True matters: a bench that has not migrated yet, or an app
	installed by hand without a registry row, keeps working. The registry
	takes things away; it does not grant them.
	"""
	return _state().get(plugin_name, True)


def disabled_route_prefixes() -> tuple:
	"""Public route prefixes belonging to plugins that are currently off."""
	cached = frappe.cache().get_value("unpress_plugin_blocked_routes")
	if cached is not None:
		return tuple(cached)

	blocked = []
	state = _state()
	for name, enabled in state.items():
		if enabled:
			continue
		# The prefix has to come from the registry row, not only from the
		# built-in manifest: a third-party plugin's routes were never blocked,
		# so turning it off hid its Studio entry and refused its endpoints
		# while its public pages kept answering. Half-off is not off.
		prefix = (BUILT_IN_BY_NAME.get(name, {}) or {}).get("route_prefix")
		if not prefix:
			prefix = frappe.db.get_value(REGISTRY_DOCTYPE, name, "route_prefix")
		if not prefix and frappe.db.exists(REGISTRY_DOCTYPE, name):
			prefix = frappe.db.get_value(REGISTRY_DOCTYPE, name, "route_prefix")
		if prefix:
			blocked.append(prefix.strip("/"))

	frappe.cache().set_value("unpress_plugin_blocked_routes", blocked)
	return tuple(blocked)


def guard(plugin_name: str):
	"""Refuse an endpoint belonging to a disabled plugin.

	Called at the top of a plugin's whitelisted methods. Hiding the button is
	not access control — the endpoint is still reachable by anyone who knows
	its name.
	"""
	if not is_enabled(plugin_name):
		title = (BUILT_IN_BY_NAME.get(plugin_name, {}) or {}).get("title") or plugin_name
		frappe.throw(
			_("{0} is turned off for this site.").format(_(title)),
			frappe.PermissionError,
		)


def _installed_apps() -> set:
	"""What is really installed, read from the table rather than the cache.

	`frappe.get_installed_apps()` is cached per process, and the install path
	runs `bench install-app` in a **subprocess** — so the worker that installed
	an app would otherwise still believe it is absent and mark the plugin
	unavailable the moment it became available.
	"""
	try:
		rows = frappe.get_all("Installed Application", pluck="app_name")
		if rows:
			return set(rows)
	except Exception:
		pass
	return set(frappe.get_installed_apps())


def _declared_plugins() -> list:
	"""Manifests contributed by installed apps through the `unpress_plugins` hook.

	This is how a third party ships a plugin without us shipping anything: the
	host app declares itself, and we never import it at build time. An app that
	is installed on a bench without Unpress simply has its hook read by nobody.

	A manifest that raises, or that omits `plugin_name`, is skipped with a
	warning rather than taking the whole registry down with it — one bad app
	must not stop the others from appearing.
	"""
	out = []
	seen = {spec["plugin_name"] for spec in BUILT_INS}

	for method in frappe.get_hooks("unpress_plugins") or []:
		try:
			spec = frappe.get_attr(method)()
		except Exception as exc:
			frappe.log_error("Plugin manifest refused", f"{method}\n{exc}")
			continue

		if not isinstance(spec, dict) or not spec.get("plugin_name"):
			frappe.log_error("Plugin manifest incomplete", f"{method} returned {spec!r}")
			continue

		name = spec["plugin_name"]
		if name in seen:
			# A built-in wins: an app cannot rename or re-describe the blog.
			frappe.log_error("Plugin name already taken", f"{method} claims {name!r}")
			continue

		seen.add(name)
		out.append({
			"plugin_name": name,
			"title": spec.get("title") or name,
			"description": spec.get("description") or "",
			"app_name": spec.get("app_name") or "",
			"icon": spec.get("icon") or "lucide-puzzle",
			"route_prefix": spec.get("route_prefix") or "",
			"is_core": 0,
			"witness_doctype": spec.get("witness_doctype"),
		})

	return out


def sync_plugins(app_name: str | None = None):
	"""Seed and refresh the registry.

	Wired to both `after_migrate` (no argument) and `after_app_install` (which
	passes the app that was just installed) — hence the ignored parameter.
	Installing the blog app is what makes the blog plugin appear.

	A built-in gets a row when its app is on the bench. When the app is gone
	the row stays but is marked unavailable: the owner's on/off choice, and
	anything a hub plugin recorded, survives a reinstall.
	"""
	if not frappe.db.exists("DocType", REGISTRY_DOCTYPE):
		return

	installed = _installed_apps()

	for spec in list(BUILT_INS) + _declared_plugins():
		available = 1 if spec["app_name"] in installed else 0
		witness = spec.get("witness_doctype")
		if not available and witness and frappe.db.exists("DocType", witness):
			available = 1
		name = spec["plugin_name"]

		if frappe.db.exists(REGISTRY_DOCTYPE, name):
			doc = frappe.get_doc(REGISTRY_DOCTYPE, name)
			# The manifest owns the presentation; the site owns `enabled`.
			doc.title = spec["title"]
			doc.description = spec["description"]
			doc.app_name = spec["app_name"]
			doc.icon = spec["icon"]
			doc.route_prefix = spec["route_prefix"]
			doc.is_core = spec["is_core"]
			doc.is_available = available
			doc.save(ignore_permissions=True)
			continue

		doc = frappe.new_doc(REGISTRY_DOCTYPE)
		doc.update({k: v for k, v in spec.items() if k != "witness_doctype"})
		doc.source = "Built-in" if spec in BUILT_INS else "App"
		doc.is_available = available
		# A plugin that ships with the product starts on. The owner turns it
		# off; they should not have to turn it on to get what they installed.
		doc.enabled = 1
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
	clear_cache()


@frappe.whitelist()
def get_capabilities() -> dict:
	"""What the Studio is allowed to show. Cheap, called on boot."""
	state = dict(_state())
	# an app that is not on the bench cannot be shown whatever the row says
	if frappe.db.exists("DocType", REGISTRY_DOCTYPE):
		for row in frappe.get_all(
			REGISTRY_DOCTYPE, fields=["plugin_name", "is_available"], filters={"is_available": 0}
		):
			state[row.plugin_name] = False
	return state


@frappe.whitelist()
def list_plugins() -> list:
	"""The Settings > Plugins screen."""
	frappe.only_for(("System Manager", "Website Manager"))
	if not frappe.db.exists("DocType", REGISTRY_DOCTYPE):
		return []
	rows = frappe.get_all(
		REGISTRY_DOCTYPE,
		fields=[
			"name",
			"plugin_name",
			"title",
			"description",
			"app_name",
			"icon",
			"enabled",
			"is_core",
			"is_available",
			"source",
			"route_prefix",
		],
		order_by="is_core desc, title asc",
	)
	for row in rows:
		row["title"] = _(row["title"])
		row["description"] = _(row["description"]) if row.get("description") else ""
	return rows


@frappe.whitelist()
def set_plugin_enabled(plugin_name: str, enabled) -> dict:
	frappe.only_for("System Manager")
	doc = frappe.get_doc(REGISTRY_DOCTYPE, plugin_name)
	if doc.is_core and not frappe.parse_json(str(enabled).lower()):
		frappe.throw(_("{0} cannot be turned off.").format(_(doc.title)))
	doc.enabled = 1 if frappe.parse_json(str(enabled).lower()) else 0
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"plugin_name": doc.plugin_name, "enabled": bool(doc.enabled)}


def route_guard():
	"""`before_request` — a disabled plugin does not serve its public routes.

	Turning the blog off has to make /blog stop existing, not merely hide the
	Studio entry, or the site keeps publishing articles the owner believes they
	have taken down. Frappe offers nothing for this: a route belongs to an app
	for as long as the app is installed.

	Runs on every request, so it reads a cached list and returns immediately
	when nothing is disabled — the common case.
	"""
	if not frappe.request:
		return

	try:
		blocked = disabled_route_prefixes()
	except Exception:
		# a bench mid-migration has no registry yet; never break the site over it
		return

	if not blocked:
		return

	path = frappe.request.path.strip("/")
	for prefix in blocked:
		if path == prefix or path.startswith(prefix + "/"):
			abort(404)
