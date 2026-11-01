# The band's single enum becomes a preset and a fill.
#
# `page_header_style` mixed a composition with a background: "Centered" is an
# alignment, "Tinted" is what the band sits on. A site could therefore never ask
# for a centred title over a photograph — half the combinations had no way of
# being said. The field is split, and what each site already chose is carried
# across rather than reset to the default.
#
# Read before writing: the old column is dropped by `bench migrate` once the
# doctype no longer declares it, so this has to run while it is still there.
import frappe

DOCTYPES = ("Website Header Footer Config", "Website Header Footer Variant")

# old value -> (template, background)
TRANSLATION = {
	"None": ("None", "None"),
	"Simple": ("Standard", "None"),
	"Centered": ("Centered", "None"),
	"Tinted": ("Standard", "Tinted"),
}


def _pages_already_open_on_their_own() -> bool:
	"""Do the site's interior pages already draw an opening of their own?

	A site generated before the shared band exists carries its opening inside
	each page — an eyebrow, then a large heading. Switching the band on above
	that stacks two titles, which is worse than having no band at all. Seen on a
	live client site: /about opened on "À PROPOS / Daniel Moret Info Service"
	and the band would have added "Accueil / À propos" over it.

	So the band defaults to off wherever the pages already speak for themselves.
	Turning it on stays one setting away, once those openings have been lifted.
	"""
	import json
	import re

	HEADINGS = {"h1", "h2", "h3"}

	def opens_with_heading(blocks, depth=0):
		if depth > 6 or not isinstance(blocks, list):
			return False
		for block in blocks:
			if not isinstance(block, dict):
				continue
			raw = block.get("innerHTML") or block.get("innerText") or ""
			text = re.sub(r"<[^>]+>", " ", str(raw)).strip()
			if text and str(block.get("element", "")).lower() in HEADINGS:
				return True
			if text and len(text) > 60:
				return False  # real copy first: this page opens on content
			if opens_with_heading(block.get("children") or [], depth + 1):
				return True
		return False

	try:
		routes = frappe.get_all(
			"Builder Page",
			filters={"published": 1, "is_template": 0},
			fields=["name", "route", "blocks"],
			limit=20,
		)
	except Exception:
		return False

	interior = [r for r in routes if (r.route or "").strip("/") not in ("", "home", "index")]
	if not interior:
		return False

	own = 0
	for page in interior:
		try:
			blocks = json.loads(page.blocks or "[]")
		except (ValueError, TypeError):
			continue
		if len(blocks) == 1 and blocks[0].get("children"):
			blocks = blocks[0]["children"]
		if opens_with_heading(blocks):
			own += 1

	return own >= max(1, len(interior) // 2)


def execute():
	# Decided once, before touching anything, and used for every doctype below.
	safe_default = "None" if _pages_already_open_on_their_own() else "Standard"

	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.get_field("page_header_template"):
			continue

		# Re-runnable on purpose: an earlier pass could leave the fields empty
		# when there was nothing to translate, and an empty Select is not a
		# configured site.

		if meta.issingle:
			# A Single has no table of its own — its values live as rows in
			# `tabSingles`, so has_column() would raise TableMissingError. And
			# get_value() on that table appends an ORDER BY `creation`, a column
			# it does not have either; the read has to be direct.
			row = frappe.db.sql(
				"select `value` from `tabSingles` where `doctype`=%s and `field`=%s",
				(doctype, "page_header_style"),
			)
			old = row[0][0] if row else None
			# A Single that was never written has no row at all, so the doctype's
			# `default` never applies — the field reads back as "". Rendering
			# survives (settings() falls back in code) but the Theme would show
			# empty selects, and nothing would say what the site actually uses.
			# The patch writes a defined state either way.
			template, background = TRANSLATION.get(old, (safe_default, "None")) if old else (safe_default, "None")
			frappe.db.set_single_value(doctype, "page_header_template", template)
			frappe.db.set_single_value(doctype, "page_header_background", background)

			# A Check that was never written reads back as 0 — indistinguishable
			# from someone deliberately turning breadcrumbs off. The absence of
			# the row is the only honest witness, and it has to be consulted
			# before anything is written. Seen on a live site: breadcrumbs silently
			# off on a site that had never been asked.
			written = frappe.db.sql(
				"select 1 from `tabSingles` where `doctype`=%s and `field`=%s",
				(doctype, "show_breadcrumbs"),
			)
			if not written:
				frappe.db.set_single_value(doctype, "show_breadcrumbs", 1)
			continue

		# The doctype can exist without its table: declared by the app, never
		# created on this site. has_column() raises TableMissingError there —
		# seen on a live site for the multi-site Variant.
		if not frappe.db.table_exists(doctype):
			continue
		# has_column() takes a DOCTYPE, not a table name. Passing "tab" + doctype
		# made it look for `tabtabWebsite Header Footer Variant` and raise
		# TableMissingError — which read like a missing table and was not one.
		if not frappe.db.has_column(doctype, "page_header_style"):
			# nothing to translate, but the rows still deserve a defined state
			for name in frappe.get_all(doctype, pluck="name"):
				if not frappe.db.get_value(doctype, name, "page_header_template"):
					frappe.db.set_value(
						doctype,
						name,
						{"page_header_template": safe_default, "page_header_background": "None"},
						update_modified=False,
					)
			continue

		for name, old in frappe.db.get_all(
			doctype, fields=["name", "page_header_style"], as_list=True
		):
			template, background = TRANSLATION.get(old, (safe_default, "None")) if old else (safe_default, "None")
			frappe.db.set_value(
				doctype,
				name,
				{"page_header_template": template, "page_header_background": background},
				update_modified=False,
			)

	frappe.db.commit()
