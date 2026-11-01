# Give existing sites a header style.
#
# The field arrived after these configs were created, so they carry no value
# and the Theme tab shows an empty "Select option". The renderer already falls
# back to Classic, which is exactly what these sites look like today — this
# only writes down what is already true.
#
# The site-wide config is a Single (its values live in `tabSingles`, it has no
# table of its own); the per-profile Variant is an ordinary doctype. Going
# through the ORM handles both without caring which is which.
import frappe

DOCTYPES = ("Website Header Footer Config", "Website Header Footer Variant")


def execute():
	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.get_field("header_style"):
			continue

		if meta.issingle:
			if not frappe.db.get_single_value(doctype, "header_style"):
				frappe.db.set_single_value(doctype, "header_style", "Classic")
			continue

		for name in frappe.get_all(doctype, filters={"header_style": ("in", ("", None))}, pluck="name"):
			frappe.db.set_value(doctype, name, "header_style", "Classic", update_modified=False)

	frappe.db.commit()
