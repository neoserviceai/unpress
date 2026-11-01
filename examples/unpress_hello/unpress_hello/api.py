"""The plugin's endpoints. Every one of them guards first."""

import frappe

from .plugin import guard


@frappe.whitelist()
def greet(name: str = "") -> dict:
	"""A whitelisted method, refused when the plugin is off.

	`guard()` comes before everything, including argument validation: an
	endpoint that validates then refuses still tells a caller whether their
	input was well-formed.
	"""
	guard()

	name = (name or "").strip()[:60]
	return {"message": frappe._("Hello, {0}!").format(name or frappe._("stranger"))}
