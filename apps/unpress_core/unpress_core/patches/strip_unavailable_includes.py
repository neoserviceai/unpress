# A generated page that includes a template from an app the bench does not have
# renders as a 500 — the whole page, not the section.
#
# The generator offered the webshop carousels on every e-commerce site, and
# Unpress has no webshop. The generation reported success and the homepage was
# a server error, which is the worst way to find out.
#
# The generator no longer offers them and the sanitiser now checks the app is
# installed. This clears the pages that were already written.
import json
import re

import frappe

INCLUDE_RE = re.compile(
	r"""\{%[-\s]*include\s+['"]([a-z_][a-z0-9_]*)/templates/[^'"]+['"][^%]*%\}"""
)


def _installed() -> set:
	return set(frappe.get_installed_apps())


def _strip(html: str, installed: set) -> tuple:
	"""Return (cleaned html, how many includes were removed)."""
	removed = 0

	def drop(match):
		nonlocal removed
		if match.group(1) in installed:
			return match.group(0)
		removed += 1
		return ""

	return INCLUDE_RE.sub(drop, html), removed


def _walk(blocks, installed) -> int:
	removed = 0
	stack = list(blocks or [])
	while stack:
		block = stack.pop()
		if not isinstance(block, dict):
			continue
		inner = block.get("innerHTML")
		if isinstance(inner, str) and "{%" in inner:
			cleaned, count = _strip(inner, installed)
			if count:
				block["innerHTML"] = cleaned
				removed += count
		children = block.get("children")
		if isinstance(children, list):
			stack.extend(children)
	return removed


def execute():
	if not frappe.db.exists("DocType", "Builder Page"):
		return

	installed = _installed()
	touched = 0

	for name in frappe.get_all("Builder Page", pluck="name"):
		values = {}
		total = 0
		for field in ("blocks", "draft_blocks"):
			raw = frappe.db.get_value("Builder Page", name, field)
			if not raw:
				continue
			try:
				blocks = json.loads(raw)
			except (TypeError, ValueError):
				continue
			count = _walk(blocks, installed)
			if count:
				values[field] = json.dumps(blocks, ensure_ascii=False)
				total += count

		if values:
			# update_modified stays False: this is a repair, not an edit, and the
			# page should not look freshly touched in the Studio's list
			frappe.db.set_value("Builder Page", name, values, update_modified=False)
			touched += 1

	if touched:
		frappe.db.commit()
		frappe.logger().info(f"stripped includes from apps not on this bench — {touched} pages")
