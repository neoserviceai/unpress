"""Legacy site chrome injection for migrated client sites.

Some sites — WordPress migrations especially — embed a Builder
navbar/footer component on their Builder pages AND expect the same chrome plus the
Builder CSS stack (DaisyUI/Tailwind CDN, reset, variables) on non-Builder pages
(webshop /all-products, cart, item pages...).

The whole hook is a no-op unless the site opts in via site_config:

    "builder_legacy_site_chrome": 1

so fleet instances without legacy sites are unaffected.
"""

import json

import frappe

# CSS fixes shipped with the legacy chrome. Embedded BOTH in _head_html (Builder
# pages render it) and in navbar_html (webshop/system pages render the navbar Web
# Template but NOT _head_html — without this the search bar keeps the component's
# dark-header defaults: 260px wide, translucent, white-on-white input).
LEGACY_FIXES_CSS = (
	# Header product search must be full-width on ALL pages (webshop shop pages
	# e.g. /magasin render the search .dropdown as inline-block, collapsing it).
	"<style>html body .webshop-search-component .dropdown.w-100,"
	"html body .webshop-search-component .input-group>.dropdown{display:block !important;width:100% !important}"
	"html body .webshop-search-component .dropdown.w-100>.form-control{width:100% !important}</style>"
	# Avatar letter vertical centering on Builder pages (builder reset forces
	# .standard-image to display:block, dropping the flex centering used on shop pages).
	"<style>html body .avatar .standard-image,"
	"html body .my-account-avatar .standard-image"
	"{display:flex !important;align-items:center !important;justify-content:center !important}</style>"
	# Navbar search widget (builder header_footer search_bar component): the stock
	# component caps at 260-300px and themes for dark headers via CSS vars. Legacy
	# navbars place it on a colored band and expect the original full-width white bar.
	"<style>html body .builder-search-bar{width:100% !important;max-width:100% !important}"
	"html body .builder-search-bar__wrapper{background:#fff !important;border:1px solid #fff !important;"
	"height:44px;border-radius:8px}"
	"html body .builder-search-bar__wrapper:focus-within{box-shadow:0 0 0 3px rgba(0,0,0,.08) !important}"
	# border/box-shadow: webshop's theme styles bare inputs, drawing a second box
	# inside the wrapper; the native webkit clear button duplicates the component's.
	"html body .builder-search-bar__input{background:transparent !important;color:#1f2937 !important;"
	"border:none !important;outline:none !important;box-shadow:none !important;height:auto !important}"
	"html body .builder-search-bar__input::-webkit-search-cancel-button{-webkit-appearance:none;display:none}"
	"html body .builder-search-bar__input::placeholder{color:#9ca3af}"
	"html body .builder-search-bar__icon{color:#9ca3af !important}</style>"
	# User avatar: the component colors it var(--primary-color, #2563eb). Config-driven
	# headers (theme_variables.html) define that var on every page; legacy embedded
	# navbars don't, so each page falls back differently (blue on Builder pages,
	# frappe gray-900 on webshop pages). Pin the original neutral look everywhere.
	"<style>html body .builder-user-header__avatar .standard-image,"
	"html body .builder-user-header__avatar .avatar-frame"
	"{background:#f3f4f6 !important;color:#374151 !important}</style>"
	# Webshop/system pages underline links on hover; Builder pages don't. Keep the
	# injected chrome (navbar/footer web templates) consistent with Builder pages.
	"<style>html body .llm-navbar a:hover,html body .llm-navbar a:focus,"
	"html body .llm-footer a:hover,html body .llm-footer a:focus"
	"{text-decoration:none !important}</style>"
	# Webshop's base CSS gives <p> a 1rem bottom margin; Builder pages reset it.
	# Menu labels and footer lines in the injected chrome are <p> blocks, so the
	# margin skewed their vertical alignment on shop pages.
	"<style>html body .llm-navbar p,html body .llm-footer p"
	"{margin-top:0 !important;margin-bottom:0 !important}</style>"
)


def get_builder_component_html(component_name):
	"""Get rendered HTML from a Builder Component.

	Tries webshop's ``get_builder_page_content`` helper first (handles Jinja
	rendering, styles and caching), then falls back to direct component
	rendering via ``get_block_html``.

	Args:
		component_name (str): Builder Component name (e.g. "navbar", "footer")

	Returns:
		str: Rendered HTML or empty string if not found
	"""
	try:
		# Try to use webshop's helper function if available
		try:
			builder_data = frappe.call(
				"webshop.webshop.utils.builder.get_builder_page_content",
				route=component_name,
				use_cache=True,
			)

			if builder_data and builder_data.get("success"):
				html_parts = []

				# Add global styles
				if builder_data.get("global_style"):
					html_parts.append(f"<style>\n{builder_data['global_style']}\n</style>")

				# Add component styles
				if builder_data.get("style"):
					html_parts.append(builder_data["style"])

				# Add client styles
				for style in builder_data.get("client_styles", []):
					html_parts.append(f"<style>\n{style.get('content', '')}\n</style>")

				# Add HTML content
				content = builder_data.get("content", "")

				# Webshop skips Jinja rendering for includes, assuming the parent template
				# will render them. But our parent template {{ navbar_html }} doesn't
				# interpret Jinja, so render includes here.
				if content and ("{% " in content or "{{ " in content):
					from frappe.utils.jinja import render_template

					try:
						ctx = builder_data.get("page_data", {}) or {}
						content = render_template(content, ctx)
					except Exception as e:
						frappe.log_error("Legacy chrome Jinja render error", f"Component {component_name}: {e}")

				if content:
					html_parts.append(content)

				return "\n".join(html_parts)
		except Exception:
			# Webshop helper not available, fall back to direct rendering
			pass

		# Fallback: direct component rendering
		component = frappe.db.get_value(
			"Builder Component",
			{"component_name": component_name},
			["name", "block"],
			as_dict=True,
		)

		if not component or not component.block:
			return ""

		block_data = json.loads(component.block)

		from builder.builder.doctype.builder_page.builder_page import get_block_html

		result = get_block_html(block_data)

		if isinstance(result, tuple) and len(result) >= 2:
			html = result[0]
			styles = result[1]
		else:
			html = result
			styles = ""

		# Render Jinja directives ({% include %}, {{ vars }})
		if "{% " in html or "{{ " in html:
			from frappe.utils.jinja import render_template

			html = render_template(html, {})

		if styles:
			return f"{html}\n{styles}"

		return html
	except Exception as e:
		frappe.log_error("Legacy chrome component error", f"Component {component_name}: {e}")
		return ""


