# Give existing sites the scroll behaviour the field defaults to.
#
# The renderer already falls back to "Hide going down"; this only writes it
# down so the Theme tab shows a value instead of an empty select.
import frappe

DOCTYPES = ("Website Header Footer Config", "Website Header Footer Variant")
DEFAULT = "Hide going down"


def execute():
	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.get_field("header_scroll"):
			continue
		if meta.issingle:
			if not frappe.db.get_single_value(doctype, "header_scroll"):
				frappe.db.set_single_value(doctype, "header_scroll", DEFAULT)
			continue
		for name in frappe.get_all(doctype, pluck="name"):
			if not frappe.db.get_value(doctype, name, "header_scroll"):
				frappe.db.set_value(doctype, name, "header_scroll", DEFAULT, update_modified=False)
	frappe.db.commit()
