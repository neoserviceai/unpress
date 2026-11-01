# Custom fields the ported AI generation writes on Builder Page (the fork
# carried them in its own doctype JSON; as an app we add them as custom fields),
# plus the Studio AI settings on Builder Settings (edited from the builder
# Settings > AI tab — resolution order documented in ai/config.py: site_config
# always wins over these, so managed fleets stay pinned).
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_custom_fields():
	if not frappe.db.exists("DocType", "Builder Page"):
		return
	create_custom_fields(
		{
			"Builder Page": [
				{
					"fieldname": "ai_generated_at",
					"fieldtype": "Datetime",
					"label": "AI Generated At",
					"read_only": 1,
					"hidden": 1,
				},
				{
					"fieldname": "ai_blocks_hash",
					"fieldtype": "Data",
					"label": "AI Blocks Hash",
					"read_only": 1,
					"hidden": 1,
				},
			],
			# No `default` on any of these on purpose: empty means "use the code
			# default" (ai/config.py DEFAULTS), so upgrading the defaults never
			# requires a data migration.
			"Builder Settings": [
				{
					"fieldname": "unpress_ai_provider",
					"fieldtype": "Select",
					"label": "AI Provider",
					# codex belongs here: a Select silently drops a value that is
					# not in its options, so picking the ChatGPT subscription in
					# the UI looked like it worked and saved nothing.
					"options": "\nopenai\nollama\ncodex",
					"insert_after": "ai_api_key",
					"description": "Empty = OpenAI-compatible API (default)",
				},
				{
					"fieldname": "unpress_ai_base_url",
					"fieldtype": "Data",
					"label": "AI API Base URL",
					"insert_after": "unpress_ai_provider",
					"description": "Empty = Moonshot (https://api.moonshot.ai/v1)",
				},
				{
					"fieldname": "unpress_ai_brief_model",
					"fieldtype": "Data",
					"label": "AI Brief Model",
					"insert_after": "unpress_ai_base_url",
					"description": "Model for the creative brief. Empty = kimi-k3",
				},
				{
					"fieldname": "unpress_ai_page_model",
					"fieldtype": "Data",
					"label": "AI Page Model",
					"insert_after": "unpress_ai_brief_model",
					"description": "Model for page generation. Empty = kimi-k2.7-code",
				},
				{
					# How hard the model thinks before answering. The single
					# biggest lever on both quality and wall-clock, and it was
					# only reachable from site_config until now.
					"fieldname": "unpress_ai_reasoning_effort",
					"fieldtype": "Select",
					"label": "AI Reasoning Effort",
					"options": "\nminimal\nlow\nmedium\nhigh",
					"insert_after": "unpress_ai_page_model",
					"description": "How long the model thinks before answering. Empty = the provider decides.",
				},
				{
					"fieldname": "unpress_ai_output_language",
					"fieldtype": "Data",
					"label": "AI Content Language",
					"insert_after": "unpress_ai_reasoning_effort",
					"description": "Language of the generated content. Empty = French",
				},
				# Images: bring your own backend. No default endpoint ships with
				# the app — an OpenAI-compatible /v1/images/generations URL
				# (OpenAI, a local Ollama, any gateway) or a ComfyUI server.
				{
					"fieldname": "unpress_ai_image_enabled",
					"fieldtype": "Check",
					"label": "Generate images with AI",
					"insert_after": "unpress_ai_output_language",
					"description": "Replace placeholders with generated images after a site is built",
				},
				{
					"fieldname": "unpress_ai_image_provider",
					"fieldtype": "Select",
					"label": "Image Backend",
					"options": "\nAPI\ncodex",
					"insert_after": "unpress_ai_image_enabled",
					"description": "codex = the local Codex CLI (ChatGPT plan). Empty/API = the endpoint below",
				},
				{
					"fieldname": "unpress_ai_image_base_url",
					"fieldtype": "Data",
					"label": "Image API Base URL",
					"insert_after": "unpress_ai_image_provider",
					"description": "OpenAI-compatible host, e.g. https://api.openai.com or http://localhost:11434",
				},
				{
					"fieldname": "unpress_ai_image_api_key",
					"fieldtype": "Password",
					"label": "Image API Key",
					"insert_after": "unpress_ai_image_base_url",
				},
				{
					"fieldname": "unpress_ai_image_model",
					"fieldtype": "Data",
					"label": "Image Model",
					"insert_after": "unpress_ai_image_api_key",
					"description": "e.g. gpt-image-1, or x/flux2-klein:latest on a local Ollama",
				},
				{
					"fieldname": "unpress_ai_image_size",
					"fieldtype": "Data",
					"label": "Image Size",
					"insert_after": "unpress_ai_image_model",
					"description": "Empty = 1024x1024",
				},
			],
		},
		ignore_validate=True,
	)
	ensure_studio_branding()


