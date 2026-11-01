# Rich components rebuilt from third-party Elementor widgets.
# Each component is a real Builder block tree (editable) plus one scoped
# <style> block for behavior inline styles cannot express (hover, media).
from frappe import _

from .elementor import block


def _style_block(css):
	return block("style", {}, inner_html=css, name="component-style")


def build_expanding_cards(items, uid="ecc1", height="540px"):
	"""Vertical accordion cards (rebuild of ucaddon_expanding_content_cards):
	collapsed cards show a vertical title; the hovered card expands."""
	cls = f"upx-ecc-{uid}"
	css = f"""
.{cls} {{ display:flex; gap:10px; width:100%; height:{height}; }}
.{cls} .upx-card {{ position:relative; flex:1; min-width:0; border-radius:14px; overflow:hidden;
  background-size:cover; background-position:center; display:flex; align-items:flex-end;
  text-decoration:none; transition:flex .45s cubic-bezier(.4,0,.2,1); }}
.{cls} .upx-card::after {{ content:""; position:absolute; inset:0;
  background:linear-gradient(to top, rgba(0,0,0,.72) 0%, rgba(0,0,0,.12) 55%); }}
.{cls} .upx-card:hover {{ flex:5; }}
.{cls} .upx-title {{ position:relative; z-index:1; color:#fff; font-weight:700; font-size:1.05rem;
  letter-spacing:.14em; text-transform:uppercase; white-space:nowrap; margin:22px;
  writing-mode:vertical-rl; transform:rotate(180deg); transition:all .45s; }}
.{cls} .upx-card:hover .upx-title {{ writing-mode:horizontal-tb; transform:none; font-size:1.5rem; letter-spacing:.05em; }}
@media (max-width: 900px) {{
  .{cls} {{ flex-direction:column; height:auto; }}
  .{cls} .upx-card {{ height:64px; flex:none; }}
  .{cls} .upx-card:hover {{ height:300px; }}
  .{cls} .upx-title {{ writing-mode:horizontal-tb; transform:none; }}
}}
"""
	cards = []
	for it in items:
		title = block("div", {}, inner_html=it["title"], name="card-title", classes=["upx-title"])
		card = block(
			"a",
			{"backgroundImage": f"url('{it['img']}')"} if it.get("img") else {"background": "#222"},
			[title],
			name=f"card-{it['title'][:18]}",
			attributes={"href": it.get("link") or "#"},
			classes=["upx-card"],
		)
		cards.append(card)
	return block(
		"div", {"width": "100%"}, [_style_block(css)] + [
			block("div", {}, cards, name="cards-row", classes=[cls])
		],
		name="expanding-cards",
	)


def build_post_grid(items, uid="grid1", columns=3):
	"""Responsive property grid (rebuild of ucaddon_post_grid):
	image cards with gradient overlay and bottom title, zoom on hover."""
	cls = f"upx-grid-{uid}"
	css = f"""
.{cls} {{ display:grid; grid-template-columns:repeat({columns}, 1fr); gap:26px; width:100%; }}
.{cls} .upx-cell {{ position:relative; display:block; border-radius:14px; overflow:hidden;
  aspect-ratio:3/2; text-decoration:none; }}
.{cls} .upx-img {{ position:absolute; inset:0; background-size:cover; background-position:center;
  transition:transform .5s ease; }}
.{cls} .upx-cell:hover .upx-img {{ transform:scale(1.06); }}
.{cls} .upx-cell::after {{ content:""; position:absolute; inset:0;
  background:linear-gradient(to top, rgba(0,0,0,.66) 0%, rgba(0,0,0,0) 55%); }}
.{cls} .upx-label {{ position:absolute; left:20px; bottom:16px; z-index:1; color:#fff;
  font-weight:700; font-size:1.15rem; letter-spacing:.04em; }}
@media (max-width: 1000px) {{ .{cls} {{ grid-template-columns:repeat(2, 1fr); }} }}
@media (max-width: 640px) {{ .{cls} {{ grid-template-columns:1fr; }} }}
"""
	cells = []
	for it in items:
		img = block(
			"div",
			{"backgroundImage": f"url('{it['img']}')"} if it.get("img") else {"background": "#333"},
			name="cell-img",
			classes=["upx-img"],
		)
		label = block("div", {}, inner_html=it["title"], name="cell-title", classes=["upx-label"])
		cells.append(
			block(
				"a", {}, [img, label],
				name=f"cell-{it['title'][:18]}",
				attributes={"href": it.get("link") or "#"},
				classes=["upx-cell"],
			)
		)
	return block(
		"div", {"width": "100%"}, [_style_block(css)] + [block("div", {}, cells, name="grid", classes=[cls])],
		name="post-grid",
	)


