# Repair the root block of pages generated before the editor could recognise it.
#
# The generator wrote the root as {"element": "body"} without `originalElement`,
# which is what Block.isRoot() tests. The body was therefore treated as an
# ordinary block: the resize handle appeared on it, and a single drag wrote a
# fixed pixel width — which the page then carried into its published CSS,
# leaving the site narrower than the viewport with a horizontal overflow.
#
# This stamps `originalElement` on the roots that lack it, and drops a fixed
# pixel width from the root's styles. A root width in % or a keyword is left
# alone: only an absolute px value can produce the overflow.
import json

import frappe

STYLE_BUCKETS = ("baseStyles", "rawStyles", "mobileStyles", "tabletStyles")


def _repair(raw: str) -> tuple[str | None, bool, bool]:
	"""Returns (new json, stamped, width_dropped)."""
	try:
		blocks = json.loads(raw)
	except (TypeError, ValueError):
		return None, False, False

	root = blocks[0] if isinstance(blocks, list) and blocks else blocks
	if not isinstance(root, dict) or root.get("element") != "body":
		return None, False, False

	stamped = False
	if root.get("originalElement") != "body":
		root["originalElement"] = "body"
		stamped = True

	dropped = False
	for bucket in STYLE_BUCKETS:
		styles = root.get(bucket)
		if isinstance(styles, dict) and str(styles.get("width", "")).endswith("px"):
			styles.pop("width")
			dropped = True

	if not (stamped or dropped):
		return None, False, False
	return json.dumps(blocks), stamped, dropped


def execute():
	if not frappe.db.exists("DocType", "Builder Page"):
		return

	stamped = dropped = 0
	for name in frappe.get_all("Builder Page", pluck="name"):
		page = frappe.get_doc("Builder Page", name)
		updates = {}
		for field in ("blocks", "draft_blocks"):
			raw = page.get(field)
			if not raw:
				continue
			new_raw, was_stamped, was_dropped = _repair(raw)
			if new_raw is None:
				continue
			updates[field] = new_raw
			stamped += int(was_stamped)
			dropped += int(was_dropped)
		if updates:
			# db_set: the blocks are already valid, and a full save would run
			# the page's own hooks (preview regeneration, publish sync) on
			# every page of every site for a repair that changes nothing visible
			for field, value in updates.items():
				page.db_set(field, value, update_modified=False)

	if stamped or dropped:
		frappe.db.commit()
		print(f"Builder page roots: {stamped} stamped, {dropped} fixed widths dropped")
