"""The band at the top of pages the editor does not build.

A generated page opens on a hero the AI composed for it. Every other page —
the blog index, a category listing, the 404, a section that is coming — arrived
with whatever heading its own app happened to print. That is why /blog read as
a different website: no breadcrumb, a bare `<h1>` in someone else's markup, and
none of the site's rhythm.

This is the third piece of the site chrome, beside the header and the footer:
one band, decided once in the Theme, rendered above the content of every page
Builder does not own.

It deliberately skips article pages. Those open on a cover hero that already
carries the title and the category — a page header there would be a title above
a title.
"""

import frappe
from frappe import _

# The band is a preset plus a fill — the same shape as the header and the
# footer, and for the same reason.
#
# It used to be one enum: None / Simple / Centered / Tinted. "Centered" is a
# composition and "Tinted" is a background, so mixing them in one field made
# half the combinations unsayable — there was no way to ask for a centred title
# over a photograph. And letting the model invent a band per site would repeat
# the mistake the interior pages already made.
#
# So: WE design the presets, the AI picks one and picks a fill. `footer_template`
# works exactly this way.
TEMPLATES = ("Minimal", "Standard", "Centered", "Split", "None")
BACKGROUNDS = ("None", "Tinted", "Solid", "Image")

DEFAULTS = {
	"page_header_template": "Standard",
	"page_header_background": "None",
	"page_header_bg_color": "",     # empty: Tinted washes the primary colour
	"page_header_image": "",
	"page_header_excluded_routes": "",
	"show_breadcrumbs": 1,
}

# Fills that put the title over something dark enough to need light text.
_DARK_BACKGROUNDS = ("Image", "Solid")

# The band carries its own CSS, the way the header and the footer do.
#
# `web_include_css` only reaches pages frappe renders. A Builder page loads its
# own assets, so a stylesheet rule for the band would style it on the blog and
# leave it unstyled — breadcrumbs flush against the window edge — on every page
# the AI generated. Shipping the rules with the markup is what makes one band
# actually mean one band.
_CSS = (
	"<style>.site-page-header{border-bottom:1px solid var(--footer-border,rgba(0,0,0,0.08))}.site-page-header__inner{max-width:var(--container-width,1280px);margin:0 auto;padding:44px 24px 36px}.site-page-header__crumbs{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:0.8125rem;color:var(--muted-color,#6b7280);margin-bottom:12px}.site-page-header__crumbs a{color:inherit;text-decoration:none}.site-page-header__crumbs a:hover{color:var(--primary-color,#111)}.site-page-header__sep{opacity:0.5}.site-page-header__title{font-size:clamp(1.9rem,1.2rem + 2.2vw,3rem);font-weight:700;font-family:var(--heading-font,inherit);line-height:1.15;margin:0}.site-page-header__subtitle{max-width:62ch;margin:10px 0 0;color:var(--muted-color,#6b7280);line-height:1.6}.site-page-header--minimal .site-page-header__inner{padding-top:32px;padding-bottom:24px}.site-page-header--centered .site-page-header__inner{text-align:center}.site-page-header--centered .site-page-header__crumbs{justify-content:center}.site-page-header--centered .site-page-header__subtitle{margin-left:auto;margin-right:auto}.site-page-header__split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:32px;align-items:end}.site-page-header__split .site-page-header__subtitle{margin-top:0}@media (max-width:768px){.site-page-header__split{grid-template-columns:1fr;gap:12px}}.site-page-header--bg-image .site-page-header__inner,.site-page-header--bg-solid .site-page-header__inner{padding-top:72px;padding-bottom:64px}.site-page-header--on-dark{border-bottom-color:transparent}.site-page-header--on-dark .site-page-header__title{color:#fff}.site-page-header--on-dark .site-page-header__subtitle,.site-page-header--on-dark .site-page-header__crumbs{color:rgba(255,255,255,0.82)}.site-page-header--on-dark .site-page-header__crumbs a:hover{color:#fff}.site-page-header--bg-tinted{border-bottom-color:transparent}</style>"
)


