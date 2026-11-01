# Write the page-header defaults down on sites that predate the fields.
#
# A Select with no value falls back in code, but a Check does not: Frappe hands
# back 0 for a Single field that was never written, which is indistinguishable
# from someone deliberately turning breadcrumbs off. So the default has to be
# stored, not inferred.
#
# The Select is the witness: if it is empty, this site has never seen these
# fields, and both defaults are safe to write. That has to be read **before**
# anything is written, or setting the style first makes the site look configured
# and the checkbox never gets its default.
import frappe

DOCTYPES = ("Website Header Footer Config", "Website Header Footer Variant")
DEFAULTS = {"page_header_style": "Simple", "show_breadcrumbs": 1}


def execute():
	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.get_field("page_header_style"):
			continue

		if meta.issingle:
			if not frappe.db.get_single_value(doctype, "page_header_style"):
				for field, value in DEFAULTS.items():
					frappe.db.set_single_value(doctype, field, value)
			continue

		for name in frappe.get_all(doctype, pluck="name"):
			if not frappe.db.get_value(doctype, name, "page_header_style"):
				frappe.db.set_value(doctype, name, dict(DEFAULTS), update_modified=False)

	frappe.db.commit()