def inject_site_chrome(context):
	"""``update_website_context`` hook — inject legacy chrome on all web pages.

	Sets the LLM Navbar/Footer Web Templates (rendered by frappe's base.html on
	non-Builder pages), exposes the rendered Builder navbar/footer components to
	those templates, and prepends the Builder CSS stack to ``_head_html``.

	No-op unless site_config sets ``builder_legacy_site_chrome``.
	"""
	if not frappe.conf.get("builder_legacy_site_chrome"):
		return _inject_config_chrome(context)

	# website switch: an offline site (website_online=0, the fleet
	#//// default) leaks nothing — the login page and every remaining web page
	#//// render bare, no site header/footer ("no website = just a login page",
	#//// directive 2026-07-10, seen live on a site's login page). Staff keeps
	#//// the chrome (faithful preview), same contract as get_header_footer_config.
	profile = getattr(frappe.local, "website_profile_doc", None)
	if profile is not None and "website_online" in profile and not profile.get("website_online"):
		roles = frappe.get_roles()
		if "System Manager" not in roles and "Website Manager" not in roles:
			return

	# Navbar and footer Web Templates for non-Builder pages (frappe base.html
	# renders navbar_template/footer_template). The templates are created by the
	# add_llm_chrome_web_templates patch and just print the variables below.
	context["navbar_template"] = "LLM Navbar"
	context["footer_template"] = "LLM Footer"

	# Rendered Builder component HTML consumed by the Web Templates. Prefix the
	# CSS fixes to the navbar so non-Builder pages (which don't render _head_html)
	# get them too.
	navbar_html = get_builder_component_html("navbar")
	if navbar_html:
		navbar_html = LEGACY_FIXES_CSS + navbar_html
	context["navbar_html"] = navbar_html
	context["footer_html"] = get_builder_component_html("footer")

	if not context.get("_head_html"):
		context["_head_html"] = ""

	builder_css_tags = ""
	head_html = str(context.get("_head_html", ""))

	# DaisyUI + Tailwind for template-based components (navbar, hero, footer, cards...)
	if "daisyui" not in head_html:
		# DaisyUI CSS (must be loaded before Tailwind)
		builder_css_tags += (
			'<link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css"'
			' rel="stylesheet" type="text/css" />'
		)
		builder_css_tags += '<script src="https://cdn.tailwindcss.com"></script>'

	# Builder reset CSS - normalizes browser defaults
	if "builder/reset.css" not in head_html:
		builder_css_tags += '<link rel="stylesheet" href="/assets/builder/reset.css?v=1">'

	# Builder variables CSS - CSS custom properties used by components
	if "builder_assets/variables.css" not in head_html:
		builder_css_tags += '<link rel="stylesheet" href="/builder_assets/variables.css">'

	# CSS fixes (search bar, avatar...) for Builder pages; non-Builder pages get
	# them via navbar_html above.
	builder_css_tags += LEGACY_FIXES_CSS

	context["_head_html"] = builder_css_tags + context["_head_html"]


# ---------------------------------------------------------------------------
# The config-driven chrome on pages Builder does not render
# ---------------------------------------------------------------------------
#
# A Builder page calls render_site_header/render_site_footer from its own
# template. Every other web page — the blog, a portal page, login — goes
# through frappe's base.html, which renders `navbar_template` / `footer_template`
# and knows nothing about us. Without this, installing the blog plugin gives a
# /blog that looks like a different website: no menu, no logo, no footer.
#
# Two Web Templates carry the call (see setup.ensure_web_chrome_templates); the
# hook just points base.html at them.

NAVBAR_TEMPLATE = "Site Header"
FOOTER_TEMPLATE = "Site Footer"


def _inject_config_chrome(context):
	"""Point frappe's base.html at the site's own header and footer."""
	# A site that never configured the chrome keeps frappe's default navbar —
	# this must not redecorate benches that do not use the subsystem.
	try:
		from unpress_core.hf_utils.header_footer import get_header_footer_config

		config = get_header_footer_config()
	except Exception:
		return
	if not config or not config.get("header_layout"):
		return

	# The page header renders inside a Web Template, which has its own scope and
	# cannot see this dict. Stash it where render_page_header can find it.
	frappe.local.page_header_context = context

	# An explicit choice by the page wins: the Builder's own generator template
	# renders the chrome itself, and portal pages may set their own.
	if not context.get("navbar_template") and frappe.db.exists("Web Template", NAVBAR_TEMPLATE):
		context["navbar_template"] = NAVBAR_TEMPLATE
	if not context.get("footer_template") and frappe.db.exists("Web Template", FOOTER_TEMPLATE):
		context["footer_template"] = FOOTER_TEMPLATE
