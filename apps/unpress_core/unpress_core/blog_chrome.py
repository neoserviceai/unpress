"""The blog, wearing the site's design.

Frappe lets a page choose its own template: `base_template_page` reads
`context.template` **after** the `update_website_context` hooks have run. That
is the seam this uses — the blog app keeps its doctypes, its routing and its
data, and we own how an article looks.

Owning the templates rather than styling theirs is a deliberate cost. It buys
the two things a stylesheet cannot do: render the cover image, which their
markup never prints, and offer layouts, which is a structural choice. It costs
a copy that drifts if they rewrite theirs — acceptable, because the blog app is
mature, extracted from the core, and barely moves.
"""

import frappe

PLUGIN = "blog"

POST_TEMPLATE = "unpress_core/templates/blog/post.html"

# The settings the templates read, and what they fall back to. Kept here so a
# site that predates the fields still renders.
DEFAULTS = {
	"blog_layout": "Grid",
	"blog_post_layout": "Cover hero",
	"blog_allow_comments": 0,
	"blog_show_author": 1,
}


def _is_blog_page(context) -> tuple:
	"""(is a blog page, is the index). Cheap: no query when the path is not ours.

	The doctype is NOT the discriminator — the index is the list page *of* Blog
	Post, so it carries the same `doctype`. What separates them is a document:
	an article renders one, an index renders many. The path agrees, and is the
	cheaper check: /blog and /blog/<category> list, /blog/<category>/<slug>
	reads.
	"""
	path = (frappe.request.path if frappe.request else "").strip("/")
	if path != "blog" and not path.startswith("blog/"):
		return False, False

	doc = context.get("doc")
	doctype = getattr(doc, "doctype", None) or (doc or {}).get("doctype") if doc else None
	if doctype == "Blog Post":
		return True, False

	# no document: the index, or a category listing
	return True, True


def apply(context):
	"""`update_website_context` — point a blog page at our templates."""
	try:
		from unpress_core.plugins import is_enabled

		if not is_enabled(PLUGIN):
			return
	except ImportError:
		return

	is_blog, is_index = _is_blog_page(context)
	if not is_blog:
		return

	settings = _settings()
	context.update(settings)

	if is_index:
		# The index keeps the blog app's template: frappe's list machinery
		# computes `result` for it, and replacing the template loses that. A
		# body class is enough — the cards are already there, they only need
		# laying out.
		layout = str(settings.get("blog_layout") or "Grid").lower()
		existing = context.get("body_class") or ""
		context["body_class"] = f"{existing} u-blog u-blog--{layout}".strip()

		# The list page's own title is frappe's generic "Portal", which is what
		# the page header would print. Name it what the visitor came for.
		category = context.get("category") or {}
		context["page_header_title"] = (
			(category.get("title") if isinstance(category, dict) else None)
			or context.get("blog_title")
			or frappe._("Blog")
		)
		context["page_header_subtitle"] = context.get("blog_introduction") or ""
	else:
		# The article page has to be ours: the cover comes from a field their
		# markup never prints, and no stylesheet can conjure an image.
		context["template"] = POST_TEMPLATE


def _settings() -> dict:
	try:
		from unpress_core.hf_utils.header_footer import get_header_footer_config

		config = get_header_footer_config()
	except Exception:
		config = None

	if not config:
		return dict(DEFAULTS)

	out = {}
	for field, fallback in DEFAULTS.items():
		value = config.get(field)
		out[field] = fallback if value in (None, "") else value
	return out


def comments_allowed() -> bool:
	"""Whether a new article should accept comments.

	Off unless the site says otherwise: a comment box nobody watches fills with
	spam, and that is the site owner's decision to make, not a default to
	inherit.
	"""
	return bool(_settings().get("blog_allow_comments"))
