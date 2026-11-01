# Whitelisted API for the Studio import wizard (unpress_core /studio-import).
import json

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from wp_migrator.wxr_fetch import fetch_wxr


def _require_manager():
	if frappe.session.user == "Guest" or "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	_require_enabled()


def _require_enabled():
	"""Refuse the import when the site has this plugin turned off.

	unpress_core owns the plugin registry, and this app must keep working on a
	bench that does not have it — hence the soft import. Without a registry,
	nothing is gated.
	"""
	try:
		from unpress_core.plugins import guard
	except ImportError:
		return
	guard("wp_migrator")


@frappe.whitelist()
def probe(url: str):
	"""Create (or reuse) a migration for this URL and probe the site."""
	_require_manager()
	name = frappe.db.get_value("WP Migration", {"source_url": url})
	doc = (
		frappe.get_doc("WP Migration", name)
		if name
		else frappe.get_doc({"doctype": "WP Migration", "source_url": url}).insert()
	)
	result = doc.probe()
	frappe.db.commit()
	return {"name": doc.name, "probe": result}


@frappe.whitelist()
def start(name: str, username: str | None = None, password: str | None = None):
	"""Fetch the WXR with the given wp-admin credentials (if not already
	attached), then run the import as a background job."""
	_require_manager()
	doc = frappe.get_doc("WP Migration", name)

	if not doc.wxr_file:
		if not (username and password):
			frappe.throw(_("WordPress credentials are required to fetch the export"))
		xml_text = fetch_wxr(doc.source_url, username, password)
		f = save_file(
			"wordpress-export.xml", xml_text.encode(), "WP Migration", doc.name, is_private=1
		)
		doc.wxr_file = f.file_url

	doc.import_templates = 0
	doc.publish_pages = 1
	doc.import_media = 1
	doc.status = "Importing"
	doc.progress = json.dumps({"stage": _("Queued"), "detail": ""})
	doc.save()
	frappe.db.commit()

	frappe.enqueue_doc(
		"WP Migration", doc.name, "start_import", queue="long", timeout=7200, enqueue_after_commit=True
	)
	frappe.db.commit()
	return {"ok": True, "name": doc.name}


@frappe.whitelist()
def status(name: str):
	_require_manager()
	doc_status, progress, report = frappe.db.get_value(
		"WP Migration", name, ["status", "progress", "report"]
	)
	return {
		"status": doc_status,
		"progress": json.loads(progress) if progress else None,
		"report": json.loads(report) if report else None,
	}
