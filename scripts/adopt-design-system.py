#!/usr/bin/env python
"""Make existing pages adopt the site's design system.

Pages generated before the `u-` classes existed carry their own corners,
shadows and transitions. They keep them: changing the site's Corners setting
moves the header and the new pages, and leaves the old ones behind. That gap
is exactly what makes a site look assembled rather than designed.

This walks every Builder Page, recognises the blocks that plainly are buttons,
cards, images or inputs, gives them the matching role class, and removes the
properties that class now owns. Colours, spacing and layout are left alone —
only the SHAPE moves to the system.

    ../env/bin/python ../apps/unpress_core/scripts/adopt-design-system.py <site>
    ../env/bin/python ../apps/unpress_core/scripts/adopt-design-system.py <site> --apply

Without --apply nothing is written: it reports what it would change. --apply
writes the DRAFT only, so the change shows in the editor and the user
publishes it deliberately; add --publish to write the live blocks too.
"""

import argparse
import json
import sys

import frappe

# What each role takes over. Removing more than this would change the design,
# not normalise it.
OWNED_BY_ROLE = {
	"u-btn": ("borderRadius", "boxShadow", "transition"),
	"u-card": ("borderRadius", "boxShadow"),
	"u-media": ("borderRadius", "overflow"),
	"u-input": ("borderRadius",),
}


def _classify(block: dict) -> list[str] | None:
	"""The role a block plainly has, or None when it is not obvious.

	Deliberately conservative: a block we are unsure about keeps its styles.
	A wrong class is worse than a missed one — it changes how the page looks.
	"""
	element = block.get("element")
	styles = block.get("baseStyles") or {}
	classes = [str(c) for c in (block.get("classes") or [])]
	if any(c.startswith("u-") for c in classes):
		return None

	if element == "img":
		# only images that were given corners: a full-bleed hero must stay square
		return ["u-media"] if styles.get("borderRadius") else None

	if element == "input" or element == "textarea":
		return ["u-input"]

	if element in ("a", "button"):
		has_fill = "backgroundColor" in styles
		has_edge = any(k.startswith("border") and k != "borderRadius" for k in styles)
		if not (has_fill or has_edge) or "padding" not in styles:
			return None  # a plain text link, not a button
		if has_fill and styles.get("backgroundColor") not in ("transparent", "none", ""):
			return ["u-btn", "u-btn--primary"]
		return ["u-btn", "u-btn--outline"]

	if element in ("div", "article", "li"):
		# a card announces itself: a surface with corners and either padding or
		# a border. Sections and layout wrappers have neither.
		if styles.get("borderRadius") and (styles.get("padding") or styles.get("border")):
			if "backgroundColor" in styles or "border" in styles:
				return ["u-card"] if styles.get("boxShadow") else ["u-card", "u-card--flat"]
	return None


def _adopt(raw: str) -> tuple[str | None, dict]:
	"""Returns (new json, counts by role)."""
	try:
		tree = json.loads(raw)
	except (TypeError, ValueError):
		return None, {}

	counts: dict[str, int] = {}
	stack = list(tree) if isinstance(tree, list) else [tree]
	changed = False
	while stack:
		block = stack.pop()
		if not isinstance(block, dict):
			continue
		roles = _classify(block)
		if roles:
			block["classes"] = [*(block.get("classes") or []), *roles]
			owned = OWNED_BY_ROLE.get(roles[0], ())
			for bucket in ("baseStyles", "rawStyles", "mobileStyles", "tabletStyles"):
				styles = block.get(bucket)
				if isinstance(styles, dict):
					for prop in owned:
						styles.pop(prop, None)
			counts[roles[0]] = counts.get(roles[0], 0) + 1
			changed = True
		stack.extend(block.get("children") or [])

	return (json.dumps(tree) if changed else None), counts


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("site")
	parser.add_argument("--apply", action="store_true", help="write the draft blocks")
	parser.add_argument("--publish", action="store_true", help="also write the live blocks")
	args = parser.parse_args()

	frappe.init(site=args.site)
	frappe.connect()

	fields = ["draft_blocks"] + (["blocks"] if args.publish else [])
	totals: dict[str, int] = {}
	touched = 0

	for name in frappe.get_all("Builder Page", pluck="name"):
		page = frappe.get_doc("Builder Page", name)
		page_changed = False
		for field in fields:
			raw = page.get(field) or (page.get("blocks") if field == "draft_blocks" else None)
			if not raw:
				continue
			new_raw, counts = _adopt(raw)
			if not new_raw:
				continue
			page_changed = True
			for role, count in counts.items():
				totals[role] = totals.get(role, 0) + count
			if args.apply:
				page.db_set(field, new_raw, update_modified=False)
		if page_changed:
			touched += 1
			print(f"  {page.page_title or name}")

	if args.apply:
		frappe.db.commit()

	print()
	print(f"{touched} page(s), roles: {totals or 'none'}")
	if not args.apply:
		print("Nothing written. Re-run with --apply to write the drafts.")
	elif not args.publish:
		print("Drafts written. Publish each page to put it live.")

	frappe.destroy()
	return 0


if __name__ == "__main__":
	sys.exit(main())