# Pages that carry their own opening and must not get a second one.
#
# This is the DEFAULT, not the law: the list lives in a setting so an owner can
# add a route without touching the code. It mattered the day the shop arrives —
# a product page opens on its gallery, a cart is not an editorial page — but
# also for any one-off landing page a client wants bare.
SKIP_PATHS = ("", "home", "index")


def _excluded_routes(config: dict) -> tuple:
	"""Routes that get no band: the setting, or the default when it is empty.

	One route per line, `*` allowed at the end of a pattern.
	"""
	raw = (config.get("page_header_excluded_routes") or "").strip()
	if not raw:
		return SKIP_PATHS
	return tuple(line.strip().strip("/") for line in raw.splitlines() if line.strip())


def _is_excluded(path: str, routes: tuple) -> bool:
	path = (path or "").strip("/")
	for pattern in routes:
		if pattern.endswith("*"):
			if path.startswith(pattern[:-1]):
				return True
		elif path == pattern:
			return True
	return False


def _config():
	try:
		from unpress_core.hf_utils.header_footer import get_header_footer_config

		return get_header_footer_config()
	except Exception:
		return None


def settings() -> dict:
	config = _config()
	if not config:
		return dict(DEFAULTS)
	out = {}
	for field, fallback in DEFAULTS.items():
		value = config.get(field)
		out[field] = fallback if value in (None, "") else value
	return out


def _breadcrumbs(context, path: str, current: str) -> list:
	"""Home, the trail, then the page itself — each label once.

	Frappe builds `parents` for some pages (the blog does) and it knows the real
	titles, so it wins when present. It also already starts at Home, which is
	why this cannot simply prepend one: /blog was reading "Home / Home / Portal".
	"""
	crumbs = []
	parents = context.get("parents") or []

	if parents:
		for parent in parents:
			label = parent.get("label") or parent.get("title") or parent.get("name")
			route = parent.get("route") or parent.get("url") or ""
			if label:
				crumbs.append({"label": str(label), "url": "/" + str(route).lstrip("/")})
	else:
		walked = []
		for segment in [s for s in path.split("/") if s][:-1]:
			walked.append(segment)
			crumbs.append({
				"label": segment.replace("-", " ").replace("_", " ").capitalize(),
				"url": "/" + "/".join(walked),
			})

	home = _("Home")
	if not crumbs or crumbs[0]["label"].strip().lower() not in {home.lower(), "home"}:
		crumbs.insert(0, {"label": home, "url": "/"})

	# the page itself closes the trail, unless the trail already ends on it
	if current and (not crumbs or crumbs[-1]["label"].strip().lower() != current.strip().lower()):
		crumbs.append({"label": current, "url": ""})

	# consecutive duplicates come from apps that repeat the section name
	deduped = []
	for crumb in crumbs:
		if deduped and deduped[-1]["label"].strip().lower() == crumb["label"].strip().lower():
			deduped[-1] = crumb
			continue
		deduped.append(crumb)
	return deduped


def render(context) -> str:
	"""The band, or an empty string when this page should not have one."""
	config = settings()
	template = config.get("page_header_template") or "Standard"
	if template == "None":
		return ""

	# A page may say it opens on its own composition — our 404 is a centred
	# statement, and a band above it would be the same words twice.
	if context.get("show_page_header") is False:
		return ""

	path = (getattr(frappe.local, "page_header_route", None) or (frappe.request.path if frappe.request else "")).strip("/")
	if _is_excluded(path, _excluded_routes(config)):
		return ""

	# an article opens on its cover; that hero already is the page header
	doc = context.get("doc")
	doctype = getattr(doc, "doctype", None) if doc else None
	if doctype == "Blog Post":
		return ""

	title = context.get("page_header_title") or context.get("title") or ""
	if not title:
		return ""

	background = config.get("page_header_background") or "None"
	return _CSS + frappe.render_template(
		"unpress_core/templates/includes/header_footer/page_header.html",
		{
			"template": template,
			"background": background,
			"fill": _fill(background, config),
			"on_dark": background in _DARK_BACKGROUNDS,
			"title": title,
			"subtitle": context.get("page_header_subtitle") or "",
			"breadcrumbs": _breadcrumbs(context, path, title) if config.get("show_breadcrumbs") else [],
		},
	)


