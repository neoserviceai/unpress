# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

"""
Header/Footer rendering utilities for Frappe Builder.

This module provides functions to render headers and footers from the
Website Header Footer Config DocType.
"""

import frappe
from frappe import _
from frappe.utils import cstr


@frappe.whitelist(allow_guest=True)
def get_header_footer_config():
	"""Get the header/footer configuration for the current website.

	Returns None if the DocType doesn't exist or is not configured,
	allowing graceful fallback to default header/footer.
	"""
	try:
		# website switch: an offline site (website_online=0, the fleet
		#//// default) has NO chrome for visitors — the login and every web page
		#//// render bare ("no website = just a login page", directive 2026-07-10).
		#//// This is THE seat of the chrome: the webshop navbar/footer overrides,
		#//// builder's webpage generator and the legacy injector all resolve their
		#//// config here. Staff (System/Website Manager) keeps the chrome so the
		#//// offline-site preview stays faithful. Keyed on the key existing in the
		#//// resolved profile dict, like every other gate.
		profile_doc = getattr(frappe.local, "website_profile_doc", None)
		if (
			profile_doc is not None
			and "website_online" in profile_doc
			and not profile_doc.get("website_online")
		):
			roles = frappe.get_roles()
			if "System Manager" not in roles and "Website Manager" not in roles:
				return None

		# multi-site: a resolved Website Profile with its own
		#//// variant gets it; everything else (default site, fleet instances
		#//// without profiles) falls back to the global Single.
		profile = getattr(frappe.local, "website_profile", None)
		if profile and frappe.db.exists("DocType", "Website Header Footer Variant"):
			if frappe.db.exists("Website Header Footer Variant", profile):
				return frappe.get_cached_doc("Website Header Footer Variant", profile)

		# Check if the DocType exists first
		if not frappe.db.exists("DocType", "Website Header Footer Config"):
			return None
		return frappe.get_single("Website Header Footer Config")
	except Exception:
		# Catch any error (DoesNotExistError, SQL errors, etc.)
		return None


@frappe.whitelist(allow_guest=True)
def render_header(config=None) -> str:
	"""
	Render the header HTML from configuration.

	Args:
		config: WebsiteHeaderFooterConfig document or None to fetch it

	Returns:
		HTML string for the header
	"""
	if config is None:
		config = get_header_footer_config()

	if not config:
		return ""

	layout = config.get_layout_type()
	menu_position = config.get_menu_position()
	icons = config.get_visible_icons()
	logo = config.get_logo_data()
	cta = config.get_cta_data()
	colors = config.get_header_colors()

	# Build theme variables + header HTML
	# Theme variables are included here so ALL pages that render the header
	# (Builder pages + Webshop pages) get consistent fonts and colors
	theme_css = get_theme_css(config)
	header_html = frappe.render_template(
		"unpress_core/templates/includes/header_footer/header.html",
		{
			"config": config,
			"layout": layout,
			"menu_position": menu_position,
			"icons": icons,
			"logo": logo,
			"cta": cta,
			"colors": colors,
			"menu_items": config.menu_items or [],
			"sticky": config.sticky_header,
			"header_style": config.get("header_style") or "Classic",
			"header_scroll": config.get("header_scroll") or "Hide going down",
		}
	)
	return theme_css + header_html


@frappe.whitelist(allow_guest=True)
def render_footer(config=None) -> str:
	"""
	Render the footer HTML from configuration.

	Args:
		config: WebsiteHeaderFooterConfig document or None to fetch it

	Returns:
		HTML string for the footer
	"""
	if config is None:
		config = get_header_footer_config()

	if not config:
		return ""

	logo = config.get_footer_logo_data() if config.show_footer_logo else None
	social_links = config.get_social_links()
	copyright_text = config.get_copyright_text()

	# Where the footer menu comes from. A site with four links does not want to
	# retype them; a site whose footer should carry legal pages the header does
	# not show needs its own set. Both are legitimate, so it is a choice.
	source = config.get("footer_menu_source") or "Custom links"
	footer_columns = {}
	if source == "Same as header":
		footer_columns[_("Menu")] = list(config.menu_items or [])
	elif source == "Custom links":
		for link in (config.footer_links or []):
			column = link.column_name or _("Links")
			if column not in footer_columns:
				footer_columns[column] = []
			footer_columns[column].append(link)

	return frappe.render_template(
		"unpress_core/templates/includes/header_footer/footer.html",
		{
			"config": config,
			"template": config.footer_template,
			"logo": logo,
			"description": config.footer_description,
			"copyright_text": copyright_text,
			"social_links": social_links,
			"show_newsletter": config.show_newsletter,
			"newsletter_title": config.newsletter_title,
			"newsletter_placeholder": config.newsletter_placeholder,
			"footer_columns": footer_columns,
			# an embed the client already has — a newsletter form, a booking
			# widget. Rendered as-is: it is their code, not ours to sanitise
			# into uselessness.
			"footer_html": config.get("footer_html") if config.get("show_footer_html") else None,
		}
	)


