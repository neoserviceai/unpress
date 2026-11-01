app_name = "unpress_core"
app_title = "Unpress Core"
app_publisher = "Neoservice"
app_description = "Unpress core: static site export and deploy adapters"
app_email = "hello@neoservice.ai"
app_license = "AGPL-3.0"

# Fallback branding when Website Settings has no explicit app_logo.
# The WORDMARK, not the square icon: frappe's login slot is `max-height: 32px;
# width: auto`, so a square asset renders 32x32 and the word inside it becomes
# unreadable. The wordmark renders 145x32 and reads. The square icon is right
# for the favicon, where the slot really is square.
app_logo_url = "/assets/unpress_core/images/unpress-logo.svg"

# First-run experience: after login, land in the Studio
on_session_creation = "unpress_core.overrides.set_home_after_login"

before_request = [
	"unpress_core.overrides.desk_redirect",
	# a plugin that is off does not serve its public routes
	"unpress_core.plugins.route_guard",
]

doc_events = {
	"Builder Page": {
		"on_update": "unpress_core.publish_sync.on_builder_page_update",
	},
	"Website Settings": {
		"on_update": "unpress_core.hf_utils.menu_integration.sync_from_website_settings",
	},
}

# Extension point for the AI prompt. Any app installed on the bench can list a
# dotted path here to append its own markdown block (its shortcodes, its domain
# vocabulary, whatever the model should know about). Signature:
#
#     def contribute(site_type: str | None = None) -> str
#
# A contributor that takes no argument works too. The path has to live inside an
# installed app — frappe.get_attr refuses anything else — so a stale entry can
# only ever log a warning, never reach outside the bench.
#
# unpress_core never imports a host application; the host declares itself here.
unpress_ai_prompt_context = []

# Site chrome (header/footer/theme). The doctypes live here, so a host app that
# wants the same subsystem installs unpress_core rather than copying it.
jinja = {
	"methods": [
		"unpress_core.hf_utils.header_footer.render_header",
		"unpress_core.hf_utils.header_footer.render_footer",
		"unpress_core.hf_utils.header_footer.get_header_footer_config",
		"unpress_core.hf_utils.header_footer.render_site_header",
		"unpress_core.hf_utils.header_footer.render_site_footer",
		"unpress_core.page_header.render_page_header",
		"unpress_core.page_header.render_builder_page_header",
	]
}
update_website_context = [
	"unpress_core.site_chrome.inject_site_chrome",
	# the blog wears the site's design: our templates, chosen after the app's
	"unpress_core.blog_chrome.apply",
]
# The site's tokens dressing the markup other apps' web views emit (the blog's
# cards, its article page). Scoped to selectors we do not own.
#
# Cache-busted by content hash, the same trick the logo uses: /assets is served
# with a long max-age, so without this a visitor keeps yesterday's stylesheet
# after a deploy and the site looks half-updated. Computed at import, so a
# restart after deploying picks up the new hash.
def _asset_version(relative_path: str) -> str:
	import hashlib
	import os

	full = os.path.join(os.path.dirname(__file__), "public", relative_path)
	try:
		with open(full, "rb") as handle:
			return hashlib.md5(handle.read()).hexdigest()[:8]
	except OSError:
		return "0"


web_include_css = f"/assets/unpress_core/css/web_pages.css?v={_asset_version('css/web_pages.css')}"
doctype_js = {"Website Settings": "public/js/website_settings.js"}
after_migrate = [
	"unpress_core.setup.ensure_custom_fields",
	"unpress_core.setup.ensure_web_chrome_templates",
	"unpress_core.plugins.sync_plugins",
]
after_install = "unpress_core.setup.ensure_custom_fields"
after_app_install = "unpress_core.plugins.sync_plugins"
