# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

"""
Builder Chat Service
AI-guided conversational interface for collecting site generation parameters.
Uses existing builder/ai/providers and builder/api.generate_complete_site().
"""

import frappe
from frappe import _
import json
import re
from typing import Any, Dict, List, Optional


# Available themes with descriptions for suggestion buttons
THEMES = {
	"modern": "Clean, professional",
	"neobrutalist": "Bold, high contrast",
	"glassmorphism": "Frosted glass effects",
	"minimal": "Ultra-clean, simple",
	"corporate": "Professional, serious",
	"creative": "Artistic, colorful",
}

# Available site types (primary types first, secondary available via conversation)
SITE_TYPES = {
	"vitrine": "Showcase website (multi-page)",
	"one_page": "Single page website",
	"ecommerce": "Online store",
	"vitrine_user": "Showcase + user login",
	# Secondary (still available via conversation)
	"blog": "Blog / content site",
	"ecommerce_search": "Online store + search",
	"saas": "Software product",
	"portfolio": "Portfolio / showcase",
}

# Color palettes for suggestions
COLOR_PALETTES = [
	{"label": "Ocean", "primary": "#0ea5e9", "secondary": "#06b6d4"},
	{"label": "Forest", "primary": "#16a34a", "secondary": "#65a30d"},
	{"label": "Sunset", "primary": "#f97316", "secondary": "#ef4444"},
	{"label": "Royal", "primary": "#7c3aed", "secondary": "#6366f1"},
	{"label": "Rose", "primary": "#e11d48", "secondary": "#f43f5e"},
	{"label": "Midnight", "primary": "#1e293b", "secondary": "#3b82f6"},
]


def _is_neutral(hex_color: str) -> bool:
	"""Near-white, near-black or grey — not a brand colour.

	Most logos sit on a white or transparent background, so the dominant
	colour by area is almost always the background. Without this filter the
	brand colour comes out #ffffff.
	"""
	value = (hex_color or "").lstrip("#")
	if len(value) != 6:
		return True
	try:
		r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
	except ValueError:
		return True
	if max(r, g, b) > 235 or max(r, g, b) < 25:
		return True
	# low saturation = grey, whatever the lightness
	return (max(r, g, b) - min(r, g, b)) < 25

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".bmp"}

# A logo announces itself, most of the time by its filename.
LOGO_HINTS = ("logo", "logotype", "wordmark", "brandmark", "marque", "isotype")


def _is_image(filename: str) -> bool:
	import os

	return os.path.splitext(filename or "")[1].lower() in IMAGE_EXTENSIONS


def _looks_like_logo(filename: str, file_url: str) -> bool:
	"""Whether an image is the brand mark rather than a photo.

	Nobody uploads a photo as an SVG, and a logo is almost always a small
	image on transparency — a photo is neither. Cheap heuristics, and the
	conversation step decides when they are silent.
	"""
	import os

	stem = os.path.basename(filename or "").lower()
	if any(hint in stem for hint in LOGO_HINTS):
		return True
	if os.path.splitext(stem)[1] == ".svg":
		return True
	try:
		from PIL import Image

		from frappe.utils.file_manager import get_file_path

		with Image.open(get_file_path(file_url)) as image:
			transparent = image.mode in ("RGBA", "LA") or "transparency" in image.info
			widest = max(image.size)
		return transparent and widest <= 1200
	except Exception:
		return False


def _translatable_labels():
	"""Extraction markers — never called.

	The tables above are looked up by key and wrapped at the use site
	(`_(v)`), because a module-level `_()` would freeze the translation at
	import time, before the request's language is known. gettext cannot see
	through a variable, so the literals are listed here for the POT file.
	Keep in sync with THEMES / SITE_TYPES / COLOR_PALETTES.
	"""
	# themes
	_("Clean, professional")
	_("Bold, high contrast")
	_("Frosted glass effects")
	_("Ultra-clean, simple")
	_("Professional, serious")
	_("Artistic, colorful")
	_("Modern")
	_("Neobrutalist")
	_("Glassmorphism")
	_("Minimal")
	_("Corporate")
	_("Creative")
	# site types
	_("Showcase website (multi-page)")
	_("Single page website")
	_("Online store")
	_("Showcase + user login")
	_("Blog / content site")
	_("Online store + search")
	_("Software product")
	_("Portfolio / showcase")
	# colour palettes
	_("Ocean")
	_("Forest")
	_("Sunset")
	_("Royal")
	_("Rose")
	_("Midnight")


# Steps configuration
STEPS = ["description", "style", "inspiration", "pages", "page_selection", "generation"]

# Required fields per step
REQUIRED_FIELDS = {
	"description": ["site_description", "site_name", "site_type"],
	"style": ["theme", "primary_color"],
	"pages": [],  # auto-populated
}