def get_header_css(config=None) -> str:
	"""Get the CSS for the header component."""
	if config is None:
		config = get_header_footer_config()

	colors = config.get_header_colors() if config else {"bg": "#1a1a1a", "text": "#ffffff"}

	return frappe.render_template(
		"unpress_core/templates/includes/header_footer/header_styles.html",
		{"colors": colors}
	)


def get_footer_css(config=None) -> str:
	"""Get the CSS for the footer component."""
	if config is None:
		config = get_header_footer_config()

	footer_colors = config.get_footer_colors() if config else {"bg": "#ffffff", "text": "#1a1a1a"}

	return frappe.render_template(
		"unpress_core/templates/includes/header_footer/footer_styles.html",
		{"footer_colors": footer_colors}
	)


def get_theme_css(config=None) -> str:
	"""Get the CSS for theme variables injection.

	Returns CSS with :root variables compatible with WebShop.
	"""
	if config is None:
		config = get_header_footer_config()

	theme = config.get_theme_data() if config else {
		"primary_color": "#6c5ce7",
		"secondary_color": "#00b894",
		"background_color": "#ffffff",
		"text_color": "#1a1a1a",
		"heading_font": "Inter",
		"body_font": "Inter",
		"radius_style": "Subtle",
		"shadow_style": "Soft",
		"button_hover": "Darken",
		"motion_style": "Calm",
	}

	return frappe.render_template(
		"unpress_core/templates/includes/header_footer/theme_variables.html",
		{"theme": theme}
	)


@frappe.whitelist(allow_guest=True)
def render_theme_variables(config=None) -> str:
	"""Render theme CSS variables for injection into pages.

	Args:
		config: WebsiteHeaderFooterConfig document or None to fetch it

	Returns:
		HTML string with <style> tag containing CSS variables
	"""
	return get_theme_css(config)


# SVG Icons for header/footer
ICONS = {
	"search": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>''',

	"user": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>''',

	"wishlist": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>''',

	"cart": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg>''',

	"menu": '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>''',

	"close": '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>''',

	"facebook": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>''',

	"twitter": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"/></svg>''',

	"instagram": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="20" x="2" y="2" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/></svg>''',

	"linkedin": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg>''',

	"youtube": '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><path d="m10 15 5-3-5-3z"/></svg>''',
}


def get_icon(name: str) -> str:
	"""Get SVG icon by name."""
	return ICONS.get(name, "")


@frappe.whitelist(allow_guest=True)
def get_editor_header_html():
	"""Get header HTML with styles for the Builder editor preview.

	Returns a dict with:
	- html: The header HTML
	- css: The header CSS styles
	- configured: Whether the config is set up
	"""
	config = get_header_footer_config()
	if not config or not config.header_layout:
		return {"configured": False, "html": "", "css": ""}

	html = render_header(config)
	css = get_header_css(config)

	return {
		"configured": True,
		"html": html,
		"css": css,
	}


@frappe.whitelist(allow_guest=True)
def get_editor_footer_html():
	"""Get footer HTML with styles for the Builder editor preview.

	Returns a dict with:
	- html: The footer HTML
	- css: The footer CSS styles
	- configured: Whether the config is set up
	"""
	config = get_header_footer_config()
	if not config or not config.footer_template:
		return {"configured": False, "html": "", "css": ""}

	html = render_footer(config)
	css = get_footer_css()

	return {
		"configured": True,
		"html": html,
		"css": css,
	}


# --- Site-chrome hooks for the page generator -------------------------------
# The pristine `unpress` builder branch exposes two optional jinja hooks in
# webpage.html (render_site_header/render_site_footer). These wrappers
# reproduce the version-15 generator logic exactly, so rendering matches
# the host byte-for-byte while the whole subsystem lives in this app.

def render_site_header(is_template_page=False, standalone=False) -> str:
	"""The site header.

	`standalone` is for pages Builder does not render — the blog, a portal
	page. Two of the header presets deliberately pull the page up underneath
	themselves, because a generated page opens on a hero built to sit under
	the bar. A frappe web page has no hero, so its first line would land
	behind the header; these pages get a spacer instead.
	"""
	if is_template_page:
		return ""
	config = get_header_footer_config()
	if not config or not config.header_layout:
		return ""

	html = get_header_css(config) + render_header(config)
	if standalone and (config.get("header_style") or "Classic") in ("Floating", "Transparent"):
		html += '<div class="site-header__spacer" aria-hidden="true"></div>'
	return html


def render_site_footer(is_template_page=False) -> str:
	if is_template_page:
		return ""
	config = get_header_footer_config()
	if not config or not config.footer_template:
		return ""
	return get_footer_css(config) + render_footer(config)
