# Chrome (header/footer/theme) API for the builder Settings > Theme tab.
#
# Operates on Website Header Footer Config — the SAME doctype the the host
# v15 fork ships — and only through its public fieldnames, so this module
# ports to the fork's builder/hf_utils as-is. The v15 port only needs to add
# the per-Website-Profile Variant resolution on top (see header_footer.py);
# here (single-site Studio) the Single is always the right document.
import json

import frappe

CHROME_ROLES = ("System Manager", "Website Manager")

SIMPLE_FIELDS = (
	# header
	"header_layout",
	"header_style",
	"sticky_header",
	"header_scroll",
	"header_height",
	"header_bg_color",
	"header_text_color",
	"logo_type",
	"logo_text",
	"logo_image",
	"show_cta",
	"cta_text",
	"cta_url",
	"cta_style",
	"search_type",
	"show_user",
	"show_wishlist",
	"show_cart",
	# footer
	"footer_template",
	"footer_menu_source",
	# The band: a preset and a fill, plus what the fills need. The single
	# `page_header_style` these replace was still listed here after the doctype
	# had dropped it — so the Theme read a field that no longer existed and
	# showed two empty selects over values that were sitting in the database.
	"page_header_template",
	"page_header_background",
	"page_header_bg_color",
	"page_header_image",
	"page_header_excluded_routes",
	"show_breadcrumbs",
	"blog_layout",
	"blog_post_layout",
	"blog_allow_comments",
	"blog_show_author",
	"show_footer_html",
	"footer_html",
	"footer_bg_color",
	"footer_text_color",
	"show_footer_logo",
	"footer_description",
	"copyright_text",
	"show_social_links",
	"facebook_url",
	"twitter_url",
	"instagram_url",
	"linkedin_url",
	"youtube_url",
	"show_newsletter",
	"newsletter_title",
	# design system
	"radius_style",
	"shadow_style",
	"button_hover",
	"motion_style",
	# theme
	"primary_color",
	"secondary_color",
	"background_color",
	"text_color",
	"heading_font",
	"body_font",
)

# Select fields whose options the UI needs
OPTION_FIELDS = (
	"header_scroll",
	"radius_style",
	"shadow_style",
	"button_hover",
	"motion_style",
	"header_layout",
	"header_style",
	"header_height",
	"logo_type",
	"cta_style",
	"search_type",
	"footer_template",
	"footer_menu_source",
	"page_header_template",
	"page_header_background",
	"blog_layout",
	"blog_post_layout",
	"heading_font",
	"body_font",
)


def _chrome_doc():
	frappe.only_for(CHROME_ROLES)
	return frappe.get_doc("Website Header Footer Config")


@frappe.whitelist()
def get_chrome_settings():
	doc = _chrome_doc()
	meta = frappe.get_meta("Website Header Footer Config")

	settings = {field: doc.get(field) for field in SIMPLE_FIELDS}
	settings["footer_links"] = [
		{
			"column_name": row.column_name,
			"label": row.label,
			"url": row.url,
			"is_external": row.is_external,
			"open_in_new_tab": row.open_in_new_tab,
		}
		for row in (doc.footer_links or [])
	]
	settings["menu_items"] = [
		{"label": row.label, "url": row.url, "open_in_new_tab": row.open_in_new_tab}
		for row in (doc.menu_items or [])
	]

	options = {}
	for field in OPTION_FIELDS:
		df = meta.get_field(field)
		options[field] = [opt for opt in (df.options or "").split("\n") if opt] if df else []
	settings["_options"] = options
	return settings


@frappe.whitelist()
def update_chrome_settings(settings):
	if isinstance(settings, str):
		settings = json.loads(settings)

	doc = _chrome_doc()
	for field in SIMPLE_FIELDS:
		if field in settings:
			doc.set(field, settings[field])

	if "footer_links" in settings:
		doc.set("footer_links", [])
		for row in settings["footer_links"] or []:
			label = (row.get("label") or "").strip()
			url = (row.get("url") or "").strip()
			if label and url:
				doc.append("footer_links", {
					"column_name": (row.get("column_name") or "").strip(),
					"label": label,
					"url": url,
					# derived, not asked: nobody wants to tick "external" after
					# pasting an https:// address
					"is_external": 1 if url.startswith(("http://", "https://")) else 0,
					"open_in_new_tab": 1 if row.get("open_in_new_tab") else 0,
				})

	if "menu_items" in settings:
		doc.set("menu_items", [])
		for item in settings["menu_items"] or []:
			label = (item.get("label") or "").strip()
			url = (item.get("url") or "").strip()
			if label and url:
				doc.append(
					"menu_items",
					{
						"label": label,
						"url": url,
						"open_in_new_tab": 1 if item.get("open_in_new_tab") else 0,
					},
				)

	# on_update handles menu -> Website Settings sync + website cache clear
	doc.save()
	return {"ok": True}