def _fill(background: str, config: dict) -> str:
	"""The `background` declaration for the chosen fill, or an empty string.

	Written here rather than in the template so the image URL is quoted once, in
	Python, instead of being interpolated into a style attribute by hand.
	"""
	colour = (config.get("page_header_bg_color") or "").strip()

	if background == "Solid":
		return f"background-color:{colour};" if colour else ""

	if background == "Tinted":
		wash = colour or "var(--primary-color, #111)"
		return f"background:color-mix(in srgb,{wash} 8%,transparent);"

	if background == "Image":
		image = (config.get("page_header_image") or "").strip()
		if not image:
			return ""
		# the scrim is not decoration: the title is light on top of a photograph
		# nobody chose, and without it the words vanish on a bright sky
		safe = image.replace("\\", "").replace("'", "%27").replace('"', "%22")
		return (
			"background-image:linear-gradient(rgba(0,0,0,0.55),rgba(0,0,0,0.35)),"
			f"url('{safe}');background-size:cover;background-position:center;"
		)

	return ""


@frappe.whitelist(allow_guest=True)
def render_page_header() -> str:
	"""Jinja entry point — the Web Template calls this with the page context.

	Reads `frappe.local.page_header_context`, which `blog_chrome`/`site_chrome`
	stash for it: a Web Template renders in its own scope and cannot see the
	page's context dict.
	"""
	context = getattr(frappe.local, "page_header_context", None)
	if context is None:
		return ""
	return render(context)


@frappe.whitelist(allow_guest=True)
def render_builder_page_header(doc=None) -> str:
	"""The same band, for a page the editor built.

	Called from the Builder page template. The homepage keeps the hero the AI
	composed for it; every interior page opens on this instead of a title band
	each generation improvises differently — which is the whole point of having
	one.
	"""
	if doc is None:
		return ""

	route = (doc.get("route") if hasattr(doc, "get") else getattr(doc, "route", "")) or ""
	route = str(route).strip("/")
	if _is_excluded(route, _excluded_routes(settings())):
		return ""

	title = (
		(doc.get("page_title") if hasattr(doc, "get") else getattr(doc, "page_title", ""))
		or ""
	)
	if not title:
		return ""

	def _field(name):
		return (doc.get(name) if hasattr(doc, "get") else getattr(doc, name, None)) or ""

	# The page's meta description is already one descriptive line about this
	# page, written by whoever made it. Reusing it beats adding a second field
	# that says the same thing and that nothing fills.
	subtitle = _field("page_header_subtitle") or _field("meta_description")

	context = frappe._dict({"title": title, "page_header_subtitle": subtitle})
	# a Builder page has no `parents`; the route is the trail
	frappe.local.page_header_route = route
	try:
		band = render(context)
	finally:
		frappe.local.page_header_route = None

	if not band:
		return ""

	# Two header presets deliberately pull the page up underneath themselves,
	# because a generated homepage opens on a tall hero built to sit under the
	# bar. An interior page now opens on this band instead — without a spacer
	# the floating header lands squarely on its title. A frappe page gets its
	# spacer from render_site_header(standalone=True); this is the Builder side
	# of the same rule.
	config = _config()
	style = (config.get("header_style") if config else "") or "Classic"
	if style in ("Floating", "Transparent"):
		# ...and its height travels with it, for the same reason the band's own
		# rules do: `web_include_css` never reaches a Builder page, so the rule
		# in web_pages.css would leave this div at zero height here — present in
		# the markup, invisible in effect, header still on the title.
		# The floating height cannot ride on `.site-header--floating + .spacer`
		# here: on a frappe page the spacer follows the header directly, but on
		# a Builder page it is the band that emits it, so it is no longer the
		# header's adjacent sibling. Measured before fixing: /blog got 104px and
		# /about 64px — the same band sitting 40px higher on half the site. A
		# modifier class says it outright instead of inferring it from position.
		band = (
			"<style>.site-header__spacer{height:var(--header-height,64px)}"
			".site-header__spacer--floating"
			"{height:calc(var(--header-height,64px) + 40px)}</style>"
			'<div class="site-header__spacer site-header__spacer--floating"'
			' aria-hidden="true"></div>'
		) + band

	return band
