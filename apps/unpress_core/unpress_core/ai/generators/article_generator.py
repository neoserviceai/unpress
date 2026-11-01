"""Writing blog articles for a site the generator already knows.

The point is not "an LLM can write a blog post" — anything can. It is that this
one writes for *this* site: the same business, the same tone the design brief
settled on, and with the pages that already exist available to link to. An
article that could have been written for any site is the thing nobody wants.

So the context comes from what the site already carries:

- the chrome config for the site's name and what it says about itself;
- the saved design brief for the tone that was decided once;
- the published pages, so the article can point at them instead of inventing
  a "contact us" that goes nowhere.
"""

import frappe

from unpress_core.ai.config import get_ai_settings
from unpress_core.ai.logging import ai_log
from unpress_core.ai.providers import get_provider
from unpress_core.ai.schemas.article import GeneratedArticle

SYSTEM_PROMPT = """You write blog articles for a small business website.

What makes an article worth publishing:

- It says something only this business could say. Their trade, their region,
  their way of working. Generic advice that fits any business in the sector is
  the failure mode to avoid.
- It is useful on its own. A reader who never buys anything should still come
  away with something.
- It is the length the subject deserves — usually 400 to 700 words. Padding to
  hit a number reads as padding.
- It sounds like a person who does this work, not like marketing copy. No
  "In today's fast-paced world", no "Look no further", no closing paragraph
  that summarises what was just said.

Write in the language of the brief you are given. Return Markdown starting at
'## ' — the title is rendered separately, so an H1 in the body duplicates it."""


def _site_context() -> dict:
	"""What this site is, in the words it already uses about itself."""
	context = {}
	try:
		from unpress_core.hf_utils.header_footer import get_header_footer_config

		config = get_header_footer_config()
		if config:
			context["site_name"] = config.get("logo_text") or ""
			context["site_description"] = config.get("footer_description") or ""
	except Exception:
		pass

	if not context.get("site_name"):
		context["site_name"] = frappe.db.get_single_value("Website Settings", "app_name") or ""

	return context


def _brief_context() -> dict:
	"""The tone and stance the site settled on, if a brief was saved."""
	import json

	row = frappe.get_all(
		"Builder Chat Session",
		filters={"saved_brief": ["is", "set"]},
		fields=["name", "site_description", "site_name"],
		order_by="modified desc",
		limit_page_length=1,
	)
	if not row:
		return {}

	out = {"site_description": row[0].site_description or "", "site_name": row[0].site_name or ""}
	raw = frappe.db.get_value("Builder Chat Session", row[0].name, "saved_brief")
	try:
		brief = json.loads(raw) if raw else {}
	except (TypeError, ValueError):
		brief = {}

	for key in ("site_tone", "design_concept"):
		if brief.get(key):
			out[key] = brief[key]
	return out


def _existing_pages(limit: int = 12) -> list:
	"""Published pages the article may link to, rather than inventing routes."""
	try:
		rows = frappe.get_all(
			"Builder Page",
			filters={"published": 1},
			fields=["page_title", "route"],
			order_by="modified desc",
			limit_page_length=limit,
		)
	except Exception:
		return []
	return [f"{r.page_title} (/{r.route})" for r in rows if r.route]


def build_prompt(topic: str, language: str | None = None) -> str:
	site = _site_context()
	brief = _brief_context()

	name = site.get("site_name") or brief.get("site_name") or ""
	description = site.get("site_description") or brief.get("site_description") or ""

	lines = ["Write one blog article."]
	if name:
		lines.append(f"\nThe site: {name}")
	if description:
		lines.append(f"What it does: {description}")
	if brief.get("site_tone"):
		lines.append(f"Tone decided for this site: {brief['site_tone']}")
	if brief.get("design_concept"):
		lines.append(f"Design direction, for register rather than layout: {brief['design_concept']}")

	pages = _existing_pages()
	if pages:
		lines.append("\nPages that exist on this site, if the article needs to link somewhere:")
		lines.extend(f"- {page}" for page in pages)

	lines.append(f"\nThe subject: {topic}")
	if language:
		lines.append(f"\nWrite in this language: {language}")
	else:
		lines.append("\nWrite in the language of the subject above.")

	return "\n".join(lines)


