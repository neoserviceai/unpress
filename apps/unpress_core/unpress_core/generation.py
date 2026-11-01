import ipaddress
import json
import os
import socket
from io import BytesIO
from types import FunctionType, MethodType, ModuleType
from typing import Any
from urllib.parse import unquote, urlparse

import frappe
from frappe import _
import frappe.utils
import requests
from frappe.apps import get_apps as get_permitted_apps
from frappe.core.doctype.file.file import get_local_image
from frappe.core.doctype.file.utils import delete_file
from frappe.model.document import Document
from frappe.utils.caching import redis_cache
from frappe.utils.safe_exec import NamespaceDict, get_safe_globals
from PIL import Image
from werkzeug.wrappers import Response

from builder import builder_analytics
from builder.builder.doctype.builder_page.builder_page import BuilderPageRenderer
from builder.builder.doctype.builder_snapshot import builder_snapshot
from builder.utils import compact_json, has_page_read, has_page_write


@frappe.whitelist()
def get_versioned_doc(snapshot: str) -> dict:
	return builder_snapshot.get_versioned_doc(snapshot).as_dict()


# =============================================================================
# SITE TYPE CONFIGURATION CONSTANTS
# =============================================================================

# Default header/footer settings for each site type
SITE_TYPE_HEADER_FOOTER_DEFAULTS = {
	"one_page": {
		"header_style": "Transparent",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "None",
		"show_cta": True,
		"show_user": False,
		"show_wishlist": False,
		"show_cart": False,
		"footer_template": "Minimal",
		"sticky_header": True,  # Important for one-page navigation
	},
	"vitrine": {
		"header_style": "Classic",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "None",
		"show_cta": True,
		"show_user": False,
		"show_wishlist": False,
		"show_cart": False,
		"footer_template": "Standard",
	},
	"vitrine_user": {
		"header_style": "Classic",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "None",
		"show_cta": True,
		"show_user": True,
		"show_wishlist": False,
		"show_cart": False,
		"footer_template": "Standard",
	},
	"blog": {
		"header_style": "Minimal",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "Icon (overlay)",
		"show_cta": True,
		"show_user": True,
		"show_wishlist": False,
		"show_cart": False,
		"footer_template": "Standard",
	},
	"ecommerce": {
		"header_style": "Classic",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "Icon (overlay)",
		"show_cta": False,
		"show_user": True,
		"show_wishlist": True,
		"show_cart": True,
		"footer_template": "Extended",
	},
	"ecommerce_search": {
		"header_style": "Classic",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "Search Bar (inline)",
		"show_cta": False,
		"show_user": True,
		"show_wishlist": True,
		"show_cart": True,
		"footer_template": "Extended",
	},
	"saas": {
		"header_style": "Floating",
		"header_layout": "Logo | Menu Right | Icons",
		"search_type": "None",
		"show_cta": True,
		"show_user": True,
		"show_wishlist": False,
		"show_cart": False,
		"footer_template": "Extended",
	},
	"portfolio": {
		"header_style": "Minimal",
		"header_layout": "Logo | Menu Center | Icons",
		"search_type": "None",
		"show_cta": True,
		"show_user": False,
		"show_wishlist": False,
		"show_cart": False,
		"footer_template": "Minimal",
	},
}