class BuilderChatService:
	"""Service for managing AI-guided builder chat conversations."""

	def __init__(self):
		self._ai_settings = None

	def _get_ai_settings(self):
		"""Get AI settings (cached per request)."""
		if not self._ai_settings:
			from unpress_core.ai.config import get_ai_settings
			self._ai_settings = get_ai_settings()
		return self._ai_settings

	def _get_provider(self):
		"""Get configured AI provider."""
		settings = self._get_ai_settings()
		from unpress_core.ai.providers import get_provider
		return get_provider(
			settings.provider,
			model=settings.model,
			api_key=settings.api_key,
			base_url=settings.base_url,
		)

	def start_session(self, user: Optional[str] = None) -> Dict:
		"""Start a new builder chat session or resume a recent active one."""
		try:
			user = user or frappe.session.user

			# Statuses we consider "in progress" and worth reopening on reload.
			# Generating / Homepage Ready are mid-flight — the page was just
			# kicked off, so we must NOT drop the user into a fresh session.
			RESUMABLE_STATUSES = ["Active", "Generating", "Homepage Ready"]

			# Check for a resumable session (modified < 24h ago)
			recent_active = frappe.get_all(
				"Builder Chat Session",
				filters={
					"user": user,
					"status": ["in", RESUMABLE_STATUSES],
					"modified": [">", frappe.utils.add_days(frappe.utils.now(), -1)]
				},
				order_by="modified desc",
				limit=1,
				pluck="name"
			)

			if recent_active:
				# Resume existing session — include job_id + generation status
				# so the frontend can re-attach to an in-flight generation.
				session = frappe.get_doc("Builder Chat Session", recent_active[0])
				payload = {
					"success": True,
					"session_id": session.session_id,
					"is_resumed": True,
					"current_step": session.current_step,
					"completion_percentage": session.completion_percentage,
					"messages": self._format_messages(session.messages),
					"missing_fields": session.get_missing_fields(),
					"status": session.status,
					# what the user already attached, so the UI can say so again
					"logo_image": session.logo_image,
					"logo_url": self._site_logo_url(),
					"inspiration_count": len(self._parse_inspirations(session)),
					"content_count": frappe.db.count(
						"Builder Content Asset", {"session_id": session.session_id}
					),
				}
				if session.status in ("Generating", "Homepage Ready") and session.job_id:
					payload["job_id"] = session.job_id
					payload["generation_status"] = self._fetch_generation_snapshot(session.job_id)
				return payload

			# Abandon old Active sessions (> 24h). Don't touch Generating
			# ones here — the watchdog handles those separately.
			old_sessions = frappe.get_all(
				"Builder Chat Session",
				filters={"user": user, "status": "Active"},
				pluck="name"
			)
			for session_name in old_sessions:
				frappe.db.set_value("Builder Chat Session", session_name, "status", "Abandoned")
			if old_sessions:
				frappe.db.commit()

			# Create new session
			session = frappe.get_doc({
				"doctype": "Builder Chat Session",
				"user": user,
				"status": "Active",
				"current_step": "description",
			})
			session.insert(ignore_permissions=True)

			# Fetch and store company/ERPNext data
			company_data = self._get_company_data()
			if company_data:
				session.company_data = json.dumps(company_data)

			# Generate welcome message
			welcome = self._generate_welcome_message()
			session.add_message(
				role="assistant",
				content=welcome["content"],
				buttons=welcome.get("buttons")
			)
			session.save(ignore_permissions=True)

			return {
				"success": True,
				"session_id": session.session_id,
				"is_resumed": False,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"messages": self._format_messages(session.messages),
				"missing_fields": session.get_missing_fields(),
				# a fresh conversation on a site that already has a logo should
				# show it: the question "which logo is on my site" comes up here
				"logo_url": self._site_logo_url(),
			}

		except Exception as e:
			frappe.log_error("Builder Chat: Start session error", str(e))
			return {"success": False, "message": _("Failed to start chat session")}

	def _fetch_generation_snapshot(self, job_id: str) -> Dict:
		"""Return the cached generation status for a job, if any."""
		try:
			from unpress_core.generation import _get_generation_status
			return _get_generation_status(job_id)
		except Exception:
			return {}

	def _generate_welcome_message(self) -> Dict:
		"""Generate the initial welcome message."""
		first_name = self._get_user_first_name()
		greeting = _("Hello {name}!").format(name=first_name) if first_name else _("Hello!")

		from unpress_core.ai.config import get_assistant_name

		intro = _("I'm **{name}**, your website creation assistant.").format(
			name=get_assistant_name()
		)
		guide = _("I'll guide you step by step to generate a complete website. Let's start!")
		question = _("**What type of website do you want to create?** Briefly describe your business or project, and I'll take care of the rest.")

		content = f"{greeting} {intro}\n\n{guide}\n\n{question}"

		buttons = [
			{"label": _("Showcase site"), "value": _("I want a multi-page showcase website")},
			{"label": _("Single page site"), "value": _("I want a single page website")},
			{"label": _("Online store"), "value": _("I want an online store to sell products")},
			{"label": _("Site with login"), "value": _("I want a showcase site with user login")},
		]

		return {"content": content, "buttons": buttons}


	# The blog lives behind a plugin, and asking for an article on a site with
	# no blog should not silently create one.
	ARTICLE_REQUEST = re.compile(
		r"^\s*(?:"
		# "je voudrais / j'aimerais (que tu) écrire un article", and friends
		r"(?:j[e'\u2019]\s*)?(?:voudrais|veux|aimerais|souhaite)\s+(?:bien\s+)?"
		r"(?:qu(?:e|[\'\u2019])?\s*(?:tu|vous|on)\s+)?(?:écri\w*|ecri\w*|rédige\w*|redige\w*|publie\w*)"
		# or the imperative, which is how most people actually ask
		r"|(?:écris|ecris|rédige|redige|publie|poste)"
		r"|(?:write|draft|publish|post)"
		r")"
		r"[^\n]*?"
		r"\b(?:article|billet|post|blog)\b"
		r"\s*(?:sur|à\s+propos\s+d[eu\'\u2019]?|about|on|:)?\s*(?P<topic>.*)$",
		re.IGNORECASE | re.DOTALL,
	)

	def _article_request(self, message: str):
		"""The topic, if this message is asking for an article. None otherwise.

		Returns "" — not None — when someone asks for an article without saying
		what about, so the caller knows to ask rather than to ignore.
		"""
		if not message or message.startswith("__"):
			return None
		try:
			from unpress_core.plugins import is_enabled

			if not is_enabled("blog"):
				return None
		except ImportError:
			return None

		match = self.ARTICLE_REQUEST.match(message.strip())
		if not match:
			return None

		# On a bench with no site yet, the wizard's opening question is "what
		# site do you want" — and "I'd like to publish articles about X" is a
		# perfectly good answer to it. The article path only makes sense once
		# there is a site to publish on.
		if not frappe.db.count("Builder Page", {"published": 1}):
			return None

		return (match.group("topic") or "").strip(" .:—-")

	def _write_article(self, session, topic: str) -> Dict:
		"""Write it, keep it as a draft, and say where it went."""
		session.add_message(role="user", content=topic or _("Write an article"))

		if not topic:
			response = _("What should it be about? A subject, an angle, anything you would tell a writer.")
			session.add_message(role="assistant", content=response)
			session.db_set("homepage_feedback", "__AWAITING_ARTICLE_TOPIC__", update_modified=False)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
			}

		try:
			from unpress_core.blog_api import write_article

			article = write_article(topic=topic)
		except Exception as e:
			frappe.log_error("Chat article generation failed", f"{topic}\n{e}")
			response = _("I could not write that one: {0}").format(str(e)[:200])
			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
			}

		# A draft on purpose. Publishing is one click in Articles, and an
		# article nobody has read should not appear on the site because a
		# generation finished.
		response = _("**{0}** is written and waiting as a draft in Articles.").format(article["title"])
		response += "\n\n" + _("Read it before it goes live — I write from your brief, but you know the business.")
		buttons = [
			{"label": _("Write another"), "value": "__WRITE_ARTICLE__"},
			{"label": _("Publish it"), "value": "__PUBLISH_LAST_ARTICLE__:" + article["name"]},
		]
		session.add_message(role="assistant", content=response, buttons=buttons)
		session.save(ignore_permissions=True)
		return {
			"success": True,
			"response": response,
			"buttons": buttons,
			"current_step": session.current_step,
			"completion_percentage": session.completion_percentage,
		}

	def process_message(self, session_id: str, user_message: str) -> Dict:
		"""Process a user message and generate AI response."""
		try:
			session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})

			# Handle special commands
			if user_message.startswith("__"):
				return self._handle_special_command(session, user_message)

			# The AI sometimes emits its own button values (e.g. "generate_site",
			# "ajouter un CTA") instead of our canonical __TOKENS__. Route the
			# obvious generation triggers to trigger_generation so the UI starts
			# polling — otherwise it just looks like a dead button.
			if user_message.strip().lower() in {
				"generate_site",
				"generate site",
				"generate_all",
				"generate all",
				"générer le site",
				"générer le site maintenant",
				"générer tout le site",
				"tout générer",
			}:
				session.generation_mode = session.generation_mode or "full"
				session.add_message(role="user", content=_("Generate entire site"))
				session.save(ignore_permissions=True)
				return self.trigger_generation(session.session_id)

			if user_message.strip().lower() in {
				"homepage_first",
				"homepage first",
				"la page d'accueil d'abord",
				"page d'accueil d'abord",
			}:
				session.generation_mode = "progressive"
				session.add_message(role="user", content=_("Homepage first"))
				session.save(ignore_permissions=True)
				return self.trigger_generation(session.session_id)

			# Replace-confirmation buttons (asked when existing pages were
			# designed/edited by hand — see classify_existing_pages)
			if user_message.strip() in {"__FORCE_REGENERATE__", _("Yes, replace everything")}:
				session.add_message(role="user", content=_("Yes, replace everything"))
				session.save(ignore_permissions=True)
				return self.trigger_generation(session.session_id, force_replace=True)
			if user_message.strip() in {"__CANCEL_REGENERATE__", _("No, keep my pages")}:
				session.add_message(role="user", content=_("No, keep my pages"))
				response = _(
					"Understood — I kept all your existing pages. "
					"You can adjust your project and generate again whenever you want."
				)
				session.add_message(role="assistant", content=response)
				session.status = "Active"
				session.save(ignore_permissions=True)
				return {"success": True, "message": response, "completion_percentage": session.completion_percentage}

			# Writing an article. Two ways in: the button offered once the site
			# exists, and asking for one in plain words. Both land here.
			if session.homepage_feedback == "__AWAITING_ARTICLE_TOPIC__":
				session.db_set("homepage_feedback", "", update_modified=False)
				return self._write_article(session, user_message.strip())

			topic = self._article_request(user_message)
			if topic is not None:
				return self._write_article(session, topic)

			# Handle custom page name input
			if session.homepage_feedback == "__AWAITING_CUSTOM_PAGE_NAME__":
				session.db_set("homepage_feedback", "", update_modified=False)
				session.add_message(role="user", content=user_message)
				self._add_custom_page(session, user_message.strip())
				response = _("Page **{title}** added!").format(title=user_message.strip())
				response += "\n\n" + _("Want to add more pages?")
				buttons = self._get_page_selection_buttons(session)
				session.add_message(role="assistant", content=response, buttons=buttons)
				session.save(ignore_permissions=True)
				return {
					"success": True,
					"response": response,
					"buttons": buttons,
					"current_step": session.current_step,
					"completion_percentage": session.completion_percentage,
					"missing_fields": session.get_missing_fields(),
				}

			# Handle homepage feedback (progressive generation)
			if session.current_step == "feedback":
				session.add_message(role="user", content=user_message)
				# Check if user is satisfied
				satisfied_signals = ["ok", "c'est bon", "parfait", "ça me va", "bien", "super", "genial", "génial", "good", "great", "nice"]
				if user_message.lower().strip().rstrip("!.") in satisfied_signals:
					return self._handle_special_command(session, "__HOMEPAGE_SATISFIED__")

				# Otherwise, treat as revision feedback
				response = _("Regenerating the homepage with your feedback...")
				session.add_message(role="assistant", content=response)
				session.save(ignore_permissions=True)

				from unpress_core.generation import regenerate_homepage
				result = regenerate_homepage(
					session_id=session.session_id,
					feedback=user_message,
				)
				if result and result.get("job_id"):
					session.job_id = result["job_id"]
					session.generation_status = "regenerating"
					session.save(ignore_permissions=True)
				return {
					"success": True,
					"response": response,
					"job_id": result.get("job_id") if result else None,
					"status": "queued",
					"current_step": session.current_step,
					"completion_percentage": session.completion_percentage,
					"missing_fields": session.get_missing_fields(),
				}

			# Add user message
			session.add_message(role="user", content=user_message)

			# Try to extract data from message (regex-based)
			extracted = self._extract_data_regex(user_message, session)

			# Handle company data confirmation
			company_confirm = extracted.pop("_company_confirm", None)
			if company_confirm == "keep" and session.company_data:
				self._apply_company_data(session)

			# Build context and call AI
			context = self._build_ai_context(session)
			ai_response = self._call_ai(context, user_message, session)

			# Parse AI response for extracted data and buttons
			parsed = self._parse_ai_response(ai_response)

			# Merge AI-extracted data
			ai_extracted = parsed.get("extracted_data", {})
			if ai_extracted:
				extracted.update(ai_extracted)

			# Process inspiration URLs if found
			if extracted.get("inspiration_urls"):
				self._process_inspiration_urls(session, extracted.pop("inspiration_urls"))

			# Update session with extracted data
			if extracted:
				session.update_extracted_data(extracted)

			response_content = parsed.get("content", ai_response)

			# Check if we should present Company data after site_type selection
			company_presentation = self._maybe_present_company_data(
				session, extracted, response_content
			)
			if company_presentation:
				response_content = company_presentation["content"]
				parsed["buttons"] = company_presentation.get("buttons")

			# Check step transition BEFORE computing buttons
			prev_step = session.current_step
			self._check_step_transition(session)

			# If we just entered inspiration step, override response with inspiration question
			if session.current_step == "inspiration" and prev_step != "inspiration":
				response_content = response_content.rstrip() + "\n\n" + _("**Do you have any websites you admire or reference images for the design?** This is optional but helps refine the visual style.")
				response_content += "\n\n" + _("You can also drop the client's own content — photos, documents, the current site — and I'll sort it and reuse it on the site.")
				parsed["buttons"] = [
					{"label": _("Import client content (photos, docs)"), "value": "__UPLOAD_CONTENT__"},
					{"label": _("I have inspiration sites"), "value": _("I'd like to share websites I like for inspiration")},
					{"label": _("Upload reference images"), "value": "__UPLOAD_INSPIRATION__"},
					{"label": _("No, let's continue"), "value": "__SKIP_INSPIRATION__"},
				]

			# If we just entered page_selection, override with selection UI
			if session.current_step == "page_selection" and prev_step != "page_selection":
				recap = self._get_pages_recap(session)
				selection_msg = _("Would you like to add optional pages to your site?")
				response_content = recap + "\n\n" + selection_msg
				parsed["buttons"] = self._get_page_selection_buttons(session)

			# Ensure buttons are always present — fallback if AI didn't provide any
			if not parsed.get("buttons"):
				parsed["buttons"] = self._get_fallback_buttons(session)

			# Add assistant message
			session.add_message(
				role="assistant",
				content=response_content,
				buttons=parsed.get("buttons"),
				extracted_data=extracted if extracted else None
			)

			session.save(ignore_permissions=True)

			return {
				"success": True,
				"session_id": session.session_id,
				"response": response_content,
				"buttons": parsed.get("buttons"),
				"extracted_data": extracted,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
				"is_ready": len(session.get_missing_fields()) == 0 and session.site_description,
			}

		except Exception as e:
			frappe.log_error("Builder Chat: Process message error", str(e))
			return {
				"success": False,
				"message": _("Failed to process message: {0}").format(str(e))
			}

	@staticmethod
	def _colors_from_logo(file_url: str) -> tuple:
		"""(primary, secondary) read off the logo, or (None, None).

		A client's brand lives in their logo. Asking them to name a palette
		when they just handed us the answer is busy-work — and the model
		writes better copy when the site already looks like the brand.
		Pure inference: the caller decides whether to overwrite anything.
		"""
		from frappe.utils.file_manager import get_file_path

		from unpress_core.ai.inspiration.analyzer import DesignAnalyzer

		path = get_file_path(file_url)
		colors = DesignAnalyzer().extract_dominant_colors(path, n_colors=5)
		# skip near-white / near-black: a logo on a white background would
		# otherwise hand us #ffffff as the brand colour
		vivid = [
			c for c in colors
			if c.get("hex") and not _is_neutral(c["hex"])
		]
		if not vivid:
			return None, None
		primary = vivid[0]["hex"]
		secondary = vivid[1]["hex"] if len(vivid) > 1 else None
		return primary, secondary

	def _accept_logo(self, session, file_url: str) -> str:
		"""Take a logo into the session AND onto the site. Returns what to say.

		A logo handed to the assistant is the site's logo — leaving it inside
		the conversation would mean the client uploads their brand and their
		header keeps showing someone else's.
		"""
		session.logo_image = file_url
		message = _("Logo received! I'll use it for your site generation.")

		# Push it to the site chrome, on the stable path. Never fatal: a chat
		# that refuses a logo because the header could not be written is worse
		# than a header that stays behind for a moment.
		try:
			from unpress_core import branding

			branding.apply_logo(file_url)
			message += " " + _("It is now your site logo.")
		except Exception as e:
			from unpress_core.ai.logging import ai_log

			ai_log("warning", "logo not applied to site chrome", error=str(e)[:200])

		# Read the brand colours off the logo — but never overwrite a choice
		# the user already made in the conversation.
		try:
			primary, secondary = self._colors_from_logo(file_url)
			picked = []
			if primary and not session.primary_color:
				session.primary_color = primary
				picked.append(primary)
			if secondary and not session.secondary_color:
				session.secondary_color = secondary
				picked.append(secondary)
			if picked:
				message += " " + _("I read these colours off it: {0}.").format(", ".join(picked))
		except Exception as e:
			# a logo we cannot read is not a reason to reject the logo
			from unpress_core.ai.logging import ai_log

			ai_log("warning", "logo colour extraction failed", error=str(e)[:200])

		return message

	def upload_logo(self, session_id: str, file_url: str) -> Dict:
		"""Handle logo upload."""
		try:
			session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
			session.add_message(role="user", content=_("(Logo uploaded)"))

			logo_msg = self._accept_logo(session, file_url)
			next_q = self._get_next_question(session)
			response = f"{logo_msg}\n\n{next_q}"

			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)

			return {
				"success": True,
				"response": response,
				"logo_url": self._site_logo_url(),
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		except Exception as e:
			frappe.log_error("Builder Chat: Upload logo error", str(e))
			return {"success": False, "message": _("Failed to process logo")}

	@staticmethod
	def _site_logo_url() -> str:
		"""The logo as the site renders it, for the composer preview."""
		try:
			from unpress_core import branding

			return branding.logo_url() if branding.logo_version() else ""
		except Exception:
			return ""

	@staticmethod
	def _parse_inspirations(session) -> list:
		"""The references attached so far — never raises on malformed JSON."""
		if not session.inspiration_urls:
			return []
		try:
			parsed = json.loads(session.inspiration_urls)
		except (json.JSONDecodeError, TypeError):
			return []
		return parsed if isinstance(parsed, list) else []

	def _accept_inspiration(self, session, file_url: str) -> str:
		"""Capture a design reference into the session. Returns what to say."""
		from unpress_core.generation import capture_inspiration

		result = capture_inspiration(image=file_url, sentiment="like")
		existing = self._parse_inspirations(session)

		if result and result.get("name"):
			existing.append({"url": file_url, "name": result["name"], "type": "image"})
			session.inspiration_urls = json.dumps(existing)

		return _("Reference image received! I'll use it as design inspiration for your site.")

	def _accept_content(self, session, files: List[Dict]) -> int:
		"""Hand photos and documents to the understanding pass. Returns the count."""
		from unpress_core.ai.ingestion.content_understanding import ingest_content_assets

		result = ingest_content_assets(session.session_id, files) or {}
		return result.get("created", len(files))

	def upload_inspiration(self, session_id: str, file_url: str) -> Dict:
		"""Handle inspiration image upload."""
		try:
			session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
			session.add_message(role="user", content=_("(Reference image uploaded)"))

			inspo_msg = self._accept_inspiration(session, file_url)

			# Advance from inspiration to page_selection
			if session.current_step == "inspiration":
				self._auto_populate_pages(session)
				session.current_step = "page_selection"
				recap = self._get_pages_recap(session)
				selection_msg = _("Would you like to add optional pages to your site?")
				response = f"{inspo_msg}\n\n{recap}\n\n{selection_msg}"
				buttons = self._get_page_selection_buttons(session)
			else:
				next_q = self._get_next_question(session)
				response = f"{inspo_msg}\n\n{next_q}"
				buttons = self._get_fallback_buttons(session)

			session.add_message(role="assistant", content=response, buttons=buttons)
			session.save(ignore_permissions=True)

			return {
				"success": True,
				"response": response,
				"buttons": buttons,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		except Exception as e:
			frappe.log_error("Builder Chat: Upload inspiration error", str(e))
			return {"success": False, "message": _("Failed to process reference image")}

	def attach_files(self, session_id: str, files) -> Dict:
		"""One door for everything the client hands over.

		A client does not think "this one is a logo upload, that one is a
		content upload" — they drop what they have. Sorting it is our job:
		the filename and the pixels answer for the logo, and the question
		currently on screen answers for the rest.
		"""
		try:
			if isinstance(files, str):
				files = frappe.parse_json(files)
			files = [f for f in (files or []) if (f or {}).get("file_url")]
			if not files:
				return {"success": False, "message": _("No file was received.")}

			session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
			step = session.current_step

			logo_url = None
			references: List[str] = []
			content: List[Dict] = []

			for entry in files:
				url = entry["file_url"]
				name = entry.get("filename") or url
				if not _is_image(name):
					content.append({"file_url": url, "filename": name})
					continue
				# only one logo, and only while the site has none
				if not session.logo_image and not logo_url and (
					step == "logo" or _looks_like_logo(name, url)
				):
					logo_url = url
				elif step == "inspiration":
					references.append(url)
				else:
					content.append({"file_url": url, "filename": name})

			session.add_message(
				role="user", content=_("({0} file(s) attached)").format(len(files))
			)

			parts = []
			if logo_url:
				parts.append(self._accept_logo(session, logo_url))
			for url in references:
				parts.append(self._accept_inspiration(session, url))
			created = 0
			if content:
				created = self._accept_content(session, content)
				if created:
					parts.append(
						_("{0} file(s) received — I am reading them, I will tell you what I found.").format(created)
					)

			# the reference step is a checkpoint: once we have one, move on
			if references and step == "inspiration":
				self._auto_populate_pages(session)
				session.current_step = "page_selection"
				parts.append(self._get_pages_recap(session))
				parts.append(_("Would you like to add optional pages to your site?"))
				buttons = self._get_page_selection_buttons(session)
			else:
				parts.append(self._get_next_question(session))
				buttons = self._get_fallback_buttons(session)

			response = "\n\n".join(p for p in parts if p)
			session.add_message(role="assistant", content=response, buttons=buttons)
			session.save(ignore_permissions=True)

			return {
				"success": True,
				"response": response,
				"buttons": buttons,
				"logo_url": self._site_logo_url(),
				"logo_taken": bool(logo_url),
				"references_added": len(references),
				"content_added": created,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		except Exception as e:
			frappe.log_error("Builder Chat: Attach files error", frappe.get_traceback())
			return {"success": False, "message": _("Failed to process the files: {0}").format(str(e))}

	def trigger_generation(self, session_id: str, force_replace: bool = False) -> Dict:
		"""Trigger site generation with collected parameters.

		force_replace=True confirms replacing pages a user designed/edited
		(asked via the replace-confirmation buttons in process_message)."""
		try:
			session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})

			# Validate readiness
			is_ready, missing = session.is_ready_for_generation()
			if not is_ready:
				missing_labels = [f["label"] for f in missing]
				return {
					"success": False,
					"message": _("Missing required fields: {0}").format(", ".join(missing_labels))
				}

			# Update session status
			session.status = "Generating"
			session.current_step = "generation"

			# Call the existing generate_complete_site API
			from unpress_core.generation import generate_complete_site

			# Enrich prompt with inspiration data if available
			generation_prompt = session.site_description
			if session.inspiration_urls:
				try:
					inspirations = json.loads(session.inspiration_urls)
					inspiration_names = [item.get("name") for item in inspirations if item.get("name")]
					if inspiration_names:
						from unpress_core.generation import analyze_inspirations_for_generation
						analysis = analyze_inspirations_for_generation(
							inspiration_names=json.dumps(inspiration_names)
						)
						if analysis and isinstance(analysis, dict):
							# Append style hints from inspiration analysis
							style_hints = []
							if analysis.get("dominant_colors"):
								colors = [c.get("hex", "") for c in analysis["dominant_colors"][:3]]
								style_hints.append(f"Inspiration colors: {', '.join(colors)}")
							if analysis.get("style_keywords"):
								style_hints.append(f"Style: {', '.join(analysis['style_keywords'][:5])}")
							if style_hints:
								generation_prompt += "\n\n" + "\n".join(style_hints)
				except Exception as e:
					frappe.log_error("Builder Chat: Inspiration analysis error", str(e))

			# Parse social_links if present
			social_links_str = None
			if session.social_links:
				social_links_str = session.social_links if isinstance(session.social_links, str) else json.dumps(session.social_links)

			# multi-site hosts: carry the session's target Website Profile into generation
			website_profile = getattr(session, "website_profile", None)

			result = generate_complete_site(
				prompt=generation_prompt,
				site_name=session.site_name,
				site_type=session.site_type or "vitrine",
				theme=session.theme or "modern",
				primary_color=session.primary_color,
				secondary_color=session.secondary_color,
				logo_text=session.logo_text or session.site_name,
				logo_image=session.logo_image,
				cta_text=session.cta_text or "Contact",
				cta_url=session.cta_url or "/contact",
				social_links=social_links_str,
				session_id=session_id,
				heading_font=session.heading_font,
				body_font=session.body_font,
				pages_config=session.pages_config if session.pages_config else None,
				generation_mode=session.generation_mode or "full",
				replace_existing="force" if force_replace else "auto",
				website_profile=website_profile,  # multi-site
			)

			# Existing pages were designed/edited by hand: ask before wiping
			if result and result.get("status") == "confirmation_required":
				protected = result.get("protected_pages") or []
				titles = ", ".join(p.get("title") or p.get("name") for p in protected[:8])
				if len(protected) > 8:
					titles += ", …"
				question = _(
					"⚠️ Your site has {0} page(s) that were designed or edited by hand: {1}.\n\n"
					"Generating the new site will REPLACE all current pages. Do you want to continue?"
				).format(len(protected), titles)
				session.status = "Active"
				session.add_message(
					role="assistant",
					content=question,
					buttons=[
						{"label": _("Yes, replace everything"), "value": "__FORCE_REGENERATE__"},
						{"label": _("No, keep my pages"), "value": "__CANCEL_REGENERATE__"},
					],
				)
				session.save(ignore_permissions=True)
				return {
					"success": True,
					"status": "confirmation_required",
					"message": question,
					"buttons": [
						{"label": _("Yes, replace everything"), "value": "__FORCE_REGENERATE__"},
						{"label": _("No, keep my pages"), "value": "__CANCEL_REGENERATE__"},
					],
					"completion_percentage": session.completion_percentage,
				}

			if result and result.get("job_id"):
				session.job_id = result["job_id"]
				session.generation_status = "queued"
				session.save(ignore_permissions=True)

				return {
					"success": True,
					"job_id": result["job_id"],
					"status": "queued",
					"completion_percentage": session.completion_percentage,
				}
			else:
				session.status = "Failed"
				session.save(ignore_permissions=True)
				return {"success": False, "message": _("Failed to start generation")}

		except Exception as e:
			frappe.log_error("Builder Chat: Trigger generation error", str(e))
			return {"success": False, "message": _("Failed to trigger generation: {0}").format(str(e))}

	def get_session(self, session_id: str) -> Dict:
		"""Get full session data."""
		try:
			session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
			return {
				"success": True,
				"session_id": session.session_id,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"messages": self._format_messages(session.messages),
				"missing_fields": session.get_missing_fields(),
				"is_ready": len(session.get_missing_fields()) == 0 and session.site_description,
			}
		except frappe.DoesNotExistError:
			return {"success": False, "message": _("Session not found")}
		except Exception as e:
			frappe.log_error("Builder Chat: Get session error", str(e))
			return {"success": False, "message": _("Failed to get session")}

	# =========================================================================
	# AI INTERACTION
	# =========================================================================

	def _build_ai_context(self, session) -> str:
		"""Build the system prompt for the AI."""
		# Gather current session state
		collected = {}
		for field in ["site_description", "site_name", "site_type", "theme",
					   "primary_color", "secondary_color", "heading_font",
					   "body_font", "logo_text", "logo_image",
					   "cta_text", "cta_url"]:
			val = session.get(field)
			if val:
				collected[field] = val

		missing = session.get_missing_fields()
		missing_str = ", ".join([f["label"] for f in missing]) if missing else "None"

		themes_str = "\n".join([f"- {k}: {v}" for k, v in THEMES.items()])
		site_types_str = "\n".join([f"- {k}: {v}" for k, v in SITE_TYPES.items()])
		palettes_str = "\n".join([f"- {p['label']}: {p['primary']} / {p['secondary']}" for p in COLOR_PALETTES])

		# Inspiration context
		inspiration_str = ""
		if session.inspiration_urls:
			try:
				inspirations = json.loads(session.inspiration_urls)
				if inspirations:
					urls_list = [item.get("url", "") for item in inspirations]
					inspiration_str = "\n".join([f"- {u}" for u in urls_list])
			except (json.JSONDecodeError, TypeError):
				pass

		inspiration_block = ""
		if inspiration_str:
			inspiration_block = f"""
INSPIRATION:
- Users can share website URLs as design inspiration
- When a URL is shared, acknowledge it as a reference for style/colors
- These sites won't be copied, they serve as style references
- Current inspirations:
{inspiration_str}
"""

		# Build company data context block
		company_block = ""
		if session.company_data:
			try:
				cd = json.loads(session.company_data)
				items = []
				if cd.get("company_name"):
					items.append(f"Company: {cd['company_name']}")
				if cd.get("phone"):
					items.append(f"Phone: {cd['phone']}")
				if cd.get("email"):
					items.append(f"Email: {cd['email']}")
				if cd.get("logo"):
					items.append(f"Logo: available ({cd['logo']})")
				if cd.get("website"):
					items.append(f"Website: {cd['website']}")
				if cd.get("description"):
					items.append(f"Description: {cd['description'][:100]}")
				if items:
					company_block = "\nCOMPANY DATA (pre-filled from system):\n" + "\n".join(f"- {i}" for i in items) + "\n- Use this data as defaults. Don't re-ask what we already know.\n- If company data was confirmed by the user, use company_name as site_name.\n"
			except Exception as e:
				frappe.log_error("Builder Chat: company data lookup failed", str(e))

		from unpress_core.ai.config import get_assistant_name

		system_prompt = f"""You are {get_assistant_name()}, an assistant that guides users to create a website.
Your goal is to collect the required parameters through a natural conversation.

CURRENT STATE:
- Step: {session.current_step}
- Collected data: {json.dumps(collected, ensure_ascii=False)}
- Missing fields: {missing_str}
{company_block}
REQUIRED FIELDS (collect in order):
1. DESCRIPTION STEP: site_description (what the site is about), site_name (business/project name), site_type (type of site)
2. STYLE STEP: theme (visual theme), primary_color (hex color). Do NOT ask about secondary_color — it will be auto-generated.
3. INSPIRATION STEP: handled by the system — just acknowledge the user's previous input and confirm the style.
4. PAGES STEP: auto-populated based on site_type. Can also ask about CTA text/url and social links.

AVAILABLE OPTIONS:
Themes: {themes_str}
Site types: {site_types_str}
Color palettes: {palettes_str}
{inspiration_block}
CONVERSATION FLOW (CRITICAL):
- ALWAYS end your response with a question or a choice for the user
- Never leave the user without a next action
- After collecting data, immediately ask about the next missing field
- Pattern: acknowledge what was said → confirm what was extracted → ask next question
- When offering choices, use suggestion buttons

CONTENT REWRITING:
- When the user provides a text for their site (description, about text, tagline), acknowledge it and propose an improved version
- Say: "Here's a polished version: [improved text]. Does that work for you?"
- Keep the original meaning, improve clarity and marketing appeal
- If confirmed, use the rewritten version as site_description

LOGO INTELLIGENCE:
- If company data includes a logo, propose: "I found your existing logo. Shall we use it, or would you prefer to upload a new one?"
- Don't ask for a logo upload by default if one already exists

DESIGN INSPIRATION:
- The inspiration step is handled automatically by the system after the style step — do NOT ask about inspiration yourself.
- If the current step is "inspiration", simply acknowledge what the user said (confirm style choices) and end with a brief positive note.
- If the user shares URLs at any point, acknowledge them positively as style references.
- Do NOT include inspiration buttons — they are injected by the system.

RULES:
- Ask ONE question at a time
- Be concise and friendly
- When the user describes their business, extract site_description, site_name, and suggest a site_type
- When a field is collected, move to the next missing field
- Use markdown for formatting (bold for important words)
- Respond in the SAME LANGUAGE as the user's message
- Users can share website URLs as design inspiration at any time — acknowledge them positively

DATA EXTRACTION:
When you identify data from the user's message, include it in your response using this format:
<extracted_data>{{"field_name": "value", ...}}</extracted_data>

For example, if the user says "I have a bakery called Sweet Dreams":
<extracted_data>{{"site_description": "A bakery called Sweet Dreams", "site_name": "Sweet Dreams", "site_type": "vitrine"}}</extracted_data>

SUGGESTION BUTTONS (MANDATORY):
You MUST include <buttons> in EVERY response. Always provide at least 2-3 clickable options.
Format: <buttons>[{{"label": "Option 1", "value": "value1"}}, ...]</buttons>

Examples by context:
- Asking about description: offer business type buttons (consulting, store, portfolio, etc.)
- Asking about theme: offer theme name buttons
- Asking about color: offer palette name buttons
- After description rewriting: offer "Yes, perfect" / "Modify" / "Start over" buttons
- After all fields collected: offer "Generate site" / "Add CTA" / "Add social links"

When asking about themes, offer theme buttons.
When asking about colors, offer palette buttons.
When all required fields are collected, congratulate the user and tell them they can click "Generate Site"."""

		return system_prompt

	def _call_ai(self, system_prompt: str, user_message: str, session) -> str:
		"""Call the AI provider with conversation history.

		Uses the provider's internal HTTP methods to support multi-turn conversation.
		The base provider only has generate(prompt, system_prompt) which formats
		a single user message, so we call the HTTP layer directly for multi-turn.
		"""
		try:
			provider = self._get_provider()

			# Build messages list for multi-turn conversation
			messages = [{"role": "system", "content": system_prompt}]

			# Add conversation history (last 20 messages max)
			history = session.get_conversation_history(include_system=False)
			messages.extend(history[-20:])

			# Ensure the current user message is included
			if not history or history[-1].get("content") != user_message:
				messages.append({"role": "user", "content": user_message})

			# Use provider's HTTP method directly for multi-turn support
			if hasattr(provider, '_generate_with_http'):
				# Ollama provider - use HTTP streaming
				response = provider._generate_with_http(
					messages=messages,
					temperature=0.7,
					max_tokens=16384,
				)
			elif hasattr(provider, '_make_streaming_request'):
				# Fallback: build payload manually
				payload = {
					"model": provider.model,
					"messages": messages,
					"stream": True,
					"options": {
						"temperature": 0.7,
						"num_predict": 1024,
						"num_ctx": getattr(provider, 'num_ctx', 32768),
					},
				}
				response = provider._make_streaming_request("/api/chat", payload)
			else:
				# Final fallback for OpenAI-compatible providers (Moonshot/Kimi).
				# Kimi-k2.5 thinks before every reply regardless of the `think`
				# flag (Moonshot ignores it), so we give it 16k tokens so it
				# has room to both reason AND produce a final answer. Without
				# enough budget, `content` comes back empty and the provider
				# raises (see openai_provider.generate). Chat takes ~60-120s
				# per reply at this budget — acceptable given no alternative
				# until a non-thinking chat_model config is added.
				context = "\n".join([
					f"[{m['role']}]: {m['content']}"
					for m in messages[1:]  # Skip system
				])
				generate_kwargs = dict(
					prompt=context,
					system_prompt=system_prompt,
					temperature=0.7,
					max_tokens=16384,
				)
				try:
					import inspect
					if "think" in inspect.signature(provider.generate).parameters:
						generate_kwargs["think"] = False
				except (TypeError, ValueError):
					pass
				response = provider.generate(**generate_kwargs)

			if isinstance(response, str):
				return response
			elif isinstance(response, dict):
				return response.get("content", response.get("message", str(response)))
			else:
				return str(response)

		except Exception as e:
			frappe.log_error("Builder Chat: AI call error", str(e))
			# Fallback: generate a simple response based on missing fields
			return self._generate_fallback_response(session)

	def _generate_fallback_response(self, session) -> str:
		"""Generate a response without AI (fallback)."""
		missing = session.get_missing_fields()
		if not missing:
			return _("All required information has been collected! You can now click **Generate Site** to create your website.")

		next_field = missing[0]
		field = next_field.get("field", "")
		label = next_field.get("label", "")

		prompts = {
			"site_description": _("Could you describe your website project? What is your business or activity about?"),
			"site_name": _("What is the name of your business or project?"),
			"site_type": _("What type of site would you like?"),
			"theme": _("Which visual theme do you prefer for your site?"),
			"primary_color": _("What main color would you like for your site?"),
		}

		question = prompts.get(field, _("Could you provide: **{0}**?").format(label))

		# Add buttons for specific fields
		buttons_str = ""
		# Labels are translated HERE, not in the module-level tables: calling _()
		# at import time would freeze the translation before the user's language
		# is known. The button `value` stays the untranslated canonical key.
		if field == "site_type":
			btns = [{"label": _(v), "value": k} for k, v in SITE_TYPES.items()]
			buttons_str = f"\n\n<buttons>{json.dumps(btns)}</buttons>"
		elif field == "theme":
			btns = [
				{"label": "{0} ({1})".format(_(k.title() if k.islower() else k), _(v)), "value": k}
				for k, v in THEMES.items()
			]
			buttons_str = f"\n\n<buttons>{json.dumps(btns)}</buttons>"
		elif field == "primary_color":
			btns = [{"label": _(p["label"]), "value": p["primary"]} for p in COLOR_PALETTES]
			buttons_str = f"\n\n<buttons>{json.dumps(btns)}</buttons>"

		return question + buttons_str

	def _get_fallback_buttons(self, session) -> list:
		"""Generate contextual suggestion buttons based on next missing field."""
		# Inspiration step: offer inspiration buttons
		if session.current_step == "inspiration":
			return [
				{"label": _("I have inspiration sites"), "value": _("I'd like to share websites I like for inspiration")},
				{"label": _("Upload reference images"), "value": "__UPLOAD_INSPIRATION__"},
				{"label": _("No, let's continue"), "value": "__SKIP_INSPIRATION__"},
			]

		# Page selection step: propose optional pages
		if session.current_step == "page_selection":
			return self._get_page_selection_buttons(session)

		missing = session.get_missing_fields()
		if not missing:
			# All fields collected — propose generation mode
			buttons = [
				{"label": _("Generate entire site"), "value": "__GEN_MODE_FULL__"},
				{"label": _("Homepage first"), "value": "__GEN_MODE_PROGRESSIVE__"},
			]
			if not session.cta_text:
				buttons.append({"label": _("Add a CTA"), "value": _("I'd like to add a call-to-action button")})
			if not session.social_links:
				buttons.append({"label": _("Add social links"), "value": _("I'd like to add social media links")})
			if not session.inspiration_urls:
				buttons.append({"label": _("Share inspiration"), "value": _("I'd like to share websites or images for inspiration")})
			return buttons

		next_field = missing[0].get("field", "")

		# Same rule as _generate_fallback_response: translate the label at the
		# use site, keep the canonical key as the button value.
		if next_field == "site_type":
			return [{"label": _(v), "value": k} for k, v in SITE_TYPES.items()]
		elif next_field == "theme":
			return [
				{"label": "{0} ({1})".format(_(k.title() if k.islower() else k), _(v)), "value": k}
				for k, v in THEMES.items()
			]
		elif next_field == "primary_color":
			return [{"label": _(p["label"]), "value": p["primary"]} for p in COLOR_PALETTES]
		elif next_field == "site_description":
			# Contextual suggestions based on company data
			buttons = []
			if session.company_data:
				try:
					cd = json.loads(session.company_data)
					if cd.get("description"):
						buttons.append({"label": _("Use existing description"), "value": cd["description"]})
				except Exception as e:
					frappe.logger("builder").debug(f"Chat: JSON parse fallback: {e}")
			buttons.extend([
				{"label": _("Consulting / Services"), "value": _("We are a consulting and services company")},
				{"label": _("Online store"), "value": _("We sell products online")},
				{"label": _("Portfolio / Creative"), "value": _("I want to showcase my creative work")},
			])
			return buttons
		elif next_field == "site_name":
			buttons = []
			if session.company_data:
				try:
					cd = json.loads(session.company_data)
					if cd.get("company_name"):
						buttons.append({"label": cd["company_name"], "value": cd["company_name"]})
				except Exception as e:
					frappe.logger("builder").debug(f"Chat: JSON parse fallback: {e}")
			buttons.append({"label": _("I'll type it"), "value": _("Let me type my site name")})
			return buttons

		return []

	# =========================================================================
	# RESPONSE PARSING
	# =========================================================================

	def _parse_ai_response(self, response: str) -> Dict:
		"""Parse AI response to extract data and buttons."""
		result = {
			"content": response,
			"extracted_data": {},
			"buttons": None,
		}

		# Extract <extracted_data>...</extracted_data>
		data_match = re.search(r"<extracted_data>(.*?)</extracted_data>", response, re.DOTALL)
		if data_match:
			try:
				result["extracted_data"] = json.loads(data_match.group(1))
			except json.JSONDecodeError:
				pass
			# Remove tag from content
			result["content"] = re.sub(r"<extracted_data>.*?</extracted_data>", "", result["content"], flags=re.DOTALL).strip()

		# Extract <buttons>...</buttons>
		btn_match = re.search(r"<buttons>(.*?)</buttons>", response, re.DOTALL)
		if btn_match:
			try:
				result["buttons"] = json.loads(btn_match.group(1))
			except json.JSONDecodeError:
				pass
			# Remove tag from content
			result["content"] = re.sub(r"<buttons>.*?</buttons>", "", result["content"], flags=re.DOTALL).strip()

		return result

	def _extract_data_regex(self, message: str, session) -> Dict:
		"""Extract data from user message using regex patterns."""
		extracted = {}
		msg_lower = message.lower().strip()

		# Extract hex colors
		hex_match = re.findall(r"#[0-9a-fA-F]{6}\b", message)
		if hex_match:
			if not session.primary_color:
				extracted["primary_color"] = hex_match[0]
				if len(hex_match) > 1:
					extracted["secondary_color"] = hex_match[1]
			elif not session.secondary_color:
				extracted["secondary_color"] = hex_match[0]

		# Check for palette names
		for palette in COLOR_PALETTES:
			if palette["label"].lower() in msg_lower:
				if not session.primary_color:
					extracted["primary_color"] = palette["primary"]
					extracted["secondary_color"] = palette["secondary"]
				break

		# Check for theme names
		for theme_name in THEMES:
			if theme_name.lower() in msg_lower:
				if not session.theme or theme_name.lower() in msg_lower:
					extracted["theme"] = theme_name
				break

		# Check for site type names
		for st_name in SITE_TYPES:
			# Match both key and common synonyms
			if st_name.lower() in msg_lower:
				extracted["site_type"] = st_name
				break

		# Common site type synonyms
		type_synonyms = {
			"vitrine": ["showcase", "vitrine", "presentation", "multi-page", "plusieurs pages"],
			"one_page": ["single page", "one page", "une page", "une seule page", "landing", "mono"],
			"ecommerce": ["shop", "store", "e-commerce", "ecommerce", "boutique", "sell", "vendre"],
			"vitrine_user": ["login", "connexion", "user account", "compte utilisateur", "espace client"],
			"blog": ["blog", "articles", "news"],
			"portfolio": ["portfolio", "gallery", "projects"],
			"saas": ["saas", "software", "app", "platform"],
		}
		if "site_type" not in extracted:
			for st, synonyms in type_synonyms.items():
				if any(s in msg_lower for s in synonyms):
					extracted["site_type"] = st
					break

		# Extract font names (common web fonts)
		known_fonts = [
			"Roboto", "Open Sans", "Lato", "Montserrat", "Poppins", "Inter",
			"Raleway", "Oswald", "Playfair Display", "Merriweather", "Nunito",
			"Source Sans Pro", "Ubuntu", "Rubik", "Work Sans", "DM Sans",
			"Lora", "Libre Baskerville", "PT Sans", "Fira Sans", "Quicksand",
			"Barlow", "Manrope", "Space Grotesk", "Plus Jakarta Sans",
			"Archivo", "Outfit", "Sora", "Urbanist",
		]
		found_fonts = []
		for font in known_fonts:
			if font.lower() in msg_lower:
				found_fonts.append(font)
		if found_fonts and not session.heading_font:
			if len(found_fonts) >= 2:
				extracted["heading_font"] = found_fonts[0]
				extracted["body_font"] = found_fonts[1]
			else:
				extracted["heading_font"] = found_fonts[0]
				extracted["body_font"] = found_fonts[0]

		# Detect URLs for inspiration
		url_pattern = r'https?://[^\s<>"\')\]]+'
		urls = re.findall(url_pattern, message)
		if urls:
			extracted["inspiration_urls"] = urls

		# Detect company data confirmation
		keep_patterns = [
			"tout garder", "je garde", "garder tout", "garder ces informations",
			"keep all", "c'est bon", "c'est correct", "parfait",
			"confirmer", "je confirme", "oui", "ok",
		]
		modify_patterns = [
			"modifier", "changer", "corriger", "modify", "change",
		]
		if any(p in msg_lower for p in keep_patterns):
			extracted["_company_confirm"] = "keep"
		elif any(p in msg_lower for p in modify_patterns):
			extracted["_company_confirm"] = "modify"

		return extracted

	# =========================================================================
	# STEP MANAGEMENT
	# =========================================================================

	def _check_step_transition(self, session):
		"""Check if we should advance to the next step."""
		current = session.current_step
		missing = session.get_missing_fields()

		# Get missing fields for current step
		current_missing = [f for f in missing if f.get("step") == current]

		if not current_missing:
			# Inspiration step: always move to pages after any response
			if current == "inspiration":
				self._auto_populate_pages(session)
				session.current_step = "page_selection"
				return

			# Current step complete, advance
			idx = STEPS.index(current) if current in STEPS else 0
			if idx < len(STEPS) - 1:
				next_step = STEPS[idx + 1]
				# Skip inspiration if already provided
				if next_step == "inspiration" and session.inspiration_urls:
					next_step = "pages"
				# Skip pages step (auto-populate + jump to page_selection)
				if next_step == "pages":
					self._auto_populate_pages(session)
					session.current_step = "page_selection"
				elif next_step == "page_selection":
					session.current_step = next_step
				else:
					session.current_step = next_step

	def _auto_populate_pages(self, session):
		"""Auto-populate pages_config based on site_type."""
		if session.pages_config:
			return  # Already set

		from unpress_core.generation import DEFAULT_PAGES_BY_SITE_TYPE
		site_type = session.site_type or "vitrine"
		pages = DEFAULT_PAGES_BY_SITE_TYPE.get(site_type, DEFAULT_PAGES_BY_SITE_TYPE.get("vitrine", []))
		session.pages_config = json.dumps(pages)

	def _get_page_selection_buttons(self, session) -> list:
		"""Get optional page buttons for the page_selection step."""
		from unpress_core.generation import optional_pages_for_site_type
		site_type = session.site_type or "vitrine"
		optional = optional_pages_for_site_type(site_type)

		if not optional:
			return [
				{"label": _("Continue"), "value": "__SKIP_OPTIONAL_PAGES__"},
			]

		# Filter out pages already in pages_config
		existing_routes = set()
		try:
			existing_pages = json.loads(session.pages_config or "[]")
			existing_routes = {p.get("route") for p in existing_pages}
		except (json.JSONDecodeError, TypeError):
			pass

		buttons = []
		for page in optional:
			if page["route"] not in existing_routes:
				buttons.append({
					"label": page["title"],
					"value": f"__ADD_PAGE_{page['route']}__",
				})
		buttons.append({"label": _("No additional pages"), "value": "__SKIP_OPTIONAL_PAGES__"})
		buttons.append({"label": _("Custom page"), "value": "__ADD_CUSTOM_PAGE__"})
		return buttons

	def _add_optional_page(self, session, route: str):
		"""Add an optional page to the session pages_config."""
		from unpress_core.generation import optional_pages_for_site_type
		site_type = session.site_type or "vitrine"
		optional = optional_pages_for_site_type(site_type)

		page_def = next((p for p in optional if p["route"] == route), None)
		if not page_def:
			return None

		pages = json.loads(session.pages_config or "[]")
		# Avoid duplicates
		if any(p.get("route") == route for p in pages):
			return None

		pages.append({"title": page_def["title"], "route": page_def["route"], "type": page_def["type"]})
		session.pages_config = json.dumps(pages)
		return page_def["title"]

	def _add_custom_page(self, session, title: str):
		"""Add a custom page to the session pages_config."""
		# Generate route from title
		route = re.sub(r'[^a-z0-9]+', '-', title.lower().strip()).strip('-')
		pages = json.loads(session.pages_config or "[]")
		# Avoid duplicates
		if any(p.get("route") == route for p in pages):
			return

		pages.append({"title": title, "route": route, "type": "custom"})
		session.pages_config = json.dumps(pages)

	def _get_pages_recap(self, session) -> str:
		"""Get a recap of all selected pages."""
		pages = json.loads(session.pages_config or "[]")
		if not pages:
			return ""
		lines = [_("**Pages to generate:**")]
		for i, p in enumerate(pages, 1):
			lines.append(f"{i}. {p['title']} (`/{p['route']}`)")

		# For e-commerce sites, mention pre-existing webshop pages
		site_type = session.site_type or ""
		if site_type in ("ecommerce", "ecommerce_search"):
			lines.append("")
			lines.append(_("**Pages already available via your shop:**"))
			lines.append(_("- Shop (`/all-products`) — product catalog"))
			lines.append(_("- My Account (`/me`) — customer area"))

		return "\n".join(lines)

	def _get_next_question(self, session) -> str:
		"""Get the next question to ask based on missing fields."""
		missing = session.get_missing_fields()
		if not missing:
			return _("All information collected! Click **Generate Site** when you're ready.")

		next_field = missing[0]["field"]
		prompts = {
			"site_description": _("What is your website about?"),
			"site_name": _("What is the name of your business?"),
			"site_type": _("What type of site would you like?"),
			"theme": _("Which visual theme do you prefer?"),
			"primary_color": _("What main color would you like?"),
		}
		return prompts.get(next_field, _("Let's continue with the next step."))

	# =========================================================================
	# SPECIAL COMMANDS
	# =========================================================================

	def _handle_special_command(self, session, command: str) -> Dict:
		"""Handle special commands (button values starting with __)."""
		if command == "__UPLOAD_LOGO__":
			response = _("Please upload your logo using the upload button or drag & drop.")
			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"await_upload": True,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		elif command == "__UPLOAD_INSPIRATION__":
			response = _("Please upload a reference image for design inspiration.")
			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"await_upload": True,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		elif command == "__SKIP_INSPIRATION__":
			# Skip inspiration and move to pages step
			session.current_step = "style"  # Reset to style so transition goes to pages
			self._auto_populate_pages(session)
			session.current_step = "page_selection"
			session.add_message(role="user", content=_("(Skip inspiration)"))
			recap = self._get_pages_recap(session)
			selection_msg = _("Would you like to add optional pages to your site?")
			response = recap + "\n\n" + selection_msg
			buttons = self._get_page_selection_buttons(session)
			session.add_message(role="assistant", content=response, buttons=buttons)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"buttons": buttons,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		elif command == "__SKIP_LOGO__":
			skip_msg = _("No problem, we'll skip the logo for now.")
			next_q = self._get_next_question(session)
			response = f"{skip_msg}\n\n{next_q}"
			session.add_message(role="user", content=_("(Skip logo)"))
			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		# --- Page selection commands ---
		elif command.startswith("__ADD_PAGE_") and command.endswith("__"):
			route = command[len("__ADD_PAGE_"):-2]
			title = self._add_optional_page(session, route)
			if title:
				response = _("Page **{title}** added!").format(title=title)
				response += "\n\n" + _("Want to add more pages?")
				buttons = self._get_page_selection_buttons(session)
			else:
				response = _("This page is already in your list.")
				buttons = self._get_page_selection_buttons(session)
			session.add_message(role="assistant", content=response, buttons=buttons)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"buttons": buttons,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		elif command == "__SKIP_OPTIONAL_PAGES__":
			recap = self._get_pages_recap(session)
			response = _("Perfect!") + "\n\n" + recap
			response += "\n\n" + _("How would you like to generate?")
			session.current_step = "generation"
			buttons = [
				{"label": _("Generate entire site"), "value": "__GEN_MODE_FULL__"},
				{"label": _("Homepage first"), "value": "__GEN_MODE_PROGRESSIVE__"},
			]
			session.add_message(role="assistant", content=response, buttons=buttons)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"buttons": buttons,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		elif command.startswith("__PUBLISH_LAST_ARTICLE__:"):
			name = command.split(":", 1)[1]
			try:
				from unpress_core.blog_api import set_published

				result = set_published(name=name, published=1)
				response = _("Published — it is live at /{0}.").format(result["route"])
			except Exception as e:
				response = _("I could not publish it: {0}").format(str(e)[:200])
			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
			}

		elif command == "__WRITE_ARTICLE__":
			response = _("What should the article be about? A subject, an angle, anything you would tell a writer.")
			session.add_message(role="assistant", content=response)
			session.db_set("homepage_feedback", "__AWAITING_ARTICLE_TOPIC__", update_modified=False)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
			}

		elif command == "__ADD_CUSTOM_PAGE__":
			response = _("What should this page be called? (e.g. \"Recruitment\", \"FAQ\", \"Pricing\")")
			session.add_message(role="assistant", content=response)
			# Set a flag so next message is treated as custom page name
			session.db_set("homepage_feedback", "__AWAITING_CUSTOM_PAGE_NAME__", update_modified=False)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		# --- Generation mode commands ---
		elif command == "__GEN_MODE_FULL__":
			session.generation_mode = "full"
			session.add_message(role="user", content=_("Generate entire site"))
			session.save(ignore_permissions=True)
			return self.trigger_generation(session.session_id)

		elif command == "__GEN_MODE_PROGRESSIVE__":
			session.generation_mode = "progressive"
			session.add_message(role="user", content=_("Homepage first"))
			session.save(ignore_permissions=True)
			return self.trigger_generation(session.session_id)

		# --- Homepage feedback commands ---
		elif command == "__HOMEPAGE_SATISFIED__":
			session.add_message(role="user", content=_("The homepage looks good!"))
			response = _("Generating the remaining pages with the refined design...")
			session.add_message(role="assistant", content=response)
			session.current_step = "generation"
			session.save(ignore_permissions=True)

			from unpress_core.generation import continue_generation
			result = continue_generation(session_id=session.session_id)
			if result and result.get("job_id"):
				session.job_id = result["job_id"]
				session.generation_status = "queued"
				session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"job_id": result.get("job_id"),
				"status": "queued",
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		elif command == "__HOMEPAGE_REVISE__":
			response = _("What would you like to change? Describe your feedback and I'll regenerate the homepage.")
			session.current_step = "feedback"
			session.add_message(role="assistant", content=response)
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"response": response,
				"current_step": session.current_step,
				"completion_percentage": session.completion_percentage,
				"missing_fields": session.get_missing_fields(),
			}

		# Replace-confirmation buttons (asked when existing pages were
		# designed/edited by hand — see classify_existing_pages). They MUST be
		# handled here: process_message dispatches every __TOKEN__ to this
		# handler before its own routing, so a check there never matches.
		elif command == "__FORCE_REGENERATE__":
			session.add_message(role="user", content=_("Yes, replace everything"))
			session.save(ignore_permissions=True)
			return self.trigger_generation(session.session_id, force_replace=True)

		elif command == "__CANCEL_REGENERATE__":
			session.add_message(role="user", content=_("No, keep my pages"))
			response = _(
				"Understood — I kept all your existing pages. "
				"You can adjust your project and generate again whenever you want."
			)
			session.add_message(role="assistant", content=response)
			session.status = "Active"
			session.save(ignore_permissions=True)
			return {
				"success": True,
				"message": response,
				"completion_percentage": session.completion_percentage,
			}

		# Default: treat as regular message
		return self.process_message(session.session_id, command.strip("_"))

	# =========================================================================
	# UTILITIES
	# =========================================================================

	def _process_inspiration_urls(self, session, urls: List[str]):
		"""Capture inspiration URLs and store references in session."""
		from unpress_core.generation import capture_inspiration

		existing = []
		if session.inspiration_urls:
			try:
				existing = json.loads(session.inspiration_urls)
			except (json.JSONDecodeError, TypeError):
				existing = []

		for url in urls:
			# Skip already captured URLs
			if any(item.get("url") == url for item in existing):
				continue
			try:
				result = capture_inspiration(url=url, sentiment="like")
				if result and result.get("name"):
					existing.append({"url": url, "name": result["name"]})
			except Exception as e:
				frappe.log_error("Builder Chat: Inspiration capture error", str(e))

		session.inspiration_urls = json.dumps(existing)

	def _get_company_data(self) -> Dict:
		"""Fetch available company/site data from Frappe/ERPNext."""
		data = {}

		# Try ERPNext Company DocType
		try:
			company_name = frappe.db.get_default("company")
			if not company_name:
				companies = frappe.get_all("Company", limit=1, pluck="name")
				company_name = companies[0] if companies else None

			if company_name:
				company = frappe.get_doc("Company", company_name)
				if company.company_name:
					data["company_name"] = company.company_name
				if company.get("phone_no"):
					data["phone"] = company.phone_no
				if company.get("email"):
					data["email"] = company.email
				if company.get("company_logo"):
					data["logo"] = company.company_logo
				if company.get("website"):
					data["website"] = company.website
				if company.get("company_description"):
					data["description"] = company.company_description
		except Exception as e:
			frappe.log_error("Builder Chat: company data loading failed", str(e))

		# Try Website Header Footer Config (Builder-specific)
		try:
			config = frappe.get_single("Website Header Footer Config")
			if not data.get("logo") and config.get("logo_image"):
				data["logo"] = config.logo_image
			if config.get("primary_color"):
				data["primary_color"] = config.primary_color
			if config.get("secondary_color"):
				data["secondary_color"] = config.secondary_color
			if config.get("heading_font"):
				data["heading_font"] = config.heading_font
			if config.get("body_font"):
				data["body_font"] = config.body_font
			social = {}
			for platform in ["facebook", "twitter", "instagram", "linkedin", "youtube"]:
				url = config.get(f"{platform}_url")
				if url:
					social[platform] = url
			if social:
				data["social_links"] = social
		except Exception as e:
			frappe.log_error("Builder Chat: header footer config failed", str(e))

		# Site URL
		data["site_url"] = frappe.utils.get_url()

		return data

	def _maybe_present_company_data(self, session, extracted: Dict, ai_response: str) -> Optional[Dict]:
		"""Present company data after site_type selection if available and not yet presented."""
		# Check if site_type was just extracted and company data exists
		if not extracted.get("site_type"):
			return None
		if not session.company_data:
			return None
		if session.site_name:
			# Already have a site name, company data was already processed
			return None

		presentation = self._build_company_presentation(session)
		if not presentation:
			return None

		# Build the combined response
		lines = [ai_response.rstrip()]
		lines.append("")
		lines.append("---")
		lines.append("")
		lines.append(presentation["text"])

		buttons = [
			{"label": _("Keep all"), "value": _("Keep all")},
			{"label": _("Modify"), "value": _("Modify")},
		]

		return {
			"content": "\n".join(lines),
			"buttons": buttons,
		}

	def _build_company_presentation(self, session) -> Optional[Dict]:
		"""Build a user-facing presentation of found company data."""
		if not session.company_data:
			return None

		try:
			cd = json.loads(session.company_data)
		except (json.JSONDecodeError, TypeError):
			return None

		items = []
		if cd.get("company_name"):
			items.append(f"**{_('Name')}:** {cd['company_name']}")
		if cd.get("phone"):
			items.append(f"**{_('Phone')}:** {cd['phone']}")
		if cd.get("email"):
			items.append(f"**{_('Email')}:** {cd['email']}")
		if cd.get("logo"):
			items.append(f"**{_('Logo')}:** {_('available')} ✓")
		if cd.get("website"):
			items.append(f"**{_('Website URL')}:** {cd['website']}")
		if cd.get("description"):
			desc_preview = cd["description"][:80]
			if len(cd["description"]) > 80:
				desc_preview += "..."
			items.append(f"**{_('Description')}:** {desc_preview}")

		if not items:
			return None

		header = _("I found the following information for your business:")
		text = f"{header}\n\n" + "\n".join(f"- {item}" for item in items)
		text += "\n\n" + _("Would you like to keep this information or modify it?")

		return {"text": text, "data": cd}

	def _apply_company_data(self, session):
		"""Apply all company data to session fields."""
		if not session.company_data:
			return

		try:
			cd = json.loads(session.company_data)
		except (json.JSONDecodeError, TypeError):
			return

		update = {}
		if cd.get("company_name") and not session.site_name:
			update["site_name"] = cd["company_name"]
		if cd.get("logo") and not session.logo_image:
			update["logo_image"] = cd["logo"]
		if cd.get("primary_color") and not session.primary_color:
			update["primary_color"] = cd["primary_color"]
		if cd.get("secondary_color") and not session.secondary_color:
			update["secondary_color"] = cd["secondary_color"]
		if cd.get("heading_font") and not session.heading_font:
			update["heading_font"] = cd["heading_font"]
		if cd.get("body_font") and not session.body_font:
			update["body_font"] = cd["body_font"]
		if cd.get("social_links") and not session.social_links:
			update["social_links"] = json.dumps(cd["social_links"])

		if update:
			session.update_extracted_data(update)

	def _get_user_first_name(self) -> str:
		"""Get the current user's first name."""
		try:
			user = frappe.session.user
			if user and user != "Guest":
				user_doc = frappe.get_doc("User", user)
				if user_doc.first_name:
					return user_doc.first_name
				if user_doc.full_name:
					return user_doc.full_name.split()[0]
		except Exception as e:
			frappe.log_error("Builder Chat: user lookup failed", str(e))
		return ""

	def _format_messages(self, messages) -> List[Dict]:
		"""Format messages for frontend consumption."""
		formatted = []
		for msg in messages:
			entry = {
				"role": msg.role,
				"content": msg.content,
				"timestamp": str(msg.timestamp) if msg.timestamp else None,
				"attachment": msg.attachment,
			}
			# Parse buttons JSON
			if msg.buttons:
				try:
					entry["buttons"] = json.loads(msg.buttons)
				except (json.JSONDecodeError, TypeError):
					entry["buttons"] = None
			else:
				entry["buttons"] = None
			formatted.append(entry)
		return formatted
