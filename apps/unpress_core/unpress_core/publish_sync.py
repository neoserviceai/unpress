# Unified publishing: publishing a page in the Builder regenerates the static
# site automatically (when enabled) — one gesture, no separate "export" step.
# Enable per site: bench --site X set-config unpress_auto_export 1
# Optional target: unpress_publish_dir (defaults to the exporter's dist dir).
import frappe


def on_builder_page_update(doc, method=None):
	if not frappe.conf.get("unpress_auto_export"):
		return
	if not doc.published:
		return
	frappe.enqueue(
		"unpress_core.publish_sync.export_now",
		queue="short",
		job_id=f"unpress-auto-export::{frappe.local.site}",
		deduplicate=True,
	)


def export_now():
	from unpress_core.exporter import export_site

	export_site(frappe.conf.get("unpress_publish_dir"))