# Default pages to generate for each site type
# Page configurations by site type
# Note: The AI has full creative freedom for sections - we only define pages and routes
DEFAULT_PAGES_BY_SITE_TYPE = {
	"one_page": [
		# Single page with all sections - menu will use anchor links
		{"title": "Accueil", "route": "home", "type": "one_page"},
	],
	"vitrine": [
		{"title": "Accueil", "route": "home", "type": "accueil"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Services", "route": "services", "type": "services"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
	"vitrine_user": [
		{"title": "Accueil", "route": "home", "type": "accueil"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Services", "route": "services", "type": "services"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
	"blog": [
		{"title": "Accueil", "route": "home", "type": "accueil"},
		{"title": "Articles", "route": "blog", "type": "blog"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
	"ecommerce": [
		{"title": "Accueil", "route": "home", "type": "accueil_ecommerce"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
	"ecommerce_search": [
		{"title": "Accueil", "route": "home", "type": "accueil_ecommerce"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
	"saas": [
		{"title": "Accueil", "route": "home", "type": "accueil"},
		{"title": "Fonctionnalités", "route": "features", "type": "features"},
		{"title": "Tarifs", "route": "pricing", "type": "pricing"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
	"portfolio": [
		{"title": "Accueil", "route": "home", "type": "accueil"},
		{"title": "Projets", "route": "projects", "type": "portfolio"},
		{"title": "À propos", "route": "about", "type": "about"},
		{"title": "Contact", "route": "contact", "type": "contact"},
	],
}


def _plugin_owned_routes() -> set:
	"""Routes a live plugin serves. The generator must not build on top of them.

	A site_type "blog" plans a page at route `blog`, and a Builder page wins
	over the blog app's index because custom page renderers are tried first —
	so generating that page would silently hide the blog the owner just turned
	on. When the plugin is off the route is free and the page is generated as
	before.
	"""
	try:
		from unpress_core.plugins import BUILT_IN_BY_NAME, is_enabled
	except ImportError:
		return set()

	owned = set()
	for name, spec in BUILT_IN_BY_NAME.items():
		prefix = (spec.get("route_prefix") or "").strip("/")
		if prefix and is_enabled(name):
			owned.add(prefix)
	return owned



def _save_brief_to_session(session_id, design_brief, **extra):
	"""Record the brief on the chat session.

	It is what every page was generated from, what the "generate the remaining
	pages" flow reads back, what the visual loop compares against — and, since
	the Studio can show it, the answer to "why does my site look like this?".

	It used to be written only on the progressive-mode early return, so an
	ordinary generation finished with an empty `saved_brief`. Saving it as soon
	as it exists also means a run that dies halfway still leaves its reasoning
	behind.
	"""
	if not (session_id and design_brief):
		return
	try:
		session_name = frappe.db.get_value("Builder Chat Session", {"session_id": session_id}, "name")
		if not session_name:
			return
		brief_json = (
			design_brief.model_dump_json()
			if hasattr(design_brief, "model_dump_json")
			else json.dumps(design_brief.__dict__, default=str)
		)
		frappe.db.set_value(
			"Builder Chat Session",
			session_name,
			{"saved_brief": brief_json, **extra},
			update_modified=False,
		)
		frappe.db.commit()
	except Exception as e:
		ai_log("warning", "Failed to save brief to session", error=str(e)[:200])


def optional_pages_for_site_type(site_type):
	"""The optional pages to offer, minus what a live plugin already provides.

	The "Blog" option builds a static listing page. With the blog plugin on,
	that is a second, emptier blog sitting next to the real one — worse than
	nothing, because the owner has to work out which is which.
	"""
	optional = OPTIONAL_PAGES_BY_SITE_TYPE.get(site_type, [])
	owned = _plugin_owned_routes()
	if not owned:
		return optional
	# a plugin owning /blog provides the blog; drop the page that duplicates it
	blocked_types = {"blog"} if "blog" in owned else set()
	return [
		page
		for page in optional
		if page.get("type") not in blocked_types
		and (page.get("route") or "").strip("/") not in owned
	]


def pages_for_site_type(site_type):
	"""The default page plan, minus whatever a plugin already serves."""
	pages = DEFAULT_PAGES_BY_SITE_TYPE.get(site_type, DEFAULT_PAGES_BY_SITE_TYPE["vitrine"])
	owned = _plugin_owned_routes()
	if not owned:
		return pages
	return [page for page in pages if (page.get("route") or "").strip("/") not in owned]


# Optional pages available per site type (proposed in chat, user selects)
OPTIONAL_PAGES_BY_SITE_TYPE = {
	"vitrine": [
		{"title": "FAQ", "route": "faq", "type": "faq", "description": "Frequently asked questions"},
		{"title": "Équipe", "route": "team", "type": "team", "description": "Team members presentation"},
		{"title": "Blog", "route": "articles", "type": "blog", "description": "Blog articles listing"},
		{"title": "Témoignages", "route": "testimonials", "type": "testimonials", "description": "Customer testimonials"},
	],
	"vitrine_user": [
		{"title": "FAQ", "route": "faq", "type": "faq", "description": "Frequently asked questions"},
		{"title": "Équipe", "route": "team", "type": "team", "description": "Team members presentation"},
		{"title": "Blog", "route": "articles", "type": "blog", "description": "Blog articles listing"},
		{"title": "Témoignages", "route": "testimonials", "type": "testimonials", "description": "Customer testimonials"},
	],
	"ecommerce": [
		{"title": "FAQ", "route": "faq", "type": "faq", "description": "Frequently asked questions"},
		{"title": "Livraison", "route": "shipping", "type": "custom", "description": "Shipping information"},
		{"title": "CGV", "route": "terms", "type": "custom", "description": "Terms and conditions"},
		{"title": "Blog", "route": "articles", "type": "blog", "description": "Blog articles listing"},
	],
	"ecommerce_search": [
		{"title": "FAQ", "route": "faq", "type": "faq", "description": "Frequently asked questions"},
		{"title": "Livraison", "route": "shipping", "type": "custom", "description": "Shipping information"},
		{"title": "CGV", "route": "terms", "type": "custom", "description": "Terms and conditions"},
		{"title": "Blog", "route": "articles", "type": "blog", "description": "Blog articles listing"},
	],
	"blog": [
		{"title": "FAQ", "route": "faq", "type": "faq", "description": "Frequently asked questions"},
		{"title": "Équipe", "route": "team", "type": "team", "description": "Team members presentation"},
		{"title": "Portfolio", "route": "portfolio", "type": "portfolio", "description": "Portfolio / projects showcase"},
	],
	"saas": [
		{"title": "FAQ", "route": "faq", "type": "faq", "description": "Frequently asked questions"},
		{"title": "Blog", "route": "articles", "type": "blog", "description": "Blog articles listing"},
		{"title": "Équipe", "route": "team", "type": "team", "description": "Team members presentation"},
		{"title": "Changelog", "route": "changelog", "type": "custom", "description": "Product changelog"},
	],
	"portfolio": [
		{"title": "Blog", "route": "articles", "type": "blog", "description": "Blog articles listing"},
		{"title": "Témoignages", "route": "testimonials", "type": "testimonials", "description": "Customer testimonials"},
		{"title": "Services", "route": "services", "type": "services", "description": "Services offered"},
	],
}


# =============================================================================
# AI GENERATION API (Creative AI with full freedom)
# =============================================================================

@frappe.whitelist()
def generate_page_blocks(
	prompt: str,
	theme: str = "modern",
	primary_color: str = None,
	secondary_color: str = None,
	provider: str = None,
	model: str = None,
):
	"""
	Generate page blocks using creative AI generation.

	The AI has full creative freedom to design unique pages.
	Header and footer are managed via Website Header Footer Config.

	Args:
		prompt: Description of the desired page
		theme: Visual theme (modern, neobrutalist, glassmorphism, minimal, corporate, creative)
		primary_color: Custom primary color (e.g., "#6c5ce7")
		secondary_color: Custom secondary color (e.g., "#00b894")
		provider: AI provider override (ollama, openai)
		model: Model name override

	Returns:
		list[dict]: Generated Frappe Builder blocks
	"""
	from unpress_core.ai.generators.page_generator import PageGenerator

	generator = PageGenerator(provider=provider, model=model)

	blocks = generator.generate_page(
		prompt=prompt,
		theme=theme,
		primary_color=primary_color,
		secondary_color=secondary_color,
	)

	return blocks






@frappe.whitelist()
def get_ai_themes():
	"""
	Get available AI generation themes.

	Returns:
		list[dict]: List of available themes with descriptions
	"""
	from unpress_core.ai.design_system.themes import THEMES

	return [
		{
			"name": name,
			"label": theme.get("name", name.title()),
			"description": theme.get("description", ""),
		}
		for name, theme in THEMES.items()
	]


@frappe.whitelist()
def check_ai_provider_status():
	"""
	Check the status of configured AI providers.

	Returns:
		dict: Status of each provider
	"""
	result = {
		"ollama": {"available": False, "message": "Not configured"},
		"openai": {"available": False, "message": "Not configured"},
	}

	# Check Ollama
	try:
		from unpress_core.ai.providers.ollama_provider import OllamaProvider
		from unpress_core.ai.config import get_ai_settings

		settings = get_ai_settings()
		if settings.provider == "ollama" or settings.base_url:
			provider = OllamaProvider(
				base_url=settings.base_url,
				model=settings.model
			)
			if provider.is_available():
				result["ollama"] = {
					"available": True,
					"message": f"Connected - Model: {settings.model}",
					"model": settings.model
				}
			else:
				result["ollama"] = {
					"available": False,
					"message": f"Server running but model '{settings.model}' not found"
				}
	except Exception as e:
		result["ollama"]["message"] = str(e)

	# Check OpenAI-compatible (site_config > Builder Settings UI > defaults)
	try:
		from unpress_core.ai.config import get_ai_settings

		settings = get_ai_settings()
		if settings.provider == "openai" and settings.api_key:
			result["openai"] = {
				"available": True,
				"message": f"API key configured - Model: {settings.model}",
				"model": settings.model,
				"page_model": settings.page_model,
				"base_url": settings.base_url,
			}
	except Exception as e:
		result["openai"]["message"] = str(e)

	return result


def _save_generated_png(content: bytes, prefix: str = "gen") -> str:
	"""Store raw image bytes as a public File and return its /files/ URL."""
	fdoc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{prefix}_{frappe.generate_hash(length=10)}.png",
			"is_private": 0,
			"content": content,
		}
	).insert(ignore_permissions=True)
	return fdoc.file_url


def generate_one_image(prompt: str, width: int = 1024, height: int = 576) -> str:
	"""One image, through whichever backend this site actually has.

	The site image worker picks between Codex, ComfyUI and an OpenAI-compatible
	endpoint. Anything else that wants a picture — an article cover — has to
	make the same choice, or it works on the developer's bench and silently
	produces nothing on a site configured differently.

	Returns the /files/ URL. Raises if no backend produced one.
	"""
	from unpress_core.ai.config import get_ai_settings, get_image_settings
	from unpress_core.ai.generators import comfyui_client
	from unpress_core.ai.logging import ai_log

	settings = get_image_settings()

	if settings.get("provider") == "codex":
		from unpress_core.ai.providers.codex_provider import CodexProvider

		ok, why = CodexProvider.login_status()
		if ok:
			provider = CodexProvider(reasoning_effort=get_ai_settings().reasoning_effort)
			# No model here: `settings["model"]` is the *image* model, which
			# belongs to the OpenAI-compatible path below. Codex draws through
			# its own plugin and refuses an image model on its `-m` flag.
			content = provider.generate_image_file(prompt, width=width, height=height)
			return _save_generated_png(content, prefix="codex")
		ai_log("warning", "Codex unavailable for image, falling back", reason=why)

	if comfyui_client.is_configured():
		healthy, why = comfyui_client.health()
		if healthy:
			return comfyui_client.generate_image(prompt, width=width, height=height)
		ai_log("warning", "ComfyUI unavailable for image, falling back", reason=why)

	from unpress_core.ai.generators.image_generator import ImageGenerator

	return ImageGenerator().generate(prompt=prompt, size=f"{width}x{height}").file_url


def _image_backend_available() -> bool:
	"""Is an image backend usable on this site? ComfyUI must be explicitly
	pointed at a server; otherwise an OpenAI-compatible endpoint must be
	enabled and reachable-looking (URL present)."""
	from unpress_core.ai.config import get_image_settings
	from unpress_core.ai.generators import comfyui_client

	settings = get_image_settings()
	if settings.get("provider") == "codex":
		from unpress_core.ai.providers.codex_provider import CodexProvider

		ok, _why = CodexProvider.login_status()
		if ok:
			return True
	if comfyui_client.is_configured():
		return True
	return bool(settings.get("enabled") and settings.get("base_url"))


def _enqueue_image_generation(placeholder_images: list, session_id: str = None) -> str:
	"""Queue the image worker and return its job id (shared by the automatic
	post-generation path and the chat's explicit trigger)."""
	img_job_id = f"img_gen_{frappe.generate_hash(length=10)}"

	_update_generation_status(img_job_id, {
		"status": "queued",
		"progress": 0,
		"total_images": len(placeholder_images),
		"images_completed": 0,
		"images_failed": 0,
		"current_image": None,
		"error": None,
	})

	if session_id:
		try:
			name = frappe.db.get_value("Builder Chat Session", {"session_id": session_id})
			if name:
				frappe.db.set_value("Builder Chat Session", name, "image_job_id", img_job_id)
		except Exception:
			pass

	# own queue: image jobs are minutes long and must not starve page generation
	frappe.enqueue(
		"unpress_core.generation._generate_images_worker",
		queue="long",
		timeout=5400,
		job_name=img_job_id,
		img_job_id=img_job_id,
		placeholder_images=placeholder_images,
	)
	from unpress_core.ai.logging import ai_log

	ai_log("info", "image generation queued", job_id=img_job_id, slots=len(placeholder_images))
	return img_job_id


@frappe.whitelist()
def test_image_connection():
	"""Validate the configured image backend without burning a generation."""
	from unpress_core.ai.config import get_image_settings
	from unpress_core.ai.generators import comfyui_client

	if comfyui_client.is_configured():
		ok, message = comfyui_client.health()
		return {"success": ok, "backend": "comfyui", "message": message}

	settings = get_image_settings()
	if not settings.get("enabled"):
		return {"success": False, "message": _("Image generation is turned off")}
	if not settings.get("base_url"):
		return {"success": False, "message": _("No image API base URL configured")}

	url = settings["base_url"].rstrip("/") + "/v1/models"
	headers = {}
	if settings.get("api_key"):
		headers["Authorization"] = f"Bearer {settings['api_key']}"
		headers["X-API-Key"] = settings["api_key"]
	try:
		resp = requests.get(url, headers=headers, timeout=15)
	except Exception as e:
		return {"success": False, "message": _("Connection failed: {0}").format(e)}
	if resp.status_code in (401, 403):
		return {"success": False, "message": _("Invalid API key (HTTP {0})").format(resp.status_code)}
	if not resp.ok:
		return {"success": False, "message": _("HTTP {0} from {1}").format(resp.status_code, url)}
	return {
		"success": True,
		"backend": "openai-compatible",
		"message": _("Connected — model: {0}, size: {1}").format(settings["model"], settings["size"]),
	}


@frappe.whitelist()
def test_ai_connection():
	"""
	Live connectivity test for the configured AI provider (Settings > AI).

	Uses the model-listing endpoint — free (no tokens), validates both the
	API key and the base URL. Moonshot, OpenAI and OpenRouter all serve
	GET /models; native Ollama serves GET /api/tags.
	"""
	from unpress_core.ai.config import get_ai_settings, validate_provider_config

	settings = get_ai_settings()
	ok, msg = validate_provider_config(settings)
	if not ok:
		return {"success": False, "message": msg}

	if settings.provider == "ollama":
		url = (settings.base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
	else:
		url = (settings.base_url or "https://api.moonshot.ai/v1").rstrip("/") + "/models"

	headers = {}
	if settings.api_key:
		headers["Authorization"] = f"Bearer {settings.api_key}"

	try:
		resp = requests.get(url, headers=headers, timeout=15)
	except Exception as e:
		return {"success": False, "message": _("Connection failed: {0}").format(e)}

	if resp.status_code == 200:
		return {
			"success": True,
			"message": _("Connected — brief model: {0}, page model: {1}").format(
				settings.model, settings.page_model
			),
		}
	if resp.status_code in (401, 403):
		return {"success": False, "message": _("Invalid API key (HTTP {0})").format(resp.status_code)}
	return {"success": False, "message": _("HTTP {0} from {1}").format(resp.status_code, url)}


@frappe.whitelist()
def generate_complete_site(
	prompt: str,
	site_name: str,
	site_type: str = "vitrine",
	theme: str = "modern",
	primary_color: str = None,
	secondary_color: str = None,
	logo_text: str = None,
	logo_image: str = None,
	cta_text: str = "Contact",
	cta_url: str = "/contact",
	social_links: str = None,
	provider: str = None,
	model: str = None,
	session_id: str = None,
	heading_font: str = None,
	body_font: str = None,
	pages_config: str = None,
	generation_mode: str = "full",
	inspiration_urls: str = None,
	replace_existing: str = "auto",
	website_profile: str = None,  # multi-site hosts: target Website Profile
):
	"""
	Generate a complete site asynchronously.

	replace_existing controls what happens to the site's current pages:
	- "auto" (default): replace silently only when every existing page is an
	  untouched AI generation; otherwise return confirmation_required without
	  queueing anything (the caller asks the user, then retries with "force")
	- "force": replace everything (template pages and hub staging always survive)
	- "none": additive — generate only the requested pages, leave the rest alone

	This function queues the site generation as a background job to avoid
	HTTP timeouts (Cloudflare 100s limit). Use get_site_generation_status()
	to poll for completion.

	Args:
		prompt: Description of the desired site
		site_name: Name of the site (used for logo if no logo_text provided)
		site_type: Type of site (vitrine, vitrine_user, blog, ecommerce, ecommerce_search, saas, portfolio)
		theme: Visual theme (modern, neobrutalist, glassmorphism, minimal, corporate, creative)
		primary_color: Primary color hex (e.g., "#6c5ce7")
		secondary_color: Secondary color hex (e.g., "#00b894")
		logo_text: Text logo (overrides site_name)
		logo_image: Image logo path (if provided, uses image instead of text)
		cta_text: Call-to-action button text
		cta_url: Call-to-action button URL
		social_links: JSON string with social media URLs {"facebook": "...", "instagram": "...", ...}
		provider: AI provider override (ollama, openai)
		model: Model name override
		session_id: Optional chat session ID to update on completion

	Returns:
		dict: {job_id: str, status: "queued"}
	"""
	# Generate a unique job ID
	job_id = f"site_gen_{frappe.generate_hash(length=10)}"

	print(f"[SITE_GEN] Starting generate_complete_site: job_id={job_id}, site_type={site_type}, site_name={site_name}")

	# Parse pages_config if provided as JSON string
	resolved_pages = None
	if pages_config:
		if isinstance(pages_config, str):
			resolved_pages = json.loads(pages_config)
		else:
			resolved_pages = pages_config
	if not resolved_pages:
		resolved_pages = pages_for_site_type(site_type)

	# Initialize job status in cache
	_update_generation_status(job_id, {
		"status": "queued",
		"progress": 0,
		"total_pages": len(resolved_pages),
		"current_page": None,
		"pages_created": [],
		"error": None,
		"site_name": site_name,
		"created_at": frappe.utils.now(),
		"generation_mode": generation_mode,
	})

	# regenerate decision — never silently destroy pages a user
	# designed or edited (see classify_existing_pages)
	if replace_existing not in ("auto", "force", "none"):
		frappe.throw(_("Invalid replace_existing value: {0}").format(replace_existing))
	if replace_existing == "auto":
		classes = classify_existing_pages(website_profile)  # multi-site
		if classes["protected"]:
			from unpress_core.ai.logging import ai_log

			ai_log("info", "Generation needs replace confirmation",
				   protected=len(classes["protected"]))
			return {
				"status": "confirmation_required",
				"protected_pages": classes["protected"],
				"untouched_pages": classes["untouched"],
				"message": _(
					"Some existing pages were designed or edited by hand. "
					"Confirm before replacing the whole site, or generate additively."
				),
			}

	# Enqueue the generation job
	# Note: job_id is a reserved parameter in frappe.enqueue() for RQ job naming
	# We pass our tracking ID as generation_job_id to avoid conflict
	frappe.enqueue(
		"unpress_core.generation._generate_complete_site_worker",
		queue="default",
		timeout=3600,  # 1 hour max (kimi model is slow)
		job_name=job_id,
		generation_job_id=job_id,  # Our tracking ID
		prompt=prompt,
		site_name=site_name,
		site_type=site_type,
		theme=theme,
		primary_color=primary_color,
		secondary_color=secondary_color,
		logo_text=logo_text,
		logo_image=logo_image,
		cta_text=cta_text,
		cta_url=cta_url,
		social_links=social_links,
		provider=provider,
		model=model,
		session_id=session_id,
		heading_font=heading_font,
		body_font=body_font,
		pages_config=json.dumps(resolved_pages),
		generation_mode=generation_mode,
		inspiration_urls=inspiration_urls,
		replace_existing=replace_existing,
		website_profile=website_profile,  # multi-site
	)

	print(f"[SITE_GEN] Job enqueued successfully: job_id={job_id}, mode={generation_mode}")

	return {
		"job_id": job_id,
		"status": "queued",
		"message": "Site generation started. Use get_site_generation_status() to track progress."
	}


def _update_generation_status(job_id: str, data: dict):
	"""Update the generation status in cache and broadcast via socketio."""
	cache_key = f"site_generation_{job_id}"
	# Stamp each update — the watchdog uses this to detect dead workers.
	data = dict(data)
	data["last_update"] = frappe.utils.now()
	frappe.cache().set_value(cache_key, data, expires_in_sec=14400)  # 4 hours TTL
	print(f"[SITE_GEN] Status update: job_id={job_id}, status={data.get('status')}, progress={data.get('progress')}%, step={data.get('current_step', '')[:50]}")

	# Push to the browser via frappe.realtime (socketio). The event name is
	# prefixed with the job_id so multiple concurrent generations don't
	# interfere. The frontend subscribes in start_generation_polling().
	try:
		frappe.publish_realtime(
			event=f"builder_gen_progress:{job_id}",
			message={**data, "job_id": job_id},
			user=frappe.session.user if getattr(frappe, "session", None) else None,
			after_commit=False,
		)
	except Exception as e:
		# Never let realtime failures break generation — polling still works.
		print(f"[SITE_GEN] publish_realtime failed: {e}")


def _get_generation_status(job_id: str) -> dict:
	"""Get the generation status from cache."""
	cache_key = f"site_generation_{job_id}"
	return frappe.cache().get_value(cache_key) or {"status": "not_found", "error": "Job not found"}


# Max minutes we allow a generation to be "running" without a cache update
# before the watchdog declares it dead. Workers can get OOM-killed, hit
# supervisorctl restart, lose their Moonshot HTTP connection — in all cases
# the RQ job stops updating the cache but the session stays "Generating"
# forever. The watchdog flips those to "Failed" so the UI can recover.
STUCK_GENERATION_TIMEOUT_MIN = 20


def check_stuck_generations():
	"""Find sessions stuck in 'Generating' and mark them Failed.

	Run every 10 minutes by the scheduler (see hooks.scheduler_events). A
	session is considered stuck when its cached status hasn't been updated
	for STUCK_GENERATION_TIMEOUT_MIN minutes — that's the telltale sign the
	RQ worker died mid-job.
	"""
	from datetime import timedelta
	from frappe.utils import get_datetime, now_datetime

	cutoff = now_datetime() - timedelta(minutes=STUCK_GENERATION_TIMEOUT_MIN)
	stuck_sessions = frappe.get_all(
		"Builder Chat Session",
		filters={"status": "Generating"},
		fields=["name", "session_id", "job_id", "modified"],
	)

	marked = 0
	for row in stuck_sessions:
		snapshot = _get_generation_status(row.job_id) if row.job_id else {}
		last_update_str = snapshot.get("last_update")

		# If the cache is fresh, the worker is still alive — leave it alone.
		if last_update_str:
			try:
				if get_datetime(last_update_str) > cutoff:
					continue
			except Exception:
				pass  # Bad timestamp → treat as stuck.

		# Also bail out if the session itself was modified recently (defensive).
		if row.modified and row.modified > cutoff:
			continue

		try:
			session = frappe.get_doc("Builder Chat Session", row.name)
			session.status = "Failed"
			session.generation_status = "failed"
			session.save(ignore_permissions=True)
			marked += 1
			if row.job_id:
				_update_generation_status(row.job_id, {
					**snapshot,
					"status": "failed",
					"error": f"Worker died — no update for >{STUCK_GENERATION_TIMEOUT_MIN} min",
				})
		except Exception as e:
			frappe.log_error("check_stuck_generations: session update failed", str(e))

	if marked:
		frappe.db.commit()
		print(f"[SITE_GEN] Watchdog marked {marked} stuck session(s) as Failed")


def _update_session_on_completion(session_id, job_id, status, created_pages):
	"""Update the Builder Chat Session document when generation completes or fails."""
	if not session_id:
		# Try to find session by job_id
		try:
			session_name = frappe.db.get_value(
				"Builder Chat Session", {"job_id": job_id}, "name"
			)
			if not session_name:
				return
		except Exception as e:
			frappe.log_error("Generation: session lookup failed", str(e))
			return
	else:
		session_name = frappe.db.get_value(
			"Builder Chat Session", {"session_id": session_id}, "name"
		)
		if not session_name:
			return

	try:
		session = frappe.get_doc("Builder Chat Session", session_name)
		session.generation_status = status.lower()
		session.generation_progress = 100 if status == "Completed" else 0
		session.status = status
		if created_pages:
			session.generated_pages = json.dumps(created_pages)
		session.save(ignore_permissions=True)
		frappe.db.commit()
		print(f"[SITE_GEN] Session {session_name} updated: status={status}, pages={len(created_pages)}")
	except Exception as e:
		frappe.log_error("Session update on completion failed", str(e))
		print(f"[SITE_GEN] Failed to update session: {e}")


def _generate_complete_site_worker(
	generation_job_id: str,
	prompt: str,
	site_name: str,
	site_type: str,
	theme: str,
	primary_color: str,
	secondary_color: str,
	logo_text: str,
	logo_image: str,
	cta_text: str,
	cta_url: str,
	social_links: str,
	provider: str,
	model: str,
	session_id: str = None,
	heading_font: str = None,
	body_font: str = None,
	pages_config: str = None,
	generation_mode: str = "full",
	inspiration_urls: str = None,
	replace_existing: str = "auto",
	website_profile: str = None,  # multi-site hosts: target Website Profile
):
	"""
	Background worker for site generation.

	This function runs in a background job and updates progress via cache.

	Args:
		generation_job_id: Our tracking ID for this generation job (not the RQ job_id)
		pages_config: JSON string of pages to generate (overrides DEFAULT_PAGES_BY_SITE_TYPE)
		generation_mode: "full" (all pages) or "progressive" (homepage first, then rest)
	"""
	# Use local variable for cleaner code
	job_id = generation_job_id

	frappe.logger("builder").info(f"Generation worker started: job={job_id}, session={session_id}")
	print(f"[SITE_GEN_WORKER] ===== WORKER STARTED =====")
	print(f"[SITE_GEN_WORKER] job_id={job_id}, site_type={site_type}, site_name={site_name}, mode={generation_mode}")

	from unpress_core.ai.generators.page_generator import PageGenerator
	from unpress_core.ai.config import get_ai_settings
	from unpress_core.ai.logging import ai_log

	# Log to dedicated file (survives worker crashes)
	ai_log("info", "=== SITE GENERATION STARTED ===",
		job_id=job_id, site_name=site_name, site_type=site_type, generation_mode=generation_mode)
	ai_log("info", "Configuration",
		theme=theme, provider=provider, model=model, primary_color=primary_color)

	# Get AI config NOW (before threads) - frappe.conf is only available in main thread
	print(f"[SITE_GEN_WORKER] Getting AI settings...")
	ai_config = get_ai_settings()
	print(f"[SITE_GEN_WORKER] AI Config: provider={ai_config.provider}, model={ai_config.model}")
	ai_log("info", "AI settings loaded",
		provider=ai_config.provider, model=ai_config.model)

	# Use provided pages_config or fall back to defaults
	if pages_config:
		if isinstance(pages_config, str):
			pages_config = json.loads(pages_config)
	else:
		pages_config = pages_for_site_type(site_type)
	total_pages = len(pages_config)
	print(f"[SITE_GEN_WORKER] Pages to generate: {total_pages} - {[p['title'] for p in pages_config]}")

	# Track generation time
	import time
	start_time = time.time()

	try:
		# Update status: starting
		_update_generation_status(job_id, {
			"status": "running",
			"progress": 0,
			"total_pages": total_pages,
			"current_step": "Deleting existing pages",
			"current_page": None,
			"pages_created": [],
			"error": None,
			"site_name": site_name,
			"started_at": frappe.utils.now(),
		})

		# =====================================================================
		# STEP 1: Delete ALL existing Builder Pages
		# =====================================================================
		ai_log("info", "Step 1: Deleting existing pages", replace_existing=replace_existing)
		print(f"[SITE_GEN_WORKER] Cleaning up existing Builder Pages (mode={replace_existing})...")
		# full-site generation replaces the previous site, but NEVER
		# template pages (the hub's catalog lives in this doctype!) nor the
		# hub's editorial staging ("Hub Inbox — <group>" folders). Pages a user
		# designed/edited (protected) are only removed in "force" mode; "none"
		# is additive and deletes nothing here.
		if replace_existing == "none":
			existing_pages = []
		else:
			classes = classify_existing_pages(website_profile)  # multi-site
			existing_pages = [p["name"] for p in classes["untouched"]]
			if replace_existing == "force":
				existing_pages += [p["name"] for p in classes["protected"]]
			elif classes["protected"]:
				# "auto" should have been confirmed upstream; play safe anyway
				ai_log("warning", "Auto mode with protected pages — keeping them",
					   kept=len(classes["protected"]))
		for page_name in existing_pages:
			try:
				frappe.delete_doc("Builder Page", page_name, ignore_permissions=True, force=True)
				print(f"[SITE_GEN_WORKER] Deleted page: {page_name}")
			except Exception as e:
				# If page has links, try to remove them first
				print(f"[SITE_GEN_WORKER] Could not delete {page_name}: {e}, trying to clear links...")
				try:
					frappe.db.delete("Dynamic Link", {"link_doctype": "Builder Page", "link_name": page_name})
					frappe.delete_doc("Builder Page", page_name, ignore_permissions=True, force=True)
					print(f"[SITE_GEN_WORKER] Deleted page after clearing links: {page_name}")
				except Exception as e2:
					print(f"[SITE_GEN_WORKER] Skipping page {page_name}: {e2}")
		frappe.db.commit()
		print(f"[SITE_GEN_WORKER] Cleanup complete")
		ai_log("info", "Deleted existing pages", count=len(existing_pages))

		# =====================================================================
		# STEP 2: Configure Website Header Footer Config
		# =====================================================================
		ai_log("info", "Step 2: Configuring header/footer")
		_update_generation_status(job_id, {
			"status": "running",
			"progress": 5,
			"total_pages": total_pages,
			"current_step": "Configuring header/footer",
			"current_page": None,
			"pages_created": [],
			"error": None,
			"site_name": site_name,
		})

		# multi-site: chrome goes to the profile's Variant when targeted
		config = _get_site_chrome_config(website_profile)

		# Apply site_type defaults
		defaults = SITE_TYPE_HEADER_FOOTER_DEFAULTS.get(site_type, SITE_TYPE_HEADER_FOOTER_DEFAULTS["vitrine"])
		for key, value in defaults.items():
			if hasattr(config, key):
				setattr(config, key, value)

		# Apply explicit parameters
		# Default to Image logo type (uses existing logo_image from config)
		config.logo_type = "Image"
		if logo_image:
			config.logo_image = logo_image
		# A full site generation IS a re-identification: this bench is now this
		# business. "Only write when empty" kept the FIRST site's brand forever
		# — measured on a bench that had generated three sites in a row, the
		# chrome still said "FC Colombier" while the pages were a glassblower's
		# and the contact card named a wine estate. Three identities, one site.
		if logo_text:
			config.logo_text = logo_text
		elif site_name:
			config.logo_text = site_name
		if hasattr(config, "footer_logo_text") and (logo_text or site_name):
			config.footer_logo_text = logo_text or site_name

		# Apply colors if provided
		if primary_color and hasattr(config, "primary_color"):
			config.primary_color = primary_color
		if secondary_color and hasattr(config, "secondary_color"):
			config.secondary_color = secondary_color

		# Header colors: use secondary (darker) as bg, white text for contrast
		if hasattr(config, "header_bg_color"):
			config.header_bg_color = secondary_color or primary_color or "#1a1a1a"
		if hasattr(config, "header_text_color"):
			config.header_text_color = "#ffffff"

		# CTA configuration
		config.cta_text = cta_text
		config.cta_url = cta_url
		# CTA button uses primary color
		if primary_color and hasattr(config, "cta_button_color"):
			config.cta_button_color = primary_color
		if hasattr(config, "cta_button_text_color"):
			config.cta_button_text_color = "#ffffff"

		# Social links
		if social_links:
			try:
				links = json.loads(social_links) if isinstance(social_links, str) else social_links
				config.show_social_links = True
				if links.get("facebook"):
					config.facebook_url = links["facebook"]
				if links.get("instagram"):
					config.instagram_url = links["instagram"]
				if links.get("twitter"):
					config.twitter_url = links["twitter"]
				if links.get("linkedin"):
					config.linkedin_url = links["linkedin"]
				if links.get("youtube"):
					config.youtube_url = links["youtube"]
			except (json.JSONDecodeError, TypeError):
				pass

		# Clear menu items (will be populated after page creation)
		config.menu_items = []
		config.save(ignore_permissions=True)
		frappe.db.commit()
		ai_log("info", "Header/footer config saved")

		# Seed Contact Us Settings when still empty so the shared contact_info
		# include renders real data instead of nothing (frappe core doctype,
		# same on both forks; never overwrites values the user has set)
		try:
			cus = frappe.get_doc("Contact Us Settings")
			current = (cus.get("address_title") or "").strip()
			# Same rule as the brand above. `_was_seeded_by_us` only recognises
			# names recorded on a chat session, so a generation launched
			# programmatically left the previous site's name in place.
			if not current or _was_seeded_by_us(current) or current != site_name:
				cus.address_title = site_name
				cus.flags.ignore_mandatory = True
				cus.save(ignore_permissions=True)
				frappe.db.commit()
		except Exception:
			pass

		# =====================================================================
		# STEP 2.5: Generate Design Brief for visual consistency
		# =====================================================================
		ai_log("info", "Step 2.5: Generating design brief for consistency")

		# ground the generation in the site's REAL business data —
		# the model must never invent an address/phone/email, and the logo
		# (when the caller didn't pass one) feeds the brief's vision analysis
		# (palette + typographic personality extracted from it).
		contact_data = get_site_contact_context(website_profile)  # multi-site
		contact_prompt = _contact_context_prompt(contact_data)
		if contact_prompt:
			prompt = f"{prompt}{contact_prompt}"
			ai_log("info", "Injected real business data into prompt",
				   fields=[k for k in contact_data if contact_data.get(k)])
		if not logo_image and contact_data.get("logo"):
			logo_image = contact_data["logo"]
			ai_log("info", "Using the site's existing logo for brief vision",
				   logo=logo_image)
		_update_generation_status(job_id, {
			"status": "running",
			"progress": 8,
			"total_pages": total_pages,
			"current_step": "Generating design brief...",
			"current_page": None,
			"pages_created": [],
			"error": None,
			"site_name": site_name,
		})

		from unpress_core.ai.generators.brief_generator import BriefGenerator, get_default_brief
		try:
			# Parse inspiration URLs to get image URLs
			inspiration_image_urls = []
			if inspiration_urls:
				try:
					insp_data = json.loads(inspiration_urls) if isinstance(inspiration_urls, str) else inspiration_urls
					if isinstance(insp_data, list):
						for item in insp_data:
							if isinstance(item, dict) and item.get("url"):
								inspiration_image_urls.append(item["url"])
							elif isinstance(item, str):
								inspiration_image_urls.append(item)
				except (json.JSONDecodeError, TypeError):
					pass

			# Make logo URL absolute for vision API
			# Fallback to config logo if not provided via session
			effective_logo = logo_image
			if not effective_logo and config:
				try:
					cfg_logo = config.logo_image if hasattr(config, 'logo_image') else None
					if cfg_logo:
						effective_logo = cfg_logo
						ai_log("info", "Using logo from config for vision", logo=cfg_logo)
				except Exception:
					pass
			logo_url = None
			if effective_logo:
				if effective_logo.startswith("/"):
					logo_url = frappe.utils.get_url() + effective_logo
				else:
					logo_url = effective_logo
				ai_log("info", "Logo image for vision analysis", logo_url=logo_url)

			brief_gen = BriefGenerator(provider=provider, model=model, config=ai_config)
			design_brief, brief_validation = brief_gen.generate_brief_with_validation(
				prompt=prompt,
				site_name=site_name,
				site_type=site_type,
				theme=theme,
				primary_color=primary_color,
				secondary_color=secondary_color,
				pages_config=pages_config,
				max_retries=2,
				heading_font=heading_font,
				body_font=body_font,
				logo_image=logo_url,
				inspiration_images=inspiration_image_urls if inspiration_image_urls else None,
			)

			# Log validation results
			if getattr(design_brief, "_is_fallback", False):
				# Loud on purpose. A fallback brief is valid, so it used to be
				# logged as a success — and every site came out with the same
				# chrome for as long as nobody compared the values with the
				# defaults. If this line appears, the model never answered.
				ai_log("error", "Design brief FELL BACK to defaults — the model did not answer",
					site_name=site_name)
				frappe.log_error(
					"Design brief fell back to defaults",
					f"Site: {site_name}\nThe chrome will be identical to every other "
					f"site generated this way. Check the provider and the schema.",
				)
			elif brief_validation.is_valid:
				ai_log("info", "Design brief generated and validated",
					site_tone=design_brief.site_tone, hero_style=design_brief.hero_style,
					warnings=len(brief_validation.warnings))
			else:
				ai_log("warning", "Design brief validated with defaults merged",
					site_tone=design_brief.site_tone,
					missing=brief_validation.missing_fields,
					invalid=list(brief_validation.invalid_fields.keys()))

			print(f"[SITE_GEN_WORKER] Design brief generated: tone={design_brief.site_tone}, valid={brief_validation.is_valid}")
		except Exception as e:
			ai_log("warning", "Design brief generation failed completely, using defaults", error=str(e)[:100])
			frappe.log_error("Generation: design brief failed", str(e))
			print(f"[SITE_GEN_WORKER] Design brief failed, using defaults: {str(e)[:100]}")
			design_brief = get_default_brief(
				theme=theme,
				primary_color=primary_color,
				secondary_color=secondary_color,
			)

		# The brief is the record of what the AI decided; keep it the moment it
		# exists rather than only on one of the exit paths.
		_save_brief_to_session(session_id, design_brief)

		# =====================================================================
		# STEP 2.6: Extract colors from design brief for page generation
		# =====================================================================
		# Use colors from brief if no explicit colors were provided
		# This ensures the random palette is actually used
		if not primary_color and hasattr(design_brief, 'primary_color') and design_brief.primary_color:
			primary_color = design_brief.primary_color
			ai_log("info", "Using primary color from design brief", color=primary_color)
		if not secondary_color and hasattr(design_brief, 'secondary_color') and design_brief.secondary_color:
			secondary_color = design_brief.secondary_color
			ai_log("info", "Using secondary color from design brief", color=secondary_color)

		print(f"[SITE_GEN_WORKER] Colors for pages: primary={primary_color}, secondary={secondary_color}")

		# =====================================================================
		# STEP 2.6.5: Apply the brief's site chrome (header/footer design)
		# =====================================================================
		try:
			applied = apply_brief_site_chrome(design_brief, website_profile=website_profile)  # multi-site
			ai_log("info", "Site chrome applied from design brief", fields=applied)
			print(f"[SITE_GEN_WORKER] Site chrome from design brief: {applied}")
		except Exception as e:
			ai_log("warning", "Failed to apply site chrome from design brief", error=str(e)[:100])
			frappe.log_error("Generation: site chrome failed", str(e))

		# =====================================================================
		# STEP 2.7: Propagate fonts from design brief to Website Header Footer Config
		# =====================================================================
		if hasattr(design_brief, 'heading_font') and design_brief.heading_font:
			try:
				config = _get_site_chrome_config(website_profile)  # multi-site
				# The Select refuses anything outside its options, and a refusal
				# here used to abort the whole step: the chrome then kept the
				# PREVIOUS site's fonts while the pages wore the new ones. The
				# brief is constrained to the same list now, so this should never
				# fire — but a rejected font must cost that font, not the step.
				allowed = set(
					(frappe.get_meta(config.doctype).get_field("heading_font").options or "").split("\n")
				)
				if not allowed or design_brief.heading_font in allowed:
					config.heading_font = design_brief.heading_font
				else:
					ai_log("warning", "Heading font not offered by the chrome — kept the current one",
						asked=design_brief.heading_font)
				body = design_brief.body_font or "Inter"
				if not allowed or body in allowed:
					config.body_font = body
				# Also propagate typography scale if available
				if hasattr(design_brief, 'typography') and design_brief.typography:
					typo = design_brief.typography
					for field in ['h1_size', 'h1_weight', 'h1_line_height', 'h1_size_mobile',
								  'h2_size', 'h2_weight', 'h2_line_height', 'h2_size_mobile',
								  'h3_size', 'h3_weight', 'h3_size_mobile',
								  'body_size', 'body_size_mobile', 'body_line_height']:
						val = getattr(typo, field, None)
						if val and hasattr(config, field):
							setattr(config, field, val)
				config.save(ignore_permissions=True)
				frappe.db.commit()
				ai_log("info", "Fonts propagated to Website Header Footer Config",
					   heading_font=design_brief.heading_font, body_font=design_brief.body_font)
				print(f"[SITE_GEN_WORKER] Fonts propagated: heading={design_brief.heading_font}, body={design_brief.body_font}")
			except Exception as e:
				ai_log("warning", "Failed to propagate fonts to config", error=str(e)[:100])
				frappe.log_error("Generation: font propagation failed", str(e))

		# =====================================================================
		# STEP 3: Generate pages SEQUENTIALLY (simpler, more reliable)
		# =====================================================================
		# In progressive mode, only generate the homepage (first page)
		pages_to_generate = pages_config
		if generation_mode == "progressive":
			pages_to_generate = pages_config[:1]
			ai_log("info", "Progressive mode: generating homepage only", total_pages=1)
		total_pages_to_gen = len(pages_to_generate)
		ai_log("info", "Step 3: Starting sequential page generation", total_pages=total_pages_to_gen)
		_update_generation_status(job_id, {
			"status": "running",
			"progress": 10,
			"total_pages": total_pages_to_gen,
			"current_step": f"Generating {total_pages_to_gen} page{'s' if total_pages_to_gen > 1 else ''}...",
			"current_page": None,
			"pages_created": [],
			"error": None,
			"site_name": site_name,
		})

		# Create one generator instance (reused for all pages)
		print(f"[SITE_GEN_WORKER] Creating PageGenerator...")
		gen = PageGenerator(provider=provider, model=model, config=ai_config)
		print(f"[SITE_GEN_WORKER] PageGenerator created successfully")

		# Retry configuration for page generation
		MAX_PAGE_RETRIES = 2

		generated_results = []
		for idx, page_def in enumerate(pages_to_generate):
			page_title = page_def["title"]
			ai_log("info", f"Generating page {idx + 1}/{total_pages_to_gen}", page=page_title)
			print(f"[SITE_GEN_WORKER] === Generating page {idx + 1}/{total_pages_to_gen}: {page_title} ===")

			# Update progress
			progress = 10 + int((idx / total_pages_to_gen) * 80)
			_update_generation_status(job_id, {
				"status": "running",
				"progress": progress,
				"total_pages": total_pages_to_gen,
				"current_step": f"Generating page {idx + 1}/{total_pages_to_gen}: {page_title}",
				"current_page": page_title,
				"pages_created": [],
				"error": None,
				"site_name": site_name,
			})

			# Pull the client's real ingested content for this page's section
			# (no-op when nothing was uploaded → behaves exactly as before).
			page_real_content = ""
			if session_id:
				try:
					from unpress_core.ai.ingestion.content_understanding import get_content_context
					page_real_content = get_content_context(
						session_id, page_def.get("type", "") or page_title)
				except Exception as e:
					ai_log("warning", "Content context fetch failed", error=str(e)[:150])

			# Retry loop for page generation
			blocks = None
			last_error = None
			for attempt in range(MAX_PAGE_RETRIES + 1):
				try:
					page_prompt = f"{prompt}. Page: {page_title}."

					# Add correction instruction on retry
					if attempt > 0:
						page_prompt += f"\n\nIMPORTANT: La génération précédente a échoué (erreur JSON). Assure-toi de retourner un JSON valide et complet."
						ai_log("warning", f"Retry attempt {attempt}/{MAX_PAGE_RETRIES}",
							page=page_title, previous_error=str(last_error)[:100])
						print(f"[SITE_GEN_WORKER] Retry {attempt}/{MAX_PAGE_RETRIES} for {page_title}...")

						# Update status to show retry
						_update_generation_status(job_id, {
							"status": "running",
							"progress": progress,
							"total_pages": total_pages,
							"current_step": f"Retry {attempt}/{MAX_PAGE_RETRIES}: {page_title}",
							"current_page": page_title,
							"pages_created": [],
							"error": None,
							"site_name": site_name,
						})
					else:
						ai_log("info", "Calling PageGenerator.generate_page()",
							page=page_title, provider=provider, model=model)
						print(f"[SITE_GEN_WORKER] Calling gen.generate_page for {page_title}...")

					blocks = gen.generate_page(
						prompt=page_prompt,
						theme=theme,
						primary_color=primary_color,
						secondary_color=secondary_color,
						page_title=page_title,
						page_type=page_def.get("type", ""),
						design_brief=design_brief,
						real_content=page_real_content,
					)

					ai_log("info", "Page generation successful",
						page=page_title, blocks_count=len(blocks) if blocks else 0,
						attempt=attempt + 1)
					print(f"[SITE_GEN_WORKER] Page {page_title} generated: {len(blocks)} blocks")
					break  # Success - exit retry loop

				except ValueError as e:
					# JSON parsing errors - retryable
					last_error = e
					if "JSON" in str(e) and attempt < MAX_PAGE_RETRIES:
						ai_log("warning", f"JSON error, will retry", page=page_title,
							attempt=attempt + 1, error=str(e)[:100])
						print(f"[SITE_GEN_WORKER] JSON error for {page_title}, will retry: {str(e)[:100]}")
						continue
					break  # this page failed — keep generating the others

				except Exception as e:
					last_error = e
					# transient API failures (Moonshot timeout on a
					# dense page, connection blips, rate limits) ARE retryable —
					# raising here used to kill the WHOLE job after 30 minutes.
					message = str(e).lower()
					transient = any(token in message for token in (
						"timed out", "timeout", "connection", "rate limit",
						"429", "502", "503", "504",
					))
					if transient and attempt < MAX_PAGE_RETRIES:
						ai_log("warning", "Transient API error, will retry",
							page=page_title, attempt=attempt + 1, error=str(e)[:120])
						print(f"[SITE_GEN_WORKER] Transient error for {page_title}, retrying: {str(e)[:120]}")
						continue
					break  # this page failed — keep generating the others

			# After retry loop
			if blocks:
				generated_results.append({"page_def": page_def, "blocks": blocks, "error": None})
			else:
				import traceback
				error_msg = str(last_error)[:200] if last_error else "Unknown error"
				full_traceback = traceback.format_exc() if last_error else ""
				ai_log("error", "Page generation failed after retries",
					page=page_title, error=error_msg, attempts=MAX_PAGE_RETRIES + 1,
					traceback=full_traceback[:500])
				print(f"[SITE_GEN_WORKER] Page {page_title} FAILED after {MAX_PAGE_RETRIES + 1} attempts: {error_msg}")
				print(f"[SITE_GEN_WORKER] Full traceback:\n{full_traceback}")
				frappe.log_error(f"Page generation failed: {page_title}",
					f"After {MAX_PAGE_RETRIES + 1} attempts\n{str(last_error)}\n\n{full_traceback}")
				generated_results.append({"page_def": page_def, "blocks": None, "error": error_msg})

		# Now create all pages in DB (sequential, but fast)
		ai_log("info", "All page generations completed",
			successful=sum(1 for r in generated_results if not r["error"]),
			failed=sum(1 for r in generated_results if r["error"]))
		ai_log("info", "Step 4: Creating pages in database")
		created_pages = []
		for result in generated_results:
			if result["error"] or not result["blocks"]:
				page_title = result["page_def"].get("title", "unknown")
				skip_reason = result["error"] if result["error"] else "blocks is None or empty"
				ai_log("warning", f"Skipping page creation: {page_title}", reason=skip_reason)
				print(f"[SITE_GEN_WORKER] SKIPPING page {page_title}: {skip_reason}")
				frappe.log_error(f"Page skipped: {page_title}", f"Reason: {skip_reason}\nBlocks: {result.get('blocks')}")
				continue

			page_def = result["page_def"]
			blocks = result["blocks"]

			try:
				# Wrap blocks in a root container (required by Frappe Builder)
				# The Builder expects: [{ blockId, element: "body", children: [...sections...] }]
				root_block = {
					"blockId": f"root-{frappe.generate_hash(length=8)}",
					"element": "body",
					# The editor recognises its root by `originalElement`; without
					# it the body is treated as an ordinary block — resizable,
					# deletable, and free to take a fixed width.
					"originalElement": "body",
					"baseStyles": {},
					"children": blocks
				}
				wrapped_blocks = [root_block]

				# Create the Builder Page
				# The opening line moves up into the shared band — but only on an
				# interior page. The homepage keeps the hero the AI composed for
				# it, and lifting its headline out would leave a hero with no
				# words on it.
				# One horizontal rhythm for the whole site — the model invents an
				# inset per page unless something enforces it.
				_normalise_section_rhythm(wrapped_blocks)
				_retune_container_widths(wrapped_blocks)

				opening = ""
				if str(page_def.get("route", "")).strip("/") not in ("", "home", "index"):
					opening = _lift_opening_into_header(blocks)
					wrapped_blocks[0]["children"] = blocks

				page = frappe.new_doc("Builder Page")
				page.page_title = page_def["title"]
				page.meta_description = opening or _describe_page(blocks)
				page.blocks = json.dumps(wrapped_blocks)
				page.draft_blocks = json.dumps(wrapped_blocks)
				page.published = 1
				# multi-site: tag the page for its target site
				if website_profile and frappe.db.has_column("Builder Page", "neo_website_profile"):
					page.neo_website_profile = website_profile
				page.insert(ignore_permissions=True)

				# Force route (no /pages/ prefix)
				route = page_def["route"]
				# additive mode — resolve a route collision by replacing
				# the occupant only when it is an untouched AI page, otherwise
				# keep the user's page and shift the new route.
				if replace_existing == "none":
					occupant_filters = {"route": route, "is_template": 0, "name": ("!=", page.name)}
					# multi-site: route collisions are per site — only
					#//// consider the target profile's pages (or untagged ones).
					if frappe.db.has_column("Builder Page", "neo_website_profile"):
						occupant_filters["neo_website_profile"] = website_profile if website_profile else ("is", "not set")
					occupant = frappe.db.get_value(
						"Builder Page",
						occupant_filters,
						["name", "ai_generated_at", "ai_blocks_hash", "blocks", "draft_blocks"],
						as_dict=True,
					)
					if occupant:
						occupant_hash = _blocks_fingerprint(occupant.draft_blocks or occupant.blocks)
						if occupant.ai_generated_at and occupant_hash == occupant.ai_blocks_hash:
							frappe.delete_doc("Builder Page", occupant.name,
											  ignore_permissions=True, force=True)
						else:
							route = f"{route}-{frappe.generate_hash(length=4)}"
							ai_log("warning", "Route occupied by a protected page — shifted",
								   new_route=route)
				# stamp the generation so future runs can tell
				# untouched AI pages from user-designed ones
				frappe.db.set_value("Builder Page", page.name, {
					"route": route,
					"ai_generated_at": frappe.utils.now(),
					"ai_blocks_hash": _blocks_fingerprint(page.blocks),
				}, update_modified=False)
				frappe.db.commit()

				ai_log("info", "Page created successfully",
					page=page_def["title"], route=route, page_id=page.name)

				created_pages.append({
					"name": page.name,
					"title": page_def["title"],
					"route": f"/{route}",
				})

			except Exception as e:
				error_msg = str(e)[:200]
				ai_log("error", "Failed to create page in database",
					page=page_def["title"], error=error_msg)
				frappe.log_error(f"Page creation failed: {page_def['title']}", str(e))
				# Continue with next page instead of crashing
				continue

		# =====================================================================
		# STEP 4.5: Brief compliance check ("Last Call")
		# =====================================================================
		if design_brief and created_pages:
			ai_log("info", "Step 4.5: Brief compliance check", pages=len(created_pages))
			_update_generation_status(job_id, {
				"status": "running",
				"progress": 92,
				"total_pages": total_pages,
				"current_step": "Final quality check...",
				"current_page": None,
				"pages_created": created_pages,
				"error": None,
				"site_name": site_name,
			})

			from unpress_core.ai.generators.page_generator import BriefComplianceChecker
			checker = BriefComplianceChecker(design_brief, primary_color, secondary_color)
			total_fixes = 0
			for page_info in created_pages:
				try:
					page_doc = frappe.get_doc("Builder Page", page_info["name"])
					blocks = json.loads(page_doc.blocks or "[]")
					fixed_blocks, fixes = checker.check_and_fix(blocks, page_info["title"])
					if fixes:
						total_fixes += len(fixes)
						new_json = json.dumps(fixed_blocks, ensure_ascii=False)
						# re-stamp the AI hash — these are still
						# generator-made blocks, not user edits
						frappe.db.set_value("Builder Page", page_info["name"],
							{"blocks": new_json, "draft_blocks": new_json,
							 "ai_blocks_hash": _blocks_fingerprint(new_json)},
							update_modified=False)
				except Exception as e:
					ai_log("warning", "Brief compliance check failed for page",
						page=page_info["title"], error=str(e)[:200])

			if total_fixes:
				frappe.db.commit()
				ai_log("info", "Brief compliance check completed",
					total_fixes=total_fixes, pages_checked=len(created_pages))

		# =====================================================================
		# STEP 4.6: Progressive mode early return (homepage ready)
		# =====================================================================
		if generation_mode == "progressive" and created_pages:
			ai_log("info", "Progressive mode: homepage ready, pausing generation",
				homepage=created_pages[0]["title"])

			_save_brief_to_session(
				session_id, design_brief, generation_mode="progressive", homepage_iterations=0
			)

			end_time = time.time()
			duration_seconds = int(end_time - start_time)
			duration_str = f"{duration_seconds // 60}m {duration_seconds % 60}s"

			_update_generation_status(job_id, {
				"status": "homepage_ready",
				"progress": 100,
				"total_pages": total_pages,
				"current_step": "Homepage ready — awaiting feedback",
				"current_page": None,
				"pages_created": created_pages,
				"error": None,
				"site_name": site_name,
				"completed_at": frappe.utils.now(),
				"duration_seconds": duration_seconds,
				"duration": duration_str,
				"generation_mode": "progressive",
				"remaining_pages": len(pages_config) - 1,
			})

			# Update session status
			_update_session_on_completion(session_id, job_id, "Homepage Ready", created_pages)
			return  # Early return — remaining pages generated later via continue_generation()

		# =====================================================================
		# STEP 5: Update menu from created pages
		# =====================================================================
		ai_log("info", "Step 5: Updating menu", pages_created=len(created_pages))

		# Check that at least one page was created
		if not created_pages:
			ai_log("error", "No pages could be generated", total_pages=total_pages)
			raise ValueError(f"No pages could be generated. All {total_pages} page generations failed.")

		_update_generation_status(job_id, {
			"status": "running",
			"progress": 95,
			"total_pages": total_pages,
			"current_step": "Updating menu",
			"current_page": None,
			"pages_created": created_pages,
			"error": None,
			"site_name": site_name,
		})

		config = _get_site_chrome_config(website_profile)  # multi-site

		# ---- Update Menu ----
		config.menu_items = []

		# Special handling for one_page sites: use anchor links
		if site_type == "one_page":
			# Define anchor sections for one-page navigation
			one_page_anchors = [
				{"label": "Accueil", "url": "/#hero"},
				{"label": "Services", "url": "/#services"},
				{"label": "À propos", "url": "/#about"},
				{"label": "Contact", "url": "/#contact"},
			]
			for anchor in one_page_anchors:
				config.append("menu_items", {
					"label": anchor["label"],
					"url": anchor["url"],
					"is_external": False,
					"open_in_new_tab": False,
				})
		else:
			# Multi-page sites: use page routes
			# Track routes to prevent duplicates
			seen_routes = set()
			shop_link_added = False
			for page in created_pages:
				route = page["route"]
				# Skip if route already added (prevents "/" duplication)
				if route in seen_routes:
					continue
				seen_routes.add(route)

				# Use "Accueil" for home page, otherwise use page title
				label = "Accueil" if route in ("/", "/home", "/index") else page["title"]

				# Menu URL: use "/" for homepage instead of "/home"
				menu_url = "/" if route in ("/", "/home", "/index") else route

				config.append("menu_items", {
					"label": label,
					"url": menu_url,
					"is_external": False,
					"open_in_new_tab": False,
				})

				# For ecommerce sites: add Shop link after Accueil
				if site_type in ("ecommerce", "ecommerce_search") and route in ("/", "/home", "/index") and not shop_link_added:
					config.append("menu_items", {
						"label": "Shop",
						"url": "/all-products",
						"is_external": False,
						"open_in_new_tab": False,
					})
					shop_link_added = True

		# ---- Update Footer ----
		# Footer logo: same as header
		if hasattr(config, "footer_logo_type"):
			config.footer_logo_type = config.logo_type
		if hasattr(config, "footer_logo_text"):
			config.footer_logo_text = config.logo_text
		if hasattr(config, "footer_logo_image"):
			config.footer_logo_image = config.logo_image
		if hasattr(config, "show_footer_logo"):
			config.show_footer_logo = True

		# Footer description: extract from prompt
		if hasattr(config, "footer_description"):
			short_desc = _shorten_for_footer(prompt)
			# Clean up if it contains site name prefix
			if " - " in short_desc:
				short_desc = short_desc.split(" - ", 1)[1]
			config.footer_description = short_desc

		# Footer links: the pages we just created, under a named heading.
		# The heading matters: an unnamed column renders as "Links", and the
		# Extended template puts headings above each column. Owners add their
		# own columns (Legal, Support) from the Theme; we do not invent pages
		# that do not exist to fill a second column.
		if hasattr(config, "footer_menu_source"):
			config.footer_menu_source = "Custom links"
		if hasattr(config, "footer_links"):
			config.footer_links = []
			navigation = _("Navigation")
			if site_type == "one_page":
				# Use same anchor links for footer
				for anchor in one_page_anchors:
					config.append("footer_links", {
						"column_name": navigation,
						"label": anchor["label"],
						"url": anchor["url"],
					})
			else:
				for page in created_pages:
					route = page["route"]
					if route in seen_routes:
						label = _("Home") if route in ("/", "/home", "/index") else page["title"]
						footer_url = "/" if route in ("/", "/home", "/index") else route
						config.append("footer_links", {
							"column_name": navigation,
							"label": label,
							"url": footer_url,
						})

		config.save(ignore_permissions=True)

		# multi-site: a profile-targeted generation sets the PROFILE's
		#//// home page (Link to the Builder Page docname) and must never touch the
		#//// default site's Website Settings / Builder Settings pointers.
		if website_profile and frappe.db.exists("DocType", "Website Profile"):
			home_page_name = None
			for created_page in created_pages:
				if created_page["route"] in ("/", "/home", "/index"):
					home_page_name = created_page["name"]
					break
			if home_page_name:
				frappe.db.set_value("Website Profile", website_profile, "home_page", home_page_name)
			frappe.db.commit()
			frappe.cache.delete_value("nt_website_profiles_by_host")
			frappe.cache.delete_value("website_page")
		else:
			# Point BOTH settings to the generated home page. Website Settings
			# is Frappe's standard pointer; Builder Settings is what
			# BuilderPage.is_home_page() checks for rendering — if only Website
			# Settings is set, BuilderPageRenderer still resolves the Builder
			# Page at /home but "/" shows Frappe's fallback. Keep them in sync.
			frappe.db.set_value("Website Settings", "Website Settings", "home_page", "home")
			frappe.db.set_value("Builder Settings", "Builder Settings", "home_page", "home")
			frappe.db.commit()
		frappe.clear_cache()

		# =====================================================================
		# STEP 5.5: Place the client's own photos into the fresh pages
		# =====================================================================
		# If the client uploaded real photos for this session, drop them into
		# the matching image slots now so the generated site shows real content
		# immediately (Flux stays an opt-in fallback for the leftover slots).
		# Guarded — never let image matching fail the whole generation.
		if session_id:
			try:
				from unpress_core.ai.ingestion.image_matcher import match_and_apply
				page_names = [p["name"] for p in created_pages]
				match_result = match_and_apply(session_id, page_names)
				if match_result.get("matched"):
					ai_log("info", "Placed client photos into generated pages",
						matched=match_result["matched"], slots=match_result.get("slots"))
			except Exception as e:
				ai_log("warning", "Client photo matching skipped", error=str(e)[:200])

		# Count image slots still on placeholders (no client photo matched them).
		# This drives the chat's consent question: only offer AI image generation
		# when something is actually missing — never when real photos cover it.
		remaining_image_slots = 0
		image_job_id = None
		try:
			pending_images = _scan_placeholder_images(
				[p["name"] for p in created_pages],
				subject=_image_subject(session_id, site_name, prompt),
			)
			remaining_image_slots = len(pending_images)
			# Generate them right away when a backend is configured. This used
			# to wait for a button in the desk chat, so self-serve sites simply
			# never got real images.
			if pending_images and _image_backend_available():
				image_job_id = _enqueue_image_generation(pending_images, session_id=session_id)
		except Exception as e:
			ai_log("warning", "Image generation not started", error=str(e)[:200])

		# =====================================================================
		# STEP 6: Mark as completed
		# =====================================================================
		end_time = time.time()
		duration_seconds = int(end_time - start_time)
		duration_str = f"{duration_seconds // 60}m {duration_seconds % 60}s"

		ai_log("info", "=== SITE GENERATION COMPLETED ===",
			job_id=job_id, pages_created=len(created_pages),
			pages_failed=total_pages - len(created_pages), duration=duration_str)
		print(f"[SITE_GEN_WORKER] ===== WORKER COMPLETED =====")
		print(f"[SITE_GEN_WORKER] job_id={job_id}, pages_created={len(created_pages)}/{total_pages}, duration={duration_str}")

		_update_generation_status(job_id, {
			"status": "completed",
			"progress": 100,
			"total_pages": total_pages,
			"current_step": "Completed",
			"current_page": None,
			"pages_created": created_pages,
			"remaining_image_slots": remaining_image_slots,
			"image_job_id": image_job_id,
			"error": None,
			"site_name": site_name,
			"completed_at": frappe.utils.now(),
			"duration_seconds": duration_seconds,
			"duration": duration_str,
			"result": {
				"success": True,
				"pages": created_pages,
				"pages_generated": len(created_pages),
				"pages_failed": total_pages - len(created_pages),
				"duration": duration_str,
				"duration_seconds": duration_seconds,
				"config": {
					"site_type": site_type,
					"theme": theme,
					"logo_type": config.logo_type,
					"logo_value": config.logo_image if config.logo_type == "Image" else config.logo_text,
					"menu_items_count": len(config.menu_items),
				},
				"message": f"Site generated in {duration_str} with {len(created_pages)}/{total_pages} pages"
			}
		})

		# Update the chat session document in DB (persists beyond cache)
		_update_session_on_completion(session_id, job_id, "Completed", created_pages)

	except Exception as e:
		# Log error and update status
		ai_log("error", "=== SITE GENERATION FAILED ===",
			job_id=job_id, error=str(e))
		print(f"[SITE_GEN_WORKER] ===== WORKER FAILED =====")
		print(f"[SITE_GEN_WORKER] job_id={job_id}, error={str(e)[:200]}")
		frappe.log_error("Site generation failed", str(e))
		try:
			frappe.cache.set_value(f"site_generation_{job_id}", {"status": "failed", "error": str(e)[:500], "progress": 0}, expires_in_sec=14400)
		except Exception:
			pass
		_update_generation_status(job_id, {
			"status": "failed",
			"progress": 0,
			"total_pages": total_pages,
			"current_step": "Failed",
			"current_page": None,
			"pages_created": [],
			"error": str(e),
			"site_name": site_name,
			"failed_at": frappe.utils.now(),
		})
		# Update the chat session document in DB
		_update_session_on_completion(session_id, job_id, "Failed", [])
		raise


@frappe.whitelist()
def continue_generation(
	session_id: str,
	provider: str = None,
	model: str = None,
):
	"""
	Continue site generation after progressive homepage review.
	Generates remaining pages using the saved brief from the session.
	"""
	session_name = frappe.db.get_value(
		"Builder Chat Session", {"session_id": session_id}, "name"
	)
	if not session_name:
		frappe.throw(_("Session not found"))

	session = frappe.get_doc("Builder Chat Session", session_name)

	# Restore brief
	if not session.saved_brief:
		frappe.throw(_("No saved brief found in session"))

	# Get pages_config and skip the homepage (already generated)
	pages_config = json.loads(session.pages_config or "[]")
	if not pages_config:
		pages_config = pages_for_site_type(session.site_type)
	remaining_pages = pages_config[1:]  # Skip homepage

	if not remaining_pages:
		return {"status": "completed", "message": "No remaining pages to generate"}

	job_id = f"site_gen_{frappe.generate_hash(length=10)}"

	_update_generation_status(job_id, {
		"status": "queued",
		"progress": 0,
		"total_pages": len(remaining_pages),
		"current_page": None,
		"pages_created": [],
		"error": None,
		"site_name": session.site_name,
		"created_at": frappe.utils.now(),
		"generation_mode": "continue",
	})

	frappe.enqueue(
		"unpress_core.generation._generate_complete_site_worker",
		queue="default",
		timeout=3600,  # 1 hour max
		job_name=job_id,
		generation_job_id=job_id,
		prompt=session.site_description or "",
		site_name=session.site_name or "",
		site_type=session.site_type or "vitrine",
		theme=session.theme or "modern",
		primary_color=session.primary_color,
		secondary_color=session.secondary_color,
		logo_text=session.logo_text,
		logo_image=session.logo_image,
		cta_text=session.cta_text or "Contact",
		cta_url=session.cta_url or "/contact",
		social_links=session.social_links,
		provider=provider,
		model=model,
		session_id=session_id,
		heading_font=session.heading_font,
		body_font=session.body_font,
		pages_config=json.dumps(remaining_pages),
		generation_mode="full",  # Generate all remaining pages normally
		# multi-site: keep the continuation targeted at the same site
		website_profile=getattr(session, "website_profile", None),
	)

	# Update session
	session.job_id = job_id
	session.generation_status = "generating"
	session.save(ignore_permissions=True)
	frappe.db.commit()

	return {"job_id": job_id, "status": "queued", "remaining_pages": len(remaining_pages)}


@frappe.whitelist()
def regenerate_homepage(
	session_id: str,
	feedback: str = "",
	provider: str = None,
	model: str = None,
):
	"""
	Regenerate the homepage with user feedback integrated into the brief.
	"""
	session_name = frappe.db.get_value(
		"Builder Chat Session", {"session_id": session_id}, "name"
	)
	if not session_name:
		frappe.throw(_("Session not found"))

	session = frappe.get_doc("Builder Chat Session", session_name)

	# Check iteration limit
	iterations = (session.homepage_iterations or 0) + 1
	if iterations > 2:
		frappe.throw(_("Maximum homepage iterations reached (2). Proceeding with current version."))

	# Store feedback
	session.homepage_feedback = feedback
	session.homepage_iterations = iterations

	# Get homepage page_def
	pages_config = json.loads(session.pages_config or "[]")
	if not pages_config:
		pages_config = pages_for_site_type(session.site_type)
	homepage_config = pages_config[:1]  # Just the homepage

	# Delete existing homepage
	existing_pages = json.loads(session.generated_pages or "[]")
	for page_info in existing_pages:
		route = page_info.get("route", "")
		if route in ("/home", "/index", "/"):
			try:
				frappe.delete_doc("Builder Page", page_info["name"], force=True)
				frappe.db.commit()
			except Exception as e:
				frappe.log_error("Generation: brief restore failed", str(e))

	# Enrich prompt with feedback
	enriched_prompt = session.site_description or ""
	if feedback:
		enriched_prompt += f"\n\nREVISION INSTRUCTIONS (from user feedback, iteration {iterations}):\n{feedback}"

	job_id = f"site_gen_{frappe.generate_hash(length=10)}"

	_update_generation_status(job_id, {
		"status": "queued",
		"progress": 0,
		"total_pages": 1,
		"current_page": None,
		"pages_created": [],
		"error": None,
		"site_name": session.site_name,
		"created_at": frappe.utils.now(),
		"generation_mode": "regenerate_homepage",
	})

	frappe.enqueue(
		"unpress_core.generation._generate_complete_site_worker",
		queue="default",
		timeout=3600,
		job_name=job_id,
		generation_job_id=job_id,
		prompt=enriched_prompt,
		site_name=session.site_name or "",
		site_type=session.site_type or "vitrine",
		theme=session.theme or "modern",
		primary_color=session.primary_color,
		secondary_color=session.secondary_color,
		logo_text=session.logo_text,
		logo_image=session.logo_image,
		cta_text=session.cta_text or "Contact",
		cta_url=session.cta_url or "/contact",
		social_links=session.social_links,
		provider=provider,
		model=model,
		session_id=session_id,
		heading_font=session.heading_font,
		body_font=session.body_font,
		pages_config=json.dumps(homepage_config),
		generation_mode="progressive",  # Still progressive, will return homepage_ready
		# multi-site: keep the regeneration targeted at the same site
		website_profile=getattr(session, "website_profile", None),
	)

	# Update session
	session.job_id = job_id
	session.generation_status = "regenerating"
	session.save(ignore_permissions=True)
	frappe.db.commit()

	return {"job_id": job_id, "status": "queued", "iteration": iterations}


@frappe.whitelist()
def get_site_generation_status(job_id: str):
	"""
	Get the status of a site generation job.

	Args:
		job_id: The job ID returned by generate_complete_site()

	Returns:
		dict: Job status with progress, current step, pages created, etc.
	"""
	return _get_generation_status(job_id)


@frappe.whitelist()
def get_page_preview_html(page: str, **kwarg) -> Response:
	if not frappe.has_permission("Builder Page", "read", page):
		frappe.throw("No permission to preview this page")

	# to load preview without publishing
	frappe.form_dict.update(kwarg)
	frappe.local.request.for_preview = True
	renderer = BuilderPageRenderer(path="")
	renderer.docname = page
	renderer.doctype = "Builder Page"
	frappe.local.no_cache = 1
	renderer.init_context()
	response = renderer.render()
	page_doc = frappe.get_cached_doc("Builder Page", page)
	frappe.enqueue_doc(
		page_doc.doctype,
		page_doc.name,
		"generate_page_preview_image",
		html=str(response.data, "utf-8"),
		queue="short",
	)
	return response


@frappe.whitelist()
@has_page_write("You do not have permission to upload assets.")
def upload_builder_asset():
	from frappe.handler import upload_file

	image_file = upload_file()
	if (
		image_file
		and image_file.file_url.endswith((".png", ".jpeg", ".jpg"))
		and frappe.get_cached_value("Builder Settings", "Builder Settings", "auto_convert_images_to_webp")
	):
		convert_to_webp(file_doc=image_file)
	return image_file


@frappe.whitelist()
def convert_to_webp(image_url: str | None = None, file_doc: Document | None = None) -> str:
	"""
	Convert image to webp format.
	Handles local files, builder assets, and external URLs.
	Returns the new webp file URL or the original if conversion is not possible.
	"""
	import hashlib

	CONVERTIBLE_IMAGE_EXTENSIONS = ["png", "jpeg", "jpg"]

	def can_convert_image(extn: str) -> bool:
		return extn.lower() in CONVERTIBLE_IMAGE_EXTENSIONS

	def get_extension(filename: str) -> str:
		return filename.split(".")[-1].lower() if "." in filename else ""

	def save_as_webp(image, path: str) -> None:
		image.save(path, "WEBP")

	def to_webp_url(url: str, extn: str) -> str:
		return url.replace(extn, "webp")

	def to_webp_path(path: str, extn: str) -> str:
		return path.replace(extn, "webp")

	def handle_file_doc(file_doc: Document) -> str:
		if not file_doc.file_url.startswith("/files"):
			return file_doc.file_url
		image, _, extn = get_local_image(file_doc.file_url)
		if not can_convert_image(extn):
			return file_doc.file_url
		save_as_webp(image, to_webp_path(file_doc.get_full_path(), extn))
		delete_file(file_doc.get_full_path())
		file_doc.file_url = to_webp_url(file_doc.file_url, extn)
		file_doc.save()
		return file_doc.file_url

	def handle_local_url(image_url: str) -> str:
		image, _, extn = get_local_image(image_url)
		if not can_convert_image(extn):
			return image_url
		files = frappe.get_all("File", filters={"file_url": image_url}, fields=["name"], limit=1)
		if not files:
			return image_url
		file = frappe.get_doc("File", files[0].name)
		save_as_webp(image, to_webp_path(file.get_full_path(), extn))
		new_file = frappe.copy_doc(file)
		new_file.file_name = to_webp_url(file.file_name, extn)
		new_file.file_url = to_webp_url(file.file_url, extn)
		new_file.save()
		return new_file.file_url

	def handle_builder_asset(image_url: str) -> str:
		image_path = os.path.abspath(frappe.get_app_path("builder", "www", image_url.lstrip("/")))
		image_path = image_path.replace("_", "-").replace("/builder-assets", "/builder_assets")
		extn = get_extension(image_path)
		if not can_convert_image(extn):
			return image_url
		image = Image.open(image_path)
		save_as_webp(image, to_webp_path(image_path, extn))
		return to_webp_url(image_url, extn)

	def get_external_webp_filename(image_url: str) -> str:
		filename = image_url.split("/")[-1].split("?")[0]
		base = filename.rsplit(".", 1)[0] if "." in filename else ""
		if not base or base.lower() == "webp" or filename.lower() == "webp":
			return f"external-{hashlib.md5(image_url.encode()).hexdigest()[:8]}.webp"
		return base + ".webp"

	def handle_external_url(image_url: str) -> str:
		url = unquote(image_url)
		assert_not_private_url(url)
		image = Image.open(BytesIO(requests.get(url).content))
		filename = get_external_webp_filename(url)
		file = frappe.get_doc({"doctype": "File", "file_name": filename, "file_url": f"/files/{filename}"})
		save_as_webp(image, file.get_full_path())
		file.save()
		return file.file_url

	if not image_url and not file_doc:
		return ""
	if file_doc:
		return handle_file_doc(file_doc)

	image_url = image_url or ""
	if image_url.startswith("/files"):
		return handle_local_url(image_url)
	if image_url.startswith("/builder_assets"):
		return handle_builder_asset(image_url)
	if image_url.startswith("http"):
		return handle_external_url(image_url)
	return image_url


def assert_not_private_url(url: str) -> None:
	"""Raise PermissionError if the URL resolves to a private/internal IP (SSRF guard)."""
	parsed = urlparse(url)
	if parsed.scheme not in ("http", "https"):
		frappe.throw("Only HTTP/HTTPS URLs are allowed for external images.", frappe.PermissionError)
	hostname = parsed.hostname
	if not hostname:
		frappe.throw("Invalid URL: missing hostname.", frappe.ValidationError)
	try:
		addr_infos = socket.getaddrinfo(hostname, None)
	except socket.gaierror:
		frappe.throw(f"Could not resolve hostname: {hostname}", frappe.ValidationError)
	for addr_info in addr_infos:
		ip = ipaddress.ip_address(addr_info[4][0])
		if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
			frappe.throw("Requests to private or internal addresses are not allowed.", frappe.PermissionError)


def check_app_permission():
	if frappe.session.user == "Administrator":
		return True

	if frappe.has_permission("Builder Page", ptype="write"):
		return True

	return False


@frappe.whitelist()
@redis_cache()
def get_apps():
	# The desk is an implementation detail in Unpress (before_request bounces
	# /app back to /builder) — never advertise it in the app switcher.
	apps = get_permitted_apps()
	return list(filter(lambda app: app.get("name") != "builder", apps))


@frappe.whitelist()
@has_page_write("You do not have permission to update page folder.")
def update_page_folder(pages: list[str], folder_name: str) -> None:
	if not pages:
		return
	frappe.db.set_value(
		"Builder Page", {"name": ["in", pages]}, "project_folder", folder_name, update_modified=False
	)


def clone_client_scripts(source_page, new_page) -> None:
	"""Clone the source page's client scripts onto new_page with hashed names,
	so the copy never shares scripts with the source."""
	client_scripts = source_page.client_scripts
	new_page.client_scripts = []
	for script in client_scripts:
		builder_script = frappe.get_doc("Builder Client Script", script.builder_script)
		new_script = frappe.copy_doc(builder_script)
		new_script.name = f"{builder_script.name}-{frappe.generate_hash(length=5)}"
		new_script.insert(ignore_permissions=True)
		new_page.append("client_scripts", {"builder_script": new_script.name})


@frappe.whitelist()
@has_page_write("You do not have permission to duplicate a page.")
def duplicate_page(page_name: str):
	page = frappe.get_doc("Builder Page", page_name)
	new_page = frappe.copy_doc(page)
	del new_page.page_name
	new_page.route = None
	clone_client_scripts(page, new_page)
	new_page.insert()
	return new_page


# Templates live on a central Builder Hub site. Builder just fetches the catalog
# and, on use, a per-page bundle over HTTP (server-side — no CORS), then builds a
# page from it. Point at the hub via `template_hub_url` in the site config (or
# common_site_config for the whole bench).
DEFAULT_HUB_URL = "https://preview.frappe.cloud"


def hub_url() -> str:
	return (frappe.conf.get("template_hub_url") or DEFAULT_HUB_URL).rstrip("/")


@redis_cache(ttl=600)
def hub_get_cached(method: str, params_key: tuple):
	# make_get_request (not builder's make_safe_get_request, which blocks private
	# IPs and would reject a localhost hub). Trust = admin-set hub URL.
	from frappe.integrations.utils import make_get_request

	resp = make_get_request(
		f"{hub_url()}/api/method/builder_hub.api.{method}", params=dict(params_key) or None
	)
	return resp.get("message") if resp else None


def hub_get(method: str, **params):
	return hub_get_cached(method, tuple(sorted(params.items())))


@frappe.whitelist()
@has_page_read("You do not have permission to view templates.")
def get_template_groups() -> list[dict]:
	"""Template groups for the picker, fetched live from the hub. Empty (just
	Blank page) if the hub is unreachable."""
	try:
		return hub_get("get_catalog") or []  # type: ignore[return-value]
	except Exception:
		frappe.log_error("Failed to fetch templates from hub")
		return []


def _strip_template_navigation(blocks: list, components: list) -> list:
	"""Drop a template's own top-level navigation/footer blocks.

	Unpress renders the site-wide header/footer (Website Header Footer Config)
	around every page; importing a hub template verbatim would stack the
	template's navbar/footer on top of it. Removes root-level
	<nav>/<footer> elements and root-level blocks extending a bundle component
	whose name says it is a navbar/header/footer."""
	nav_component_ids = set()
	for comp in components:
		label = f"{comp.get('component_name') or ''} {comp.get('name') or ''}".lower()
		if any(token in label for token in ("navbar", "nav bar", "header", "footer")):
			if comp.get("component_id"):
				nav_component_ids.add(comp["component_id"])
			if comp.get("name"):
				nav_component_ids.add(comp["name"])

	def is_navigation(block: dict) -> bool:
		if not isinstance(block, dict):
			return False
		if block.get("element") in ("nav", "footer"):
			return True
		return block.get("extendedFromComponent") in nav_component_ids

	def strip(level_blocks: list) -> list:
		kept = [b for b in level_blocks if not is_navigation(b)]
		# Single root container (body/wrapper): strip one level deeper too
		if len(kept) == 1 and isinstance(kept[0], dict) and kept[0].get("children"):
			kept[0]["children"] = [c for c in kept[0]["children"] if not is_navigation(c)]
		return kept

	return strip(blocks if isinstance(blocks, list) else [blocks])


def create_page_from_bundle(bundle: dict, project_folder: str | None = None) -> str:
	"""Create an editable page from a fetched hub bundle and return its name.

	Installs shared components/variables/scripts/fonts, then builds the page
	from its blocks. Created pages hot-link the hub's /builder_assets/ images."""
	from frappe.modules.import_file import import_doc

	for font in bundle.get("fonts") or []:
		import_doc(docdict=font)
	for var in bundle.get("variables") or []:
		import_doc(docdict=var)
	for comp in bundle.get("components") or []:
		import_doc(docdict=comp)

	page = bundle.get("page")
	assert isinstance(page, dict)
	preview = page.get("preview")
	# hub templates ship their own navbar/footer components, but navigation is
	# provided site-wide by Website Header Footer Config — keeping both stacks
	# two headers/footers on every page.
	page_blocks = _strip_template_navigation(
		page.get("blocks") or [], bundle.get("components") or []
	)
	new_page = frappe.get_doc(
		{
			"doctype": "Builder Page",
			"page_title": page.get("page_title") or "My Page",
			"preview": preview or None,
			"draft_blocks": compact_json(page_blocks),
			"page_data_script": page.get("page_data_script"),
			"head_html": page.get("head_html"),
			"body_html": page.get("body_html"),
			"meta_description": page.get("meta_description"),
			"project_folder": project_folder or None,
		}
	)
	for cs in bundle.get("client_scripts") or []:
		new_script = frappe.get_doc(
			{
				"doctype": "Builder Client Script",
				"name": f"{cs.get('name')}-{frappe.generate_hash(length=5)}",
				"script_type": cs.get("script_type"),
				"script": cs.get("script"),
			}
		)
		new_script.insert(ignore_permissions=True)
		new_page.append("client_scripts", {"builder_script": new_script.name})
	new_page.insert()
	# only fall back to async generation when the template carried no preview
	if not preview:
		frappe.enqueue_doc(
			"Builder Page",
			new_page.name,
			"generate_page_preview_image",
			queue="short",
			enqueue_after_commit=True,
		)
	return new_page.name or ""


@frappe.whitelist()
@has_page_write("You do not have permission to create a page.")
def create_page_from_template(template_page: str, project_folder: str | None = None) -> str:
	"""Create an editable page from a hub template and return its name."""
	try:
		bundle = hub_get("get_template_bundle", page=template_page)
	except Exception:
		frappe.log_error("Failed to fetch template bundle")
		bundle = None
	if not bundle or not bundle.get("page"):
		frappe.throw(frappe._("Could not load the selected template. Please try again."))

	assert isinstance(bundle, dict)
	return create_page_from_bundle(bundle, project_folder)


@frappe.whitelist()
@has_page_write("You do not have permission to create pages.")
def import_template_group(template_group: str, project_folder: str | None = None) -> list[str]:
	"""Import all pages from a template group and return their names."""
	groups = get_template_groups()
	group = next((g for g in groups if g.get("name") == template_group), None)
	if not group:
		frappe.throw(frappe._("Template group not found."))

	pages = group.get("pages") or []
	if not pages:
		frappe.throw(frappe._("No pages found in this template group."))

	created = []
	for page in pages:
		try:
			bundle = hub_get("get_template_bundle", page=page.get("name"))
		except Exception:
			frappe.log_error(f"Failed to fetch template bundle for {page.get('name')}")
			continue
		if not bundle or not bundle.get("page"):
			continue
		name = create_page_from_bundle(bundle, project_folder)
		created.append(name)

	if not created:
		frappe.throw(frappe._("Could not import any pages from this template group."))

	# adopting a template group = adopting its design. The group's
	# manifest can carry a header/footer design (colors, height, CTA shape...)
	# that we apply to the centrally-managed Website Header Footer Config, so
	# the site-wide navigation matches the imported template instead of
	# clashing with it (the template's own navbar/footer blocks are stripped
	# at import — see _strip_template_navigation).
	_apply_template_header_footer(group.get("header_footer"))

	return created


def get_site_contact_context(website_profile=None) -> dict:  # multi-site
	"""real, verified contact data of this site — ERPNext Company,
	its linked Address, and the header config logo. Injected into generation
	prompts so the model never fabricates an address/phone/email."""
	data = {}
	try:
		company_name = frappe.db.get_default("company")
		if not company_name:
			companies = frappe.get_all("Company", limit=1, pluck="name")
			company_name = companies[0] if companies else None
		if company_name:
			company = frappe.get_doc("Company", company_name)
			data["company_name"] = company.company_name or company_name
			if company.get("phone_no"):
				data["phone"] = company.phone_no
			if company.get("email"):
				data["email"] = company.email
			if company.get("website"):
				data["website"] = company.website
			# Note: /files/logo-default.png can BE the client's logo on a fleet
			# that replaces the default file per instance — don't filter it out.
			if company.get("company_logo"):
				data["logo"] = company.company_logo
			address_name = frappe.db.get_value(
				"Dynamic Link",
				{"link_doctype": "Company", "link_name": company_name, "parenttype": "Address"},
				"parent",
			)
			if address_name:
				address = frappe.get_doc("Address", address_name)
				parts = [
					address.address_line1,
					address.address_line2,
					f"{address.get('pincode') or ''} {address.get('city') or ''}".strip(),
					address.get("country"),
				]
				data["address"] = ", ".join(p for p in parts if p)
				if not data.get("phone") and address.get("phone"):
					data["phone"] = address.phone
				if not data.get("email") and address.get("email_id"):
					data["email"] = address.email_id
	except Exception:
		pass

	# Fallback for benches without ERPNext (the v16 Studio): Contact Us
	# Settings is frappe core on both forks and is what the shared
	# contact_info include renders — read the same source we display.
	if not data.get("company_name"):
		try:
			cus = frappe.get_doc("Contact Us Settings")
			if cus.get("address_title"):
				data["company_name"] = cus.address_title
			parts = [
				cus.get("address_line1"),
				f"{cus.get('pincode') or ''} {cus.get('city') or ''}".strip(),
				cus.get("country"),
			]
			joined = ", ".join(p for p in parts if p)
			if joined and not data.get("address"):
				data["address"] = joined
			if cus.get("phone") and not data.get("phone"):
				data["phone"] = cus.phone
			if cus.get("email_id") and not data.get("email"):
				data["email"] = cus.email_id
		except Exception:
			pass

	try:
		# multi-site: logo fallback comes from the target site's chrome
		config = _get_site_chrome_config(website_profile)
		if not data.get("logo") and config.get("logo_image"):
			data["logo"] = config.logo_image
	except Exception:
		pass

	return data


# Layout properties that belong on the constrained container, not on the
# full-bleed section that carries the background.
_LAYOUT_PROPS = (
	"display", "gridTemplateColumns", "gridTemplateRows", "gridAutoFlow",
	"gap", "rowGap", "columnGap", "alignItems", "justifyContent",
	"flexDirection", "flexWrap", "alignContent",
)

_SITE_CONTAINER = {
	"maxWidth": "var(--container-width, 1280px)",
	"marginLeft": "auto",
	"marginRight": "auto",
	"width": "100%",
}


def _split_padding(styles: dict) -> tuple:
	"""(vertical, horizontal) from whatever padding notation the block used."""
	for axis in ("paddingLeft", "paddingRight"):
		if styles.get(axis):
			return None, str(styles[axis])
	shorthand = str(styles.get("padding") or "").strip()
	if not shorthand:
		return None, None
	parts = shorthand.split()
	if len(parts) == 1:
		return parts[0], parts[0]
	if len(parts) in (2, 3):
		return parts[0], parts[1]
	return parts[0], parts[1]


def _adopt_site_photo_for_page_header() -> bool:
	"""Give the band the site's own photograph, when the brief asked for one.

	The AI can choose that the band sits on an image; it cannot upload one. The
	generation has just produced the site's photographs, and the homepage hero is
	the one that says what this site is about. Sharing it is not a shortcut — one
	photograph across the chrome reads as an identity, two unrelated ones read as
	a template.

	Only fills an empty field: an image someone chose stays.
	"""
	try:
		from unpress_core.hf_utils.header_footer import get_header_footer_config

		config = get_header_footer_config()
		if not config or (config.get("page_header_background") or "") != "Image":
			return False
		if (config.get("page_header_image") or "").strip():
			return False

		home = frappe.get_all(
			"Builder Page", filters={"route": ["in", ("home", "index", "")]}, pluck="name"
		)
		if not home:
			return False

		blocks = json.loads(frappe.db.get_value("Builder Page", home[0], "blocks") or "[]")
		url = _first_real_background(blocks)
		if not url:
			return False

		config.page_header_image = url
		config.save(ignore_permissions=True)
		frappe.db.commit()
		ai_log("info", "Page header adopted the site photo", url=url)
		return True
	except Exception as exc:
		frappe.log_error("Page header image", str(exc))
		return False


def _first_real_background(blocks, depth: int = 0) -> str:
	"""The first generated photograph used as a background, placeholders aside."""
	import re

	if depth > 8 or not isinstance(blocks, list):
		return ""
	for block in blocks:
		if not isinstance(block, dict):
			continue
		background = str((block.get("baseStyles") or {}).get("backgroundImage") or "")
		match = re.search(r"url\(['\"]?(/files/[^'\")]+)", background)
		if match:
			return match.group(1)
		found = _first_real_background(block.get("children") or [], depth + 1)
		if found:
			return found
	return ""


def _retune_container_widths(blocks, depth: int = 0) -> int:
	"""Put content containers back on the site's width AND its inset.

	Two failures, one function, because they always travel together:

	- a hard-coded width. The normalisation below only acts when a section has
	  NO container; one that exists with the WRONG width slips through. Measured
	  on a generated page: sections on 1200px while the chrome sat on 1280 —
	  sixteen pixels of staircase.
	- a missing inset. A container with the right width but no horizontal
	  padding puts the copy flush against the column edge, 24px LEFT of the
	  logo above it. Measured right after fixing the width: 224 against 248.

	The chrome's own container is `max-width: 1280px; margin: 0 auto;
	padding: 0 24px`. A content container that says the same thing lands on the
	same x, which is the entire point.
	"""
	import re

	changed = 0
	if not isinstance(blocks, list):
		return 0

	for block in blocks:
		if not isinstance(block, dict):
			continue
		styles = block.get("baseStyles") or {}
		width = str(styles.get("maxWidth") or "")

		# a bare pixel width in the 1000-1400 range is a content container
		if re.fullmatch(r"1[0-4]\d{2}px", width.strip()):
			styles["maxWidth"] = "var(--container-width, 1280px)"
			width = styles["maxWidth"]
			changed += 1

		if "var(--container-width" in width:
			has_inset = any(
				str(styles.get(k) or "").strip() not in ("", "0", "0px")
				for k in ("paddingLeft", "paddingRight", "padding")
			)
			if not has_inset:
				styles["paddingLeft"] = "24px"
				styles["paddingRight"] = "24px"
				changed += 1
			block["baseStyles"] = styles

		changed += _retune_container_widths(block.get("children") or [], depth + 1)

	return changed


def _normalise_section_rhythm(blocks) -> int:
	"""Give every top-level section the site's own horizontal rhythm.

	The header and the footer put their content in a 1280px container. Nothing
	told the model that, so it invented an inset per page — 48px here, 6vw
	there, a 1200px container on the homepage. Measured on a generated site: the
	header's content began at x=139, the page header band at x=179 and the body
	copy at x=48. Three rhythms, one page: a staircase.

	The section keeps its background full-bleed and its vertical padding; a
	container takes over the width and the layout. The layout has to MOVE, not
	be copied — a grid left on the section would fight the container it now
	holds.

	Returns how many sections were changed, so the caller can log it.
	"""
	changed = 0

	def normalise(section) -> bool:
		styles = section.get("baseStyles") or {}
		if styles.get("maxWidth"):
			return False  # already constrained by whoever wrote it

		vertical, horizontal = _split_padding(styles)
		layout = {k: styles[k] for k in _LAYOUT_PROPS if k in styles}
		# nothing to do for a plain section already sitting at the site inset
		if not layout and horizontal in (None, "24px", "0", "0px"):
			return False

		container = {
			"blockId": f"container-{frappe.generate_hash(length=8)}",
			"element": "div",
			"baseStyles": {**_SITE_CONTAINER, **layout},
			"children": section.get("children") or [],
		}
		# a responsive layout the block declared for narrow screens belongs with
		# the layout it overrides
		for key in ("mobileStyles", "tabletStyles"):
			breakpoint = section.get(key) or {}
			moved = {k: breakpoint.pop(k) for k in list(breakpoint) if k in _LAYOUT_PROPS}
			if moved:
				container[key] = moved

		for prop in layout:
			styles.pop(prop, None)
		styles.pop("padding", None)
		styles.pop("paddingLeft", None)
		styles.pop("paddingRight", None)
		if vertical:
			styles["paddingTop"] = styles.get("paddingTop") or vertical
			styles["paddingBottom"] = styles.get("paddingBottom") or vertical
		styles["paddingLeft"] = "24px"
		styles["paddingRight"] = "24px"

		section["baseStyles"] = styles
		section["children"] = [container]
		return True

	def walk(node, depth=0):
		nonlocal changed
		if depth > 3 or not isinstance(node, dict):
			return
		for child in node.get("children") or []:
			if not isinstance(child, dict):
				continue
			if str(child.get("element", "")).lower() == "section":
				if normalise(child):
					changed += 1
			else:
				walk(child, depth + 1)

	for block in blocks if isinstance(blocks, list) else []:
		if str(block.get("element", "")).lower() == "section":
			if normalise(block):
				changed += 1
		else:
			walk(block)

	return changed


def _lift_opening_into_header(blocks) -> str:
	"""Move the page's opening line up into the shared band, and return it.

	Every generated interior page opened on the same shape — an eyebrow in caps,
	then a large coloured headline — composed differently each time. The band
	above it was identical everywhere, but the eye read the headline as the real
	top of the page, so the pages still looked unrelated. That is the
	homogeneity the band was built for, undone one centimetre below it.

	Rather than delete that line, or ask the model again not to write it, the
	line moves: the headline becomes the band's subtitle, the eyebrow goes (the
	breadcrumb already says where the visitor is), and the body keeps every
	paragraph, figure and card it had.

	Only the FIRST heading of the page is eligible, and only while nothing of
	substance precedes it — a heading further down is a section title and stays
	where it belongs.
	"""
	import html
	import re

	HEADINGS = {"h1", "h2", "h3", "h4"}

	def clean(node) -> str:
		raw = node.get("innerHTML") or node.get("innerText") or ""
		text = re.sub(r"<[^>]+>", " ", str(raw))
		return re.sub(r"\s+", " ", html.unescape(text).replace("\u00a0", " ")).strip()

	state = {"line": "", "done": False}

	def visit(parent):
		"""Depth-first, in document order, pruning each parent's children once."""
		if state["done"] or not isinstance(parent, dict):
			return
		children = parent.get("children")
		if not isinstance(children, list):
			return

		keep, eyebrow_index = [], None
		for child in children:
			if state["done"]:
				keep.append(child)
				continue
			if not isinstance(child, dict):
				keep.append(child)
				continue

			text = clean(child)
			element = str(child.get("element", "")).lower()

			if text and element in HEADINGS and len(text) <= 120:
				state["line"] = text
				state["done"] = True
				# the eyebrow directly above it goes too
				if eyebrow_index is not None:
					keep.pop(eyebrow_index)
				continue

			if text and text.isupper() and len(text) <= 60:
				eyebrow_index = len(keep)  # a candidate, until something else lands
			elif text:
				# real copy before any heading: this page opens on content
				state["done"] = True
			else:
				visit(child)

			keep.append(child)

		parent["children"] = keep

	for block in blocks if isinstance(blocks, list) else []:
		visit(block)
		if state["done"]:
			break

	return state["line"]


def _describe_page(blocks) -> str:
	"""One line describing this page, taken from what the page itself says.

	It fills `meta_description`, which does two jobs: the search snippet, and
	the line under the title in the shared page header. Generated pages had
	neither — the prompt never asked for a description, so every page shipped
	without one and every band rendered as a bare breadcrumb + title.

	It deliberately prefers a **paragraph** over the page's headline. Taking the
	headline printed the same sentence twice, a few centimetres apart: once as
	the band's subtitle, once as the big coloured heading right below it. The
	first real sentence of body copy says the same thing without the echo.
	"""
	import html
	import re

	HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

	def walk(node, found, depth=0):
		if depth > 8 or not isinstance(node, dict):
			return
		raw = node.get("innerHTML") or node.get("innerText") or ""
		if raw:
			# the blocks carry markup: strip the tags, then turn &nbsp; and
			# friends back into characters — this line is read by a human and
			# by a search engine, not by a browser
			clean = re.sub(r"<[^>]+>", " ", str(raw))
			clean = html.unescape(clean).replace("\u00a0", " ")
			clean = re.sub(r"\s+", " ", clean).strip()
			# skip eyebrows (short, shouted) and bare stat numerals
			if len(clean) > 40 and not clean.isupper():
				found.setdefault(
					"heading" if str(node.get("element", "")).lower() in HEADINGS else "body",
					clean,
				)
		for child in node.get("children") or []:
			walk(child, found, depth + 1)

	found = {}
	for block in blocks if isinstance(blocks, list) else []:
		walk(block, found)
		if "body" in found:
			break

	chosen = found.get("body") or found.get("heading") or ""
	return _shorten_for_footer(chosen, limit=180) if chosen else ""


def _shorten_for_footer(text: str, limit: int = 200) -> str:
	"""A short version of the brief that does not stop mid-word.

	`text[:200]` left the footer of a generated site reading "... et les
	possib", on every page. Prefer whole sentences; failing that, the last
	complete word, with an ellipsis so the cut is visibly deliberate.
	"""
	import re

	text = (text or "").strip()
	if len(text) <= limit:
		return text

	kept = ""
	for sentence in re.findall(r"[^.!?]*[.!?]", text):
		if len(kept) + len(sentence) > limit:
			break
		kept += sentence
	if kept.strip():
		return kept.strip()

	cut = text[:limit]
	space = cut.rfind(" ")
	return (cut[:space] if space > 0 else cut).rstrip(" ,;:") + "…"


def _was_seeded_by_us(address_title: str) -> bool:
	"""Is this contact title left over from a site WE generated earlier?

	The seeding rule is "never overwrite what the user typed", which is right —
	but on a bench where several sites have been generated it cannot tell a
	human's entry from the previous generation's. So a club's contact card kept
	announcing the wellness studio that had been generated the week before.

	A title that matches the site name of an earlier chat session is ours, and
	replacing it is the whole point. Anything else is left alone.
	"""
	if not address_title:
		return False
	try:
		previous = frappe.get_all("Builder Chat Session", pluck="site_name")
	except Exception:
		return False
	return any((name or "").strip().lower() == address_title.strip().lower() for name in previous)


def _contact_context_prompt(data: dict) -> str:
	"""Prompt section carrying the verified business data."""
	labeled = [
		("company_name", "Company name"),
		("address", "Address"),
		("phone", "Phone"),
		("email", "Email"),
		("website", "Website"),
	]
	lines = [f"- {label}: {data[key]}" for key, label in labeled if data.get(key)]
	if not lines:
		return ""
	return (
		"\n\n## REAL BUSINESS DATA (use EXACTLY these values)\n"
		+ "\n".join(lines)
		+ "\nNEVER invent contact details. If a detail is not listed above "
		"(opening hours, extra phone numbers...), omit it or use an obviously "
		"neutral placeholder — never a realistic-looking fabricated value."
	)


def _blocks_fingerprint(raw) -> str:
	"""stable hash of a page's blocks JSON (order-insensitive)."""
	import hashlib

	if not raw:
		return ""
	try:
		data = json.loads(raw) if isinstance(raw, str) else raw
		normalized = json.dumps(data, sort_keys=True, ensure_ascii=False)
	except Exception:
		normalized = str(raw)
	return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _get_site_chrome_config(website_profile=None):
	"""# multi-site: generation targeting a profile writes its chrome
	into the profile's Website Header Footer Variant (bootstrapped from the
	Single on first use); otherwise the global Single (default site / fleet)."""
	if website_profile and frappe.db.exists("DocType", "Website Header Footer Variant"):
		if not frappe.db.exists("Website Header Footer Variant", website_profile):
			single = frappe.get_single("Website Header Footer Config")
			variant = frappe.new_doc("Website Header Footer Variant")
			for f in variant.meta.fields:
				if f.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Table", "Table MultiSelect"):
					continue
				if f.fieldname == "website_profile":
					continue
				try:
					variant.set(f.fieldname, single.get(f.fieldname))
				except Exception:
					pass
			variant.website_profile = website_profile
			variant.insert(ignore_permissions=True)
			frappe.db.commit()
		return frappe.get_doc("Website Header Footer Variant", website_profile)
	return frappe.get_single("Website Header Footer Config")


def classify_existing_pages(website_profile=None) -> dict:
	"""classify the site's pages for the regenerate decision.

	- untouched: AI-generated pages never edited since (current blocks hash
	  still matches the hash stamped at generation) — safe to replace silently
	- protected: pages a user designed or edited (hand-made pages, imported
	  templates kept as drafts, or AI pages whose blocks changed since
	  generation) — replacing them requires explicit confirmation
	Template pages and hub staging are excluded entirely.
	"""
	filters = {"is_template": 0}
	# multi-site: a profile-targeted generation only classifies its
	#//// own pages; an untargeted one never touches profile-tagged pages.
	if frappe.db.has_column("Builder Page", "neo_website_profile"):
		filters["neo_website_profile"] = website_profile if website_profile else ("is", "not set")
	pages = frappe.get_all(
		"Builder Page",
		filters=filters,
		fields=[
			"name", "page_title", "project_folder",
			"ai_generated_at", "ai_blocks_hash", "blocks", "draft_blocks",
		],
	)
	untouched, protected = [], []
	for p in pages:
		if (p.project_folder or "").startswith("Hub Inbox"):
			continue
		info = {"name": p.name, "title": p.page_title}
		current = _blocks_fingerprint(p.draft_blocks or p.blocks)
		if p.ai_generated_at and p.ai_blocks_hash and current == p.ai_blocks_hash:
			untouched.append(info)
		else:
			protected.append(info)
	return {"untouched": untouched, "protected": protected}


# Brief fields applied 1:1 to Website Header Footer Config (site chrome).
# Colors are applied only when non-empty; enum fields always carry a value.
BRIEF_CHROME_FIELDS = (
	# the design system first: these become the site's CSS variables, and the
	# pages reference them instead of carrying their own copies
	# The palette itself. The chrome is configured BEFORE the brief exists, so
	# it saw primary_color=None and kept the previous site's colours — a
	# glassblower's site whose header was still the football club's slate.
	# This list runs after the brief, which is the whole point of it.
	"primary_color", "secondary_color",
	"radius_style", "shadow_style", "button_hover", "motion_style",
	"header_bg_color", "header_text_color", "header_height", "header_border",
	"header_style",
	"cta_style", "cta_shape", "cta_size",
	"footer_template", "footer_bg_color", "footer_text_color",
	# the band that opens every interior page: decided ONCE here, drawn by the
	# site everywhere, never redrawn by a page
	"page_header_template", "page_header_background", "page_header_bg_color",
	"show_breadcrumbs",
)


def apply_brief_site_chrome(design_brief, website_profile=None) -> list[str]:
	"""apply the design brief's header/footer design (site chrome)
	to the Website Header Footer Config. Returns the list of applied fields."""
	# multi-site: targeted generations write the profile's Variant
	config = _get_site_chrome_config(website_profile)
	applied = []
	for field in BRIEF_CHROME_FIELDS:
		value = getattr(design_brief, field, None)
		if value in (None, ""):
			continue
		if config.get(field) != value:
			config.set(field, value)
		applied.append(field)
	if applied:
		config.save(ignore_permissions=True)
		frappe.db.commit()
	return applied


# Website Header Footer Config fields a hub template manifest may configure.
TEMPLATE_HF_ALLOWED_FIELDS = {
	"radius_style", "shadow_style", "button_hover", "motion_style",
	"header_layout", "header_style", "sticky_header", "header_height", "header_border",
	"header_bg_color", "header_text_color",
	"show_cta", "cta_text", "cta_url", "cta_style", "cta_shape", "cta_size",
	"footer_template", "footer_bg_color", "footer_text_color",
	"primary_color", "secondary_color", "background_color", "text_color",
	"heading_font", "body_font",
}


def _apply_template_header_footer(hf: dict | None) -> None:
	"""apply a template group's header/footer design to the site's
	Website Header Footer Config (whitelisted fields only)."""
	if not hf or not isinstance(hf, dict):
		return
	try:
		config = frappe.get_single("Website Header Footer Config")
	except Exception:
		return
	changed = False
	for field, value in hf.items():
		if field in TEMPLATE_HF_ALLOWED_FIELDS and value not in (None, ""):
			config.set(field, value)
			changed = True
	if changed:
		config.save(ignore_permissions=True)
		frappe.clear_cache()


@frappe.whitelist()
@has_page_write("You do not have permission to delete a folder.")
def delete_folder(folder_name: str) -> None:
	# remove folder from all pages in a single update
	frappe.db.set_value(
		"Builder Page", {"project_folder": folder_name}, "project_folder", "", update_modified=False
	)

	frappe.db.delete("Builder Project Folder", {"folder_name": folder_name})


@frappe.whitelist()
@has_page_write("You do not have permission to sync a component.")
def sync_component(component_id: str):
	component = frappe.get_doc("Builder Component", component_id)
	component.sync_component()


@frappe.whitelist()
@has_page_read("You do not have permission to view analytics.")
def get_page_analytics(
	route: str,
	interval: str = "daily",
	from_date: str | None = None,
	to_date: str | None = None,
	route_filter_type: str = "wildcard",
):
	return builder_analytics.get_page_analytics(
		route=route,
		interval=interval,
		from_date=from_date,
		to_date=to_date,
		route_filter_type=route_filter_type,
	)


@frappe.whitelist()
@has_page_read("You do not have permission to view analytics.")
def get_overall_analytics(
	interval: str = "daily",
	route: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	route_filter_type: str = "wildcard",
):
	return builder_analytics.get_overall_analytics(
		interval=interval,
		route=route,
		from_date=from_date,
		to_date=to_date,
		route_filter_type=route_filter_type,
	)


@frappe.whitelist()
@has_page_read("You do not have permission to view analytics.")
def get_page_ctr(
	route: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	route_filter_type: str = "wildcard",
):
	return builder_analytics.get_page_ctr(
		route=route,
		from_date=from_date,
		to_date=to_date,
		route_filter_type=route_filter_type,
	)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def make_click_log(
	element: str | None = None,
	text: str | None = None,
	visitor_id: str | None = None,
):
	"""Autocapture a click on a published Builder page. Mirrors Frappe's make_view_log so
	clicks share the exact same `path` (derived from the Referer) as Web Page View rows."""
	from frappe.website.doctype.web_page_view.web_page_view import is_tracking_enabled

	if not is_tracking_enabled():
		return

	path = frappe.request.headers.get("Referer")
	if not frappe.utils.is_site_link(path):
		return

	path = urlparse(path).path
	if path != "/" and path.startswith("/"):
		path = path[1:]
	if path.startswith(("api/", "app/", "assets/", "private/files/")):
		return

	is_unique = bool(visitor_id) and not frappe.db.exists(
		"Builder Page Click", {"visitor_id": visitor_id, "path": path, "element": element or ""}
	)

	click = frappe.new_doc("Builder Page Click")
	click.path = path
	click.element = element
	click.text = text[:140] if text else text  # cap server-side; deferred_insert skips controller validation
	click.is_unique = is_unique
	click.visitor_id = visitor_id

	try:
		click.deferred_insert()
	except Exception:
		frappe.log_error("Failed to log builder page click")


def get_keys_for_autocomplete(
	key: str,
	value: Any,
	depth: int = 0,
	max_depth: int | None = None,
):
	if max_depth and depth > max_depth:
		return None  # Or some other sentinel value to indicate termination

	if key.startswith("_"):
		return None

	if isinstance(value, NamespaceDict | dict) and value:
		result = {}
		for k, v in value.items():
			nested_result = get_keys_for_autocomplete(
				k,
				v,
				depth + 1,
				max_depth=max_depth,
			)
			if nested_result is not None:  # Only add if not terminated
				result[k] = nested_result
		return result if result else None  # Return None if the dictionary is empty

	else:
		if isinstance(value, type) and issubclass(value, Exception):
			var_type = "type"  # Exceptions are types
		elif isinstance(value, ModuleType):
			var_type = "namespace"
		elif isinstance(value, FunctionType | MethodType):
			var_type = "function"
		elif isinstance(value, type):
			var_type = "type"
		elif isinstance(value, dict):
			var_type = "property"  # Assuming dict should be mapped to other
		else:
			var_type = "property"  # Default to text if no other type matches
		return {"true_type": type(value).__name__, "type": var_type}


@frappe.whitelist()
@redis_cache()
def get_codemirror_completions():
	return get_keys_for_autocomplete(
		key="",
		value=get_safe_globals(),
	)


@frappe.whitelist()
@has_page_write("You do not have permission to reorder client scripts")
def reorder_client_scripts(script_order: list[str]):
	for idx, script_name in enumerate(script_order, start=1):
		frappe.db.set_value("Builder Page Client Script", script_name, "idx", idx)


@frappe.whitelist()
@has_page_write("You do not have permission to evaluate component scripts")
def get_component_data(
	component_name: str, props: dict | str | None = None, script: str | None = None
) -> dict:
	from builder.builder.doctype.builder_component.builder_component import (
		get_component_data as _get_component_data,
	)

	return _get_component_data(component_name, props, script)


# =============================================================================
# WEBSITE HEADER FOOTER CONFIG API
# =============================================================================

@frappe.whitelist(allow_guest=True)
def render_site_header():
	"""
	Render the site header from Website Header Footer Config.

	Returns:
		str: HTML for the header
	"""
	from unpress_core.hf_utils.header_footer import render_header
	return render_header()


@frappe.whitelist(allow_guest=True)
def render_site_footer():
	"""
	Render the site footer from Website Header Footer Config.

	Returns:
		str: HTML for the footer
	"""
	from unpress_core.hf_utils.header_footer import render_footer
	return render_footer()


@frappe.whitelist()
def get_header_layout_info():
	"""
	Get information about header layouts.

	Returns:
		dict: Available layouts with descriptions
	"""
	return {
		"Logo | Menu Center | Icons": {
			"layout": "A",
			"menu": "center",
			"description": "Logo on left, menu centered, icons and CTA on right"
		},
		"Logo | Menu Right | Icons": {
			"layout": "A",
			"menu": "right",
			"description": "Logo on left, menu aligned right, icons and CTA on right"
		},
		"Menu Left | Logo Center | Icons": {
			"layout": "B",
			"menu": "left",
			"description": "Menu on left, logo centered, icons and CTA on right"
		}
	}


@frappe.whitelist()
def get_search_type_info():
	"""
	Get information about search types.

	Returns:
		dict: Available search types with descriptions
	"""
	return {
		"None": {
			"description": "No search functionality"
		},
		"Icon (overlay)": {
			"description": "Search icon that opens a slide-down overlay"
		},
		"Search Bar (inline)": {
			"description": "Search bar displayed inline next to icons"
		},
		"Search Bar (full width bottom)": {
			"description": "Full width search bar displayed below the header"
		}
	}


@frappe.whitelist()
def add_page_to_menu(page_name: str, label: str = None, url: str = None):
	"""
	Add a Builder Page to the Website Header Footer Config menu.

	Args:
		page_name: Name of the Builder Page
		label: Menu label (defaults to page title)
		url: Menu URL (defaults to page route)

	Returns:
		dict: The added menu item
	"""
	page = frappe.get_doc("Builder Page", page_name)

	if not label:
		label = page.page_title or page.page_name

	if not url:
		url = f"/{page.route}" if page.route else "/"

	config = frappe.get_single("Website Header Footer Config")
	config.append("menu_items", {
		"label": label,
		"url": url,
		"is_external": False,
		"open_in_new_tab": False,
	})
	config.save()

	return {
		"label": label,
		"url": url,
	}


@frappe.whitelist()
def auto_populate_menu_from_pages():
	"""
	Auto-populate the menu with all published Builder Pages.

	Returns:
		list: Added menu items
	"""
	pages = frappe.get_all(
		"Builder Page",
		filters={"published": 1},
		fields=["name", "page_title", "route"],
		order_by="modified desc"
	)

	config = frappe.get_single("Website Header Footer Config")

	# Clear existing menu items
	config.menu_items = []

	added = []
	for page in pages:
		label = page.page_title or page.name
		url = f"/{page.route}" if page.route else "/"

		# Don't add duplicates
		if any(item.url == url for item in config.menu_items):
			continue

		config.append("menu_items", {
			"label": label,
			"url": url,
			"is_external": False,
			"open_in_new_tab": False,
		})
		added.append({"label": label, "url": url})

	config.save()
	return added


@frappe.whitelist()
def apply_site_type_defaults(site_type: str):
	"""
	Apply default header/footer settings based on site type.

	Args:
		site_type: Type of site (vitrine, vitrine_user, blog, ecommerce, ecommerce_search)

	Returns:
		dict: Applied settings
	"""
	SITE_TYPE_DEFAULTS = {
		"vitrine": {
			"header_layout": "Logo | Menu Center | Icons",
			"search_type": "None",
			"show_cta": True,
			"show_user": False,
			"show_wishlist": False,
			"show_cart": False,
		},
		"vitrine_user": {
			"header_layout": "Logo | Menu Center | Icons",
			"search_type": "None",
			"show_cta": True,
			"show_user": True,
			"show_wishlist": False,
			"show_cart": False,
		},
		"blog": {
			"header_layout": "Logo | Menu Center | Icons",
			"search_type": "Icon (overlay)",
			"show_cta": True,
			"show_user": True,
			"show_wishlist": False,
			"show_cart": False,
		},
		"ecommerce": {
			"header_layout": "Logo | Menu Center | Icons",
			"search_type": "Icon (overlay)",
			"show_cta": False,
			"show_user": True,
			"show_wishlist": True,
			"show_cart": True,
		},
		"ecommerce_search_inline": {
			"header_layout": "Logo | Menu Center | Icons",
			"search_type": "Search Bar (inline)",
			"show_cta": False,
			"show_user": True,
			"show_wishlist": True,
			"show_cart": True,
		},
		"ecommerce_search_full": {
			"header_layout": "Logo | Menu Center | Icons",
			"search_type": "Search Bar (full width bottom)",
			"show_cta": False,
			"show_user": True,
			"show_wishlist": True,
			"show_cart": True,
		},
	}

	defaults = SITE_TYPE_DEFAULTS.get(site_type, SITE_TYPE_DEFAULTS["vitrine"])

	config = frappe.get_single("Website Header Footer Config")

	for key, value in defaults.items():
		if hasattr(config, key):
			setattr(config, key, value)

	config.save()

	return defaults


# =============================================================================
# NEWSLETTER SUBSCRIPTION API
# =============================================================================

@frappe.whitelist(allow_guest=True)
def subscribe_to_newsletter(email: str, email_group: str = None):
	"""
	Subscribe an email address to an Email Group (newsletter).

	Args:
		email: Email address to subscribe
		email_group: Name of the Email Group (optional, uses config default if not provided)

	Returns:
		dict with success status and message
	"""
	from frappe.utils import validate_email_address

	# Validate email
	if not email:
		frappe.throw(_("Email is required"))

	email = email.strip().lower()
	if not validate_email_address(email, throw=False):
		frappe.throw(_("Invalid email address"))

	# Get email group from config if not provided
	if not email_group:
		config = frappe.get_single("Website Header Footer Config")
		email_group = getattr(config, "newsletter_email_group", None)

	if not email_group:
		frappe.throw(_("No Email Group configured for newsletter"))

	# Check if Email Group exists
	if not frappe.db.exists("Email Group", email_group):
		frappe.throw(_("Email Group not found"))

	# Check if already subscribed
	if frappe.db.exists("Email Group Member", {"email_group": email_group, "email": email}):
		return {
			"success": True,
			"message": _("You are already subscribed to our newsletter"),
			"already_subscribed": True
		}

	# Add to Email Group
	try:
		doc = frappe.get_doc({
			"doctype": "Email Group Member",
			"email_group": email_group,
			"email": email
		})
		doc.insert(ignore_permissions=True)

		# Update subscriber count
		frappe.get_doc("Email Group", email_group).update_total_subscribers()

		# Send welcome email if configured
		welcome_template = frappe.db.get_value("Email Group", email_group, "welcome_email_template")
		if welcome_template:
			try:
				template = frappe.get_doc("Email Template", welcome_template)
				message = frappe.render_template(template.response_, {"email": email, "email_group": email_group})
				frappe.sendmail(email, subject=template.subject, message=message)
			except Exception:
				pass  # Don't fail subscription if welcome email fails

		return {
			"success": True,
			"message": _("Thank you for subscribing to our newsletter!"),
			"already_subscribed": False
		}

	except frappe.DuplicateEntryError:
		return {
			"success": True,
			"message": _("You are already subscribed to our newsletter"),
			"already_subscribed": True
		}
	except Exception as e:
		frappe.log_error("Newsletter subscription failed", str(e))
		frappe.throw(_("Failed to subscribe. Please try again later."))


# =============================================================================
# BUILDER SHORTCODES API
# =============================================================================

@frappe.whitelist()
def get_available_shortcodes():
	"""
	Get all enabled shortcodes for use in Builder pages.

	Returns:
		list: List of shortcode objects with usage info
	"""
	shortcodes = frappe.get_all(
		"Builder Shortcode",
		filters={"enabled": 1},
		fields=["shortcode_name", "category", "source_app", "template_path",
				"description", "usage_syntax", "parameters", "example_code"],
		order_by="category, shortcode_name"
	)

	# Parse JSON parameters
	for sc in shortcodes:
		if sc.get("parameters"):
			try:
				sc["parameters"] = json.loads(sc["parameters"])
			except Exception:
				sc["parameters"] = []

	return shortcodes


@frappe.whitelist()
def generate_image(
	prompt: str,
	size: str = None,
	negative_prompt: str = None,
	async_generation: bool = False,
	callback_doctype: str = None,
	callback_name: str = None,
	callback_field: str = None,
):
	"""
	Generate an image using AI (Flux via Ollama).

	Args:
		prompt: Text description of the image to generate
		size: Image size (e.g., "1024x1024", "512x512", "1024x576")
		negative_prompt: What to avoid in the image
		async_generation: If True, runs in background and returns job ID
		callback_doctype: DocType to update when done (for async)
		callback_name: Document name to update (for async)
		callback_field: Field to store the image URL (for async)

	Returns:
		dict: Generated image info or job ID for async
	"""
	from unpress_core.ai.generators.image_generator import ImageGenerator

	generator = ImageGenerator()

	if async_generation:
		# Queue as background job
		job_id = generator.generate_async(
			prompt=prompt,
			size=size,
			negative_prompt=negative_prompt,
			callback_doctype=callback_doctype,
			callback_name=callback_name,
			callback_field=callback_field,
		)
		return {
			"job_id": job_id,
			"status": "queued",
			"message": "Image generation started in background"
		}
	else:
		# Generate synchronously
		result = generator.generate(
			prompt=prompt,
			size=size,
			negative_prompt=negative_prompt,
		)
		return {
			"file_url": result.file_url,
			"file_doc_name": result.file_doc_name,
			"prompt": result.prompt,
			"width": result.width,
			"height": result.height,
		}


# =============================================================================
# INSPIRATION API
# =============================================================================

def _inspiration_module():
	"""The Builder Site Inspiration controller — the one unpress_core owns."""
	from unpress_core.unpress_core.doctype.builder_site_inspiration import (
		builder_site_inspiration,
	)

	return builder_site_inspiration


@frappe.whitelist()
def capture_inspiration(
	url: str = None,
	image: str = None,
	sentiment: str = "like",
	description: str = None,
):
	"""
	Capture a website or image for design inspiration.

	Args:
		url: Website URL to capture (optional)
		image: Uploaded image file URL (optional)
		sentiment: User sentiment (like, dislike, neutral)
		description: User notes about what they like/dislike

	Returns:
		dict with doc name and status
	"""
	return _inspiration_module().capture_inspiration(
		url=url, image=image, sentiment=sentiment, description=description
	)


@frappe.whitelist()
def get_inspirations(limit: int = 20, sentiment: str = None):
	"""
	Get list of captured inspirations.

	Args:
		limit: Max number to return
		sentiment: Optional filter by sentiment (like, dislike, neutral)

	Returns:
		List of inspiration summaries with dominant colors
	"""
	return _inspiration_module().get_inspirations(limit=int(limit), sentiment=sentiment)


@frappe.whitelist()
def analyze_inspirations_for_generation(inspiration_names: str = None):
	"""
	Analyze inspirations and return aggregated data for AI generation.

	Args:
		inspiration_names: JSON array of inspiration names (or None for all)

	Returns:
		Aggregated inspiration data for the design brief
	"""
	return _inspiration_module().analyze_inspirations_for_generation(
		inspiration_names=inspiration_names
	)


@frappe.whitelist()
def get_shortcodes_for_ai():
	"""
	Get shortcodes formatted for AI prompt context.

	Returns:
		str: Markdown formatted shortcode documentation
	"""
	shortcodes = frappe.get_all(
		"Builder Shortcode",
		filters={"enabled": 1},
		fields=["shortcode_name", "category", "description", "usage_syntax", "parameters", "example_code"],
		order_by="category, shortcode_name"
	)

	if not shortcodes:
		return ""

	lines = ["## Available Shortcodes\n"]
	lines.append("You can use these Jinja includes in Builder pages:\n")

	current_category = None
	for sc in shortcodes:
		if sc.category != current_category:
			current_category = sc.category
			lines.append(f"\n### {current_category}\n")

		lines.append(f"#### {sc.shortcode_name}")
		if sc.description:
			lines.append(f"{sc.description}\n")
		if sc.usage_syntax:
			lines.append(f"**Usage:**\n```jinja\n{sc.usage_syntax}\n```\n")
		if sc.example_code:
			lines.append(f"**Example:**\n```jinja\n{sc.example_code}\n```\n")

	return "\n".join(lines)


# =========================================================================
# CHAT API ENDPOINTS
# =========================================================================

@frappe.whitelist()
def chat_start_session():
	"""Start a new builder chat session or resume an existing active session."""
	from unpress_core.chat_service import BuilderChatService
	service = BuilderChatService()
	return service.start_session(user=frappe.session.user)


@frappe.whitelist()
def chat_clear_session(session_id: str):
	"""Abandon the current session to force a fresh start on next load."""
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	session_name = frappe.db.get_value(
		"Builder Chat Session",
		{"session_id": session_id, "user": frappe.session.user}
	)
	if session_name:
		frappe.db.set_value("Builder Chat Session", session_name, "status", "Abandoned")
		frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def chat_send_message(session_id: str, message: str):
	"""Send a message to the builder chat and get a response."""
	from unpress_core.chat_service import BuilderChatService
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	if not message:
		return {"success": False, "message": _("Message is required")}
	service = BuilderChatService()
	return service.process_message(session_id, message)


@frappe.whitelist()
def chat_upload_logo(session_id: str, file_url: str):
	"""Handle logo upload for a chat session."""
	from unpress_core.chat_service import BuilderChatService
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	if not file_url:
		return {"success": False, "message": _("File URL is required")}
	service = BuilderChatService()
	return service.upload_logo(session_id, file_url)


@frappe.whitelist()
def chat_upload_inspiration(session_id: str, file_url: str):
	"""Upload an inspiration image for a chat session."""
	from unpress_core.chat_service import BuilderChatService
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	if not file_url:
		return {"success": False, "message": _("File URL is required")}
	service = BuilderChatService()
	return service.upload_inspiration(session_id, file_url)


@frappe.whitelist()
def chat_attach_files(session_id: str, files):
	"""Attach any files to a chat session — the service decides what they are."""
	from unpress_core.chat_service import BuilderChatService
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	if not files:
		return {"success": False, "message": _("File URL is required")}
	service = BuilderChatService()
	return service.attach_files(session_id, files)


@frappe.whitelist()
def chat_trigger_generation(session_id: str):
	"""Trigger site generation with collected parameters."""
	from unpress_core.chat_service import BuilderChatService
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	service = BuilderChatService()
	return service.trigger_generation(session_id)


@frappe.whitelist()
def chat_get_generation_status(session_id: str):
	"""Get the current generation status for polling."""
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	try:
		session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
		if not session.job_id:
			return {"success": False, "message": _("No generation job found")}
		status = get_site_generation_status(session.job_id)
		# If cache has valid data (not "not_found"), return it
		if status and status.get("status") != "not_found":
			return status
		# Cache empty — fall back to session document data
		result = {
			"status": session.generation_status or "unknown",
			"progress": session.generation_progress or 0,
		}
		# If session has generated pages, include them
		if session.status in ("Completed", "Failed", "Homepage Ready") and session.generated_pages:
			pages = json.loads(session.generated_pages) if isinstance(session.generated_pages, str) else session.generated_pages
			result["pages_created"] = pages
			if session.status == "Completed":
				result["status"] = "completed"
				result["progress"] = 100
			elif session.status == "Homepage Ready":
				result["status"] = "homepage_ready"
				result["progress"] = 20
				result["total_pages"] = len(json.loads(session.pages_config)) if session.pages_config else 0
			elif session.status == "Failed":
				result["status"] = "failed"
				result["progress"] = 0
		return result
	except frappe.DoesNotExistError:
		return {"success": False, "message": _("Session not found")}
	except Exception as e:
		frappe.log_error("Builder Chat: Get generation status error", str(e))
		return {"success": False, "message": _("Failed to get generation status")}


@frappe.whitelist()
def chat_generate_images(session_id: str):
	"""Trigger AI image generation for all placeholder images in generated pages."""
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}

	try:
		session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})

		# Get generated pages
		generated_pages = json.loads(session.generated_pages) if session.generated_pages else []
		if not generated_pages and session.job_id:
			status = _get_generation_status(session.job_id)
			generated_pages = status.get("pages_created", [])

		if not generated_pages:
			return {"success": False, "message": _("No generated pages found")}

		page_names = [p["name"] for p in generated_pages]

		# STEP 1 — place the client's OWN photos first (free, no Flux, always on,
		# not gated by image_generation_enabled).
		from unpress_core.ai.ingestion.image_matcher import match_and_apply
		try:
			match_result = match_and_apply(session_id, page_names)
		except Exception as e:
			match_result = {"matched": 0}
			frappe.log_error("Client image matching failed", str(e))

		# STEP 2 — image generation fills only the slots no client photo matched.
		# Backend: self-hosted ComfyUI (our GPU) when configured, else the legacy
		# Ollama generator gated by the "image_generation_enabled" flag.
		from unpress_core.ai.generators import comfyui_client
		placeholder_images = _scan_placeholder_images(page_names, subject=_image_subject(session_id))

		if not placeholder_images:
			return {"success": True, "matched": match_result.get("matched", 0),
				"message": _("All images filled from the client's own photos.")}

		if not _image_backend_available():
			return {"success": True, "matched": match_result.get("matched", 0),
				"remaining_placeholders": len(placeholder_images),
				"message": _("Client photos placed. {0} slot(s) left as placeholders (image generation is off here).").format(len(placeholder_images))}

		img_job_id = _enqueue_image_generation(placeholder_images, session_id=session_id)

		return {
			"success": True,
			"job_id": img_job_id,
			"total_images": len(placeholder_images),
			"status": "queued",
		}
	except Exception as e:
		frappe.log_error("Chat: Image generation trigger failed", str(e))
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def chat_get_image_generation_status(job_id: str = None, session_id: str = None):
	"""Get the status of an image generation job."""
	if not job_id and session_id:
		# Look up job_id from session
		session_name = frappe.db.get_value(
			"Builder Chat Session", {"session_id": session_id}, "name"
		)
		if session_name:
			job_id = frappe.db.get_value(
				"Builder Chat Session", session_name, "image_job_id"
			)
	if not job_id:
		return {"success": False, "message": _("Job ID is required")}
	return _get_generation_status(job_id)


def _image_subject(session_id: str = None, site_name: str = None, site_description: str = None) -> str:
	"""One short phrase describing the business, for image slots with no text.

	A hero background rarely carries a description; without this the model is
	asked for a stock photo and answers with one.
	"""
	description = (site_description or "").strip()
	name = (site_name or "").strip()
	if not description and session_id:
		try:
			row = frappe.db.get_value(
				"Builder Chat Session",
				{"session_id": session_id},
				["site_name", "site_description"],
				as_dict=True,
			)
			if row:
				description = (row.site_description or "").strip()
				name = name or (row.site_name or "").strip()
		except Exception:
			pass
	subject = description or name
	if len(subject) <= 180:
		return subject.rstrip(" .,;")
	# the model reads a sentence better than a paragraph — and a phrase cut
	# mid-word reads as noise, so stop on the last clean break
	head = subject[:180]
	for stop in (". ", " ; ", ", "):
		cut = head.rfind(stop)
		if cut > 60:
			return head[:cut].rstrip(" .,;")
	return head[: head.rfind(" ")].rstrip(" .,;")


def _scan_placeholder_images(page_names: list, subject: str = "") -> list:
	"""Scan Builder Pages for img blocks with placehold.co URLs.

	`subject` describes the business; slots with no description of their own
	fall back to it rather than to a generic stock photo."""
	import re
	results = []

	for page_name in page_names:
		try:
			page = frappe.get_doc("Builder Page", page_name)
			blocks = json.loads(page.blocks) if page.blocks else []
			_walk_blocks_for_placeholders(blocks, page_name, results, subject=subject)
		except Exception as e:
			frappe.log_error("Scan placeholder images error", f"Page {page_name}: {str(e)}")

	return results


QUALITY_SUFFIX = "photorealistic, high resolution, no text, no words, no logos, no letters"


def _build_image_prompt(context: str, is_background: bool = False, subject: str = "") -> str:
	"""Build an image generation prompt from context text.

	Avoids words like 'website', 'section', 'page' that cause Flux
	to generate website mockups instead of photographs.

	`subject` is what the site is about. It is the fallback when a slot
	carries no description of its own — a hero background usually does not.
	Without it the fallback used to ask for "beautiful landscape photography",
	which is why a yoga studio got a mountain lake above the fold.
	"""
	# Words that are too generic/abstract for image generation
	generic_words = {"Hero Image", "Feature", "Image", "Photo", "Hero", "Section", "Banner"}

	if not context or context.strip() in generic_words:
		if subject:
			lead = "atmospheric photography of" if is_background else "professional photography of"
			return f"{lead} {subject}, natural lighting, {QUALITY_SUFFIX}"
		if is_background:
			return f"atmospheric interior photography, soft natural lighting, {QUALITY_SUFFIX}"
		return f"professional product photography, clean background, {QUALITY_SUFFIX}"

	# Clean up context: remove page-type words that confuse image models
	import re as _re
	cleaned = context.strip()
	# Remove page-type words (Accueil, Contact, About, etc.)
	page_words = _re.compile(
		r'\b(accueil|home|contact|about|à propos|services?|blog|shop|boutique|page|section|hero|banner)\b',
		_re.IGNORECASE
	)
	cleaned = page_words.sub("", cleaned).strip()
	# Remove leftover multiple spaces
	cleaned = _re.sub(r'\s+', ' ', cleaned).strip()

	if not cleaned or len(cleaned) < 3:
		return _build_image_prompt("", is_background=is_background, subject=subject)

	if is_background:
		return f"beautiful photography related to {cleaned}, atmospheric lighting, photorealistic, high resolution, no text, no words, no logos, no letters"
	return f"professional photography of {cleaned}, clean composition, photorealistic, high resolution, no text, no words, no logos, no letters"


def _walk_blocks_for_placeholders(blocks, page_name, results, subject: str = ""):
	"""Recursively walk blocks to find placehold.co URLs in img src or background images."""
	import re

	if not isinstance(blocks, list):
		return

	for block in blocks:
		if not isinstance(block, dict):
			continue

		block_id = block.get("blockId", "")

		# Check <img> elements
		if block.get("element") == "img":
			attrs = block.get("attributes", {})
			src = attrs.get("src", "")
			if "placehold.co" in src and block_id:
				size_match = re.search(r"placehold\.co/(\d+)x(\d+)", src)
				if size_match:
					w, h = int(size_match.group(1)), int(size_match.group(2))
					if w < 200 or h < 200:
						pass  # Skip small images (avatars, icons)
					else:
						size = f"{w}x{h}"
						alt = _build_image_prompt(attrs.get("alt", ""), is_background=False, subject=subject)
						results.append({
							"page_name": page_name,
							"block_id": block_id,
							"src": src,
							"alt": alt,
							"size": size,
							"type": "img",
						})
				else:
					alt = _build_image_prompt(attrs.get("alt", ""), is_background=False, subject=subject)
					results.append({
						"page_name": page_name,
						"block_id": block_id,
						"src": src,
						"alt": alt,
						"size": "1024x1024",
						"type": "img",
					})

		# Check CSS background images (backgroundImage or background with url())
		if block_id:
			styles = block.get("baseStyles", {})
			bg = styles.get("backgroundImage", "") or ""
			if not bg:
				bg_prop = styles.get("background", "") or ""
				if "url(" in bg_prop:
					bg = bg_prop

			if "placehold.co" in bg:
				size_match = re.search(r"placehold\.co/(\d+)x(\d+)", bg)
				size = f"{size_match.group(1)}x{size_match.group(2)}" if size_match else "1920x1080"
				# Extract text param as thematic context (NOT literal text to render in image)
				text_match = re.search(r"text=([^&'\"]+)", bg)
				context = text_match.group(1).replace("+", " ") if text_match else ""
				alt = _build_image_prompt(context, is_background=True, subject=subject)
				results.append({
					"page_name": page_name,
					"block_id": block_id,
					"src": bg,
					"alt": alt,
					"size": size,
					"type": "background",
				})

		# Recurse into children
		if block.get("children"):
			_walk_blocks_for_placeholders(block["children"], page_name, results, subject=subject)


def _generate_images_worker(img_job_id: str, placeholder_images: list):
	"""Background worker that fills placeholder images. Prefers the self-hosted
	ComfyUI server (FLUX.2, our GPU) when configured; falls back to the Ollama
	ImageGenerator otherwise."""
	import re as _re
	from unpress_core.ai.generators.image_generator import ImageGenerator
	from unpress_core.ai.generators import comfyui_client
	from unpress_core.ai.logging import ai_log

	total = len(placeholder_images)
	completed = 0
	failed = 0

	# Backend order: the site's explicit choice first, then ComfyUI when it is
	# actually healthy (on a shared GPU its graph dies out-of-memory and every
	# failure used to be swallowed per image — sites silently kept their
	# placeholders), then the OpenAI-compatible endpoint.
	from unpress_core.ai.config import get_ai_settings, get_image_settings

	settings = get_image_settings()
	backend = "openai-compatible"
	codex = None
	generator = None

	if settings.get("provider") == "codex":
		from unpress_core.ai.providers.codex_provider import CodexProvider

		ok, why = CodexProvider.login_status()
		if ok:
			backend, codex = "codex", CodexProvider(
				reasoning_effort=get_ai_settings().reasoning_effort
			)
		else:
			ai_log("warning", "Codex unavailable, falling back", reason=why)

	if backend != "codex" and comfyui_client.is_configured():
		healthy, why = comfyui_client.health()
		if healthy:
			backend = "comfyui"
		else:
			ai_log("warning", "ComfyUI unavailable, falling back", reason=why)

	use_comfy = backend == "comfyui"
	if backend == "openai-compatible":
		generator = ImageGenerator()
	ai_log("info", "image backend selected", backend=backend, slots=total)

	for idx, img_info in enumerate(placeholder_images):
		prompt = img_info["alt"]
		size = img_info["size"]
		page_name = img_info["page_name"]
		block_id = img_info["block_id"]

		short_prompt = prompt[:50] + "..." if len(prompt) > 50 else prompt
		_update_generation_status(img_job_id, {
			"status": "running",
			"progress": int((idx / total) * 100),
			"total_images": total,
			"images_completed": completed,
			"images_failed": failed,
			"current_image": f"{short_prompt} ({idx + 1}/{total})",
			"error": None,
		})

		try:
			img_type = img_info.get("type", "img")
			m = _re.match(r"(\d+)x(\d+)", size or "")
			w, h = (int(m.group(1)), int(m.group(2))) if m else (1024, 1024)
			if codex:
				content = codex.generate_image_file(prompt, width=w, height=h)
				new_url = _save_generated_png(content, prefix="codex")
			elif use_comfy:
				new_url = comfyui_client.generate_image(prompt, width=w, height=h)
			else:
				new_url = generator.generate(prompt=prompt, size=size).file_url
			_replace_image_in_page(page_name, block_id, new_url, img_type=img_type)
			completed += 1
		except Exception as e:
			failed += 1
			frappe.log_error(
				"Image generation failed",
				f"Prompt: {prompt[:100]}\nPage: {page_name}\nBlock: {block_id}\nError: {str(e)}"
			)
			continue

	_adopt_site_photo_for_page_header()

	_update_generation_status(img_job_id, {
		"status": "completed",
		"progress": 100,
		"total_images": total,
		"images_completed": completed,
		"images_failed": failed,
		"current_image": None,
		"error": None,
	})


def _replace_image_in_page(page_name: str, block_id: str, new_src: str, img_type: str = "img"):
	"""Replace a placeholder image src in a Builder Page by blockId."""
	page = frappe.get_doc("Builder Page", page_name)

	for field in ("blocks", "draft_blocks"):
		blocks_json = page.get(field)
		if not blocks_json:
			continue

		blocks = json.loads(blocks_json)
		if _replace_block_src(blocks, block_id, new_src, img_type=img_type):
			page.set(field, json.dumps(blocks))

	page.save(ignore_permissions=True)
	frappe.db.commit()


_SCRIM = "linear-gradient(rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0.30))"
_LIGHT_TEXT = {"#fff", "#ffff", "#ffffff", "white", "rgb(255,255,255)"}


def _has_light_text(block, depth: int = 0) -> bool:
	"""Does anything inside this block rely on the background being dark?"""
	if depth > 6 or not isinstance(block, dict):
		return False
	for key in ("baseStyles", "mobileStyles", "tabletStyles"):
		colour = str((block.get(key) or {}).get("color", "")).strip().lower().replace(" ", "")
		if colour in _LIGHT_TEXT:
			return True
	return any(_has_light_text(child, depth + 1) for child in block.get("children") or [])


def _background_with_scrim(block, new_src: str) -> str:
	"""The new photo, keeping (or earning) the veil the text needs to stay readable.

	Two failures this prevents, both seen on a generated homepage:

	- Overwriting `backgroundImage` wholesale **destroyed** the gradient the AI
	  had put in front of its own placeholder. The scrim is part of the design,
	  not part of the placeholder.
	- Where the AI never wrote one, a slate placeholder hid the problem: white
	  text on a dark rectangle reads fine. Swap in a real photo with a bright
	  sky and the headline disappears.

	So: keep an existing gradient, and add a default one when the block draws
	light text over the image. A section with dark text is left alone — a veil
	there would only muddy the photo.
	"""
	previous = str((block.get("baseStyles") or {}).get("backgroundImage") or "")
	prefix = previous.split("url(")[0].strip().rstrip(",").strip()
	if "gradient(" in prefix:
		return f"{prefix}, url('{new_src}')"
	if _has_light_text(block):
		return f"{_SCRIM}, url('{new_src}')"
	return f"url('{new_src}')"


def _replace_block_src(blocks, block_id: str, new_src: str, img_type: str = "img") -> bool:
	"""Recursively find a block by blockId and replace its image source."""
	if not isinstance(blocks, list):
		return False

	for block in blocks:
		if not isinstance(block, dict):
			continue

		if block.get("blockId") == block_id:
			if img_type == "background":
				# Replace CSS background image with proper cover styles
				if "baseStyles" not in block:
					block["baseStyles"] = {}
				block["baseStyles"]["backgroundImage"] = _background_with_scrim(block, new_src)
				block["baseStyles"]["backgroundSize"] = "cover"
				block["baseStyles"]["backgroundPosition"] = "center"
				block["baseStyles"]["backgroundRepeat"] = "no-repeat"
				# Clean up background shorthand if it contained the old URL
				if "background" in block["baseStyles"] and "placehold.co" in block["baseStyles"].get("background", ""):
					del block["baseStyles"]["background"]
			else:
				# Replace <img> src attribute
				if "attributes" not in block:
					block["attributes"] = {}
				block["attributes"]["src"] = new_src
			return True

		if block.get("children"):
			if _replace_block_src(block["children"], block_id, new_src, img_type=img_type):
				return True

	return False


@frappe.whitelist()
def chat_get_session(session_id: str):
	"""Get full session data including conversation history."""
	from unpress_core.chat_service import BuilderChatService
	if not session_id:
		return {"success": False, "message": _("Session ID is required")}
	service = BuilderChatService()
	return service.get_session(session_id)
