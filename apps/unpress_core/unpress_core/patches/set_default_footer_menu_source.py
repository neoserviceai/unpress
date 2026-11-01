# Give existing sites the footer menu source the field defaults to.
#
# The renderer already falls back to "Custom links" — which is what every site
# did before the field existed — so this changes no output. It only writes the
# value down, or the Theme's new select opens empty.
import frappe

DOCTYPES = ("Website Header Footer Config", "Website Header Footer Variant")
DEFAULT = "Custom links"


def execute():
	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.get_field("footer_menu_source"):
			continue
		if meta.issingle:
			if not frappe.db.get_single_value(doctype, "footer_menu_source"):
				frappe.db.set_single_value(doctype, "footer_menu_source", DEFAULT)
			continue
		for name in frappe.get_all(doctype, pluck="name"):
			if not frappe.db.get_value(doctype, name, "footer_menu_source"):
				frappe.db.set_value(doctype, name, "footer_menu_source", DEFAULT, update_modified=False)
	frappe.db.commit()