def ensure_studio_branding():
	"""Brand the site as Unpress Studio (login page, titles) — idempotent.

	Only fills values that are still empty or Frappe's own defaults, so a
	user who set their own name/logo is never overwritten.
	"""
	if not frappe.db.exists("DocType", "Website Settings"):
		return
	ws = frappe.get_doc("Website Settings")
	changed = False
	if not ws.app_name or ws.app_name in ("Frappe", "Frappe Framework"):
		ws.app_name = "Unpress Studio"
		changed = True
	# The wordmark here, the square icon on the favicon below — the login slot
	# constrains height and lets width run, so a square asset shrinks the word
	# inside it to nothing. Measured on a fresh install: illegible at 32px.
	if not ws.app_logo or ws.app_logo == "/assets/unpress_core/images/unpress-icon.svg":
		ws.app_logo = "/assets/unpress_core/images/unpress-logo.svg"
		changed = True
	# without this the desk and the login page keep Frappe's favicon, which is
	# the framework's brand on a page that says Unpress everywhere else
	if not ws.get("favicon"):
		ws.favicon = "/assets/unpress_core/images/unpress-icon.svg"
		changed = True
	# Hold the root until the site has a real home. Frappe falls back to the
	# login form when this is empty, so the front door of a fresh install was
	# an administration form — measured on a from-scratch install, `/` served
	# `<title>Login</title>`. Generation writes the real home page here, so
	# this yields on its own and is never seen again.
	if not ws.home_page:
		ws.home_page = "welcome"
		changed = True
	if changed:
		ws.flags.ignore_mandatory = True
		ws.save(ignore_permissions=True)


# The two Web Templates frappe's base.html renders in place of its own navbar
# and footer. They hold one call each: the chrome itself is built by
# hf_utils, so a page that goes through base.html and a Builder page render
# exactly the same header — there is no second implementation to drift.
WEB_CHROME_TEMPLATES = (
	{
		"name": "Site Header",
		"template": (
			"{%- if render_site_header is defined -%}{{ render_site_header(standalone=True) }}{%- endif -%}"
			"{%- if render_page_header is defined -%}{{ render_page_header() }}{%- endif -%}"
		),
	},
	{
		"name": "Site Footer",
		"template": "{%- if render_site_footer is defined -%}{{ render_site_footer() }}{%- endif -%}",
	},
)


def ensure_web_chrome_templates():
	"""Create (or refresh) the header/footer Web Templates."""
	if not frappe.db.exists("DocType", "Web Template"):
		return

	for spec in WEB_CHROME_TEMPLATES:
		if frappe.db.exists("Web Template", spec["name"]):
			doc = frappe.get_doc("Web Template", spec["name"])
			if doc.template != spec["template"]:
				doc.template = spec["template"]
				doc.save(ignore_permissions=True)
			continue

		doc = frappe.new_doc("Web Template")
		doc.name = spec["name"]
		doc.template = spec["template"]
		doc.type = "Section"
		# standard=0 keeps the body in the database; a standard template would
		# have to live in a fixed file path and we want it versioned with the app
		doc.standard = 0
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
