# The plugin registry and the chrome Web Templates were briefly named after the
# Unpress edition before they shipped.
#
# It is the same subsystem in both editions, and the other one must not carry
# Unpress branding in a doctype name its clients can see. Renamed to
# "Website Plugin", matching Website Header Footer Config next to it.
#
# The registry is derived: sync_plugins() rebuilds every row from the manifest
# on the next migrate, so the old table can go without carrying anything over
# except the one thing the site chose — whether each plugin is on.
import frappe

OLD = "Unpress Plugin"
NEW = "Website Plugin"
OLD_TEMPLATES = ("Unpress Header", "Unpress Footer")


def execute():
	# same reason, same fix, for the two Web Templates: they are rebuilt from
	# code on every migrate, so dropping the old names loses nothing
	for name in OLD_TEMPLATES:
		if frappe.db.exists("Web Template", name):
			frappe.delete_doc("Web Template", name, force=True, ignore_missing=True)

	if not frappe.db.exists("DocType", OLD):
		frappe.db.commit()
		return

	# carry the on/off choice across, the only thing the old rows knew that the
	# manifest does not
	choices = {}
	try:
		for row in frappe.get_all(OLD, fields=["plugin_name", "enabled"]):
			choices[row.plugin_name] = row.enabled
	except Exception:
		choices = {}

	frappe.delete_doc("DocType", OLD, force=True, ignore_missing=True)
	frappe.db.commit()

	if not choices or not frappe.db.exists("DocType", NEW):
		return

	from unpress_core.plugins import sync_plugins

	sync_plugins()
	for plugin_name, enabled in choices.items():
		if frappe.db.exists(NEW, plugin_name):
			frappe.db.set_value(NEW, plugin_name, "enabled", enabled, update_modified=False)
	frappe.db.commit()
