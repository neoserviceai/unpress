"""What makes this app a plugin rather than just an app.

Two things live here: the entry the registry needs, and the guard every entry
point calls. Both are small on purpose — a plugin should not have to understand
Unpress to be one.
"""

import frappe
from frappe import _

#: The name the registry knows this plugin by. It is also the key the Studio
#: reads in `capabilities`, so keep it stable: renaming it makes every site
#: forget whether the owner had turned it off.
PLUGIN_NAME = "hello"


def manifest() -> dict:
	"""Declared to Unpress from `hooks.py`, not registered by importing Unpress.

	The dependency points this way round on purpose: this app can be installed
	on a bench without Unpress and simply do nothing, and Unpress never has to
	know this app exists at build time.
	"""
	return {
		"plugin_name": PLUGIN_NAME,
		"title": _("Hello"),
		"description": _("An example plugin: one page, one endpoint, one prompt."),
		"app_name": "unpress_hello",
		# The Studio compiles its icon CSS from its own sources, so a name it
		# does not already bundle draws nothing and falls back to the puzzle
		# piece. Naming the fallback outright is more honest than picking a
		# nicer icon and getting the puzzle piece anyway.
		"icon": "lucide-puzzle",
		# Routes under this prefix 404 when the plugin is off. Leave empty when
		# the plugin serves no public route.
		"route_prefix": "hello",
	}


def is_enabled() -> bool:
	"""True unless the owner turned this plugin off.

	Defaults to True on purpose, and stays True when Unpress is absent: the
	registry exists to take a capability away, never to grant one. A plugin
	that silently did nothing until someone found a checkbox would be a bug
	report, not a feature.
	"""
	#: The registry answers to two package names: `unpress_core` on Unpress,
	#: and `builder` on builds that carry it inside the Builder app itself.
	#: Same code, two import paths. A plugin that tries only one silently
	#: believes it is always enabled on the other — which is exactly how this
	#: example first shipped: its endpoint kept answering after the owner
	#: switched it off.
	for module in ("unpress_core.plugins", "builder.plugins"):
		try:
			registry = frappe.get_module(module)
		except Exception:
			continue
		return bool(registry.is_enabled(PLUGIN_NAME))

	# Neither is installed: this is a plain Frappe bench, and the app keeps
	# working on its own.
	return True


def guard() -> None:
	"""Refuse the call when the plugin is off. Call this FIRST, everywhere.

	Every whitelisted method needs it. A disabled plugin whose endpoints still
	answer is not disabled — it is merely hidden, and hidden is not a security
	property.
	"""
	if not is_enabled():
		frappe.throw(
			_("The {0} plugin is turned off on this site.").format(_("Hello")),
			frappe.PermissionError,
		)