def generate_article(topic: str, language: str | None = None) -> GeneratedArticle:
	"""One article, written for this site."""
	settings = get_ai_settings()
	llm = get_provider(
		settings.provider,
		model=settings.model,
		api_key=settings.api_key,
		base_url=settings.base_url,
		# prose, not layout: a little warmth, not a lot of invention
		temperature=0.8,
		timeout=settings.request_timeout,
	)

	prompt = build_prompt(topic, language)
	ai_log("info", "Generating article", topic=topic[:120], provider=settings.provider)

	article = llm.generate_structured(
		prompt=prompt,
		schema=GeneratedArticle,
		system_prompt=SYSTEM_PROMPT,
	)

	# The model is told not to repeat the title as an H1; enforce it rather than
	# hope, because a duplicated heading is the most visible way this goes wrong.
	body = (article.content_md or "").lstrip()
	if body.startswith("# "):
		first, _, rest = body.partition("\n")
		if first[2:].strip().lower() == (article.title or "").strip().lower():
			body = rest.lstrip()
			article.content_md = body

	ai_log("info", "Article generated", title=article.title[:120], chars=len(article.content_md or ""))
	return article


COVER_NEGATIVE = (
	"text, words, letters, headlines, captions, logos, watermarks, typography, "
	"UI elements, signatures, borders, collage, split frames"
)


def cover_prompt(article) -> str:
	"""What the cover image should show.

	Deliberately concrete and about the subject, not about the article: a photo
	of the thing, not an illustration of "an article about the thing". The
	failure mode of generated blog covers is an abstract swirl that could
	illustrate anything.
	"""
	site = _site_context()
	subject = (article.title or "").strip()
	intro = (article.intro or "").strip()

	parts = [
		"Editorial photograph for a blog article.",
		f"The article is titled: {subject}." if subject else "",
		f"It is about: {intro}" if intro else "",
	]
	if site.get("site_description"):
		parts.append(f"The business it belongs to: {site['site_description'][:300]}")

	parts.append(
		"Photograph the subject itself — real objects, real hands, a real place. "
		"Natural light, shallow depth of field, room around the subject so a "
		"title can sit over it. No text of any kind in the image."
	)
	return " ".join(p for p in parts if p)


def request_cover(article, blog_post_name: str) -> str | None:
	"""Queue the cover image, writing it back onto the post when it lands.

	Returns the image job id, or None when this site has no image backend —
	the article is worth publishing either way, so a missing cover is never a
	reason to fail the write.
	"""
	try:
		from unpress_core.generation import _image_backend_available

		if not _image_backend_available():
			ai_log("info", "No image backend; article gets no cover", post=blog_post_name)
			return None
	except Exception:
		return None

	try:
		return frappe.enqueue(
			"unpress_core.ai.generators.article_generator.cover_job",
			queue="long",
			# One image, but through whichever backend the site has: Codex has
			# taken over ten minutes on a single cover under load, and the
			# 600 s this used to allow killed it mid-generation. The site's own
			# image worker allows 5400 s for a batch; one image gets a third of
			# that rather than a number that looked generous.
			timeout=1800,
			blog_post_name=blog_post_name,
			prompt=cover_prompt(article),
		).id
	except Exception as e:
		ai_log("warning", "Could not queue article cover", error=str(e)[:200])
		return None


def cover_job(blog_post_name: str, prompt: str):
	"""Generate the cover and put it on the post.

	Its own job because it goes through whichever image backend the site has,
	and those take minutes. A failure here leaves the article exactly as it
	was — with the gradient card the blog falls back to.
	"""
	from unpress_core.generation import generate_one_image

	try:
		url = generate_one_image(prompt, width=1024, height=576)
	except Exception as e:
		frappe.log_error("Article cover generation failed", f"{blog_post_name}\n{e}")
		return

	if url and frappe.db.exists("Blog Post", blog_post_name):
		frappe.db.set_value("Blog Post", blog_post_name, "meta_image", url, update_modified=False)
		frappe.db.commit()
		ai_log("info", "Article cover set", post=blog_post_name, url=url)