def build_property_page(data, uid="prop"):
	"""Property detail page: hero with title/price, description, photo grid."""
	import html as html_mod

	cls = f"upx-prop-{uid}"
	css = f"""
.{cls}-hero {{ position:relative; width:100%; height:56vh; min-height:380px;
  background-size:cover; background-position:center; display:flex; align-items:flex-end; }}
.{cls}-hero::after {{ content:""; position:absolute; inset:0;
  background:linear-gradient(to top, rgba(0,0,0,.7) 0%, rgba(0,0,0,.05) 60%); }}
.{cls}-hero .upx-hero-inner {{ position:relative; z-index:1; padding:40px;
  max-width:1140px; margin:0 auto; width:100%; }}
.{cls}-hero h1 {{ color:#fff; font-size:3rem; margin:0 0 10px; }}
.{cls}-price {{ display:inline-block; background:#fff; color:#111; font-weight:700;
  padding:8px 18px; border-radius:999px; font-size:1.05rem; }}
.{cls}-body {{ max-width:860px; margin:48px auto; padding:0 24px; }}
.{cls}-body p {{ line-height:1.75; margin:0 0 18px; color:#2a2a2a; }}
.{cls}-gallery {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px;
  max-width:1140px; margin:0 auto 64px; padding:0 24px; }}
.{cls}-gallery .upx-ph {{ aspect-ratio:4/3; border-radius:12px; overflow:hidden;
  background-size:cover; background-position:center; transition:transform .4s; }}
.{cls}-gallery .upx-ph:hover {{ transform:scale(1.03); }}
@media (max-width:900px) {{ .{cls}-gallery {{ grid-template-columns:repeat(2,1fr); }}
  .{cls}-hero h1 {{ font-size:2rem; }} }}
"""
	unesc = html_mod.unescape
	hero_children = [block("h1", {}, inner_html=unesc(data["title"]), name="prop-title")]
	if data.get("infos"):
		hero_children.append(
			block("div", {}, inner_html=unesc(data["infos"][0]), name="prop-price", classes=[f"{cls}-price"])
		)
	hero = block(
		"div",
		{"backgroundImage": f"url('{data['gallery'][0]}')"} if data.get("gallery") else {"background": "#222"},
		[block("div", {}, hero_children, name="hero-inner", classes=["upx-hero-inner"])],
		name="prop-hero",
		classes=[f"{cls}-hero"],
	)
	body = block(
		"div", {},
		[block("p", {}, inner_html=unesc(p), name=f"para-{i}") for i, p in enumerate(data.get("paragraphs", []))],
		name="prop-body",
		classes=[f"{cls}-body"],
	)
	photos = [
		block("div", {"backgroundImage": f"url('{src}')"}, name=f"photo-{i}", classes=["upx-ph"])
		for i, src in enumerate(data.get("gallery", [])[1:13])
	]
	gallery = block("div", {}, photos, name="prop-gallery", classes=[f"{cls}-gallery"])
	back = block(
		"div", {"textAlign": "center", "margin": "0 0 56px"},
		[block("a", {"color": "#111", "fontWeight": "600", "textDecoration": "underline"},
			inner_html=_("&larr; Back to projects"), name="back-link",
			attributes={"href": "/realisations"})],
		name="prop-back",
	)
	return block("div", {"width": "100%"}, [_style_block(css), hero, body, gallery, back], name="property-page")
