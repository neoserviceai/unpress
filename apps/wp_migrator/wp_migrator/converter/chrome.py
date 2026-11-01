# Site chrome (header/footer) for the clean upstream base: built as Builder
# Components so the whole site shares ONE editable header and footer — edit
# the component in the Builder and every page updates. This replaces the
# legacy header/footer subsystem the v15 branch of this Builder fork carried.
from wp_migrator.converter.elementor import block

HEADER_COMPONENT_ID = "unpress-site-header"
FOOTER_COMPONENT_ID = "unpress-site-footer"

ACCENT = "#6d5cf5"


def build_header_block(menu_items, logo_url=None, cta=None, site_name=""):
	"""menu_items: [{label, url}], cta: {label, url} | None."""
	brand_children = []
	if logo_url:
		brand_children.append(
			block("img", {"height": "38px", "width": "auto"}, name="logo",
				attributes={"src": logo_url, "alt": site_name or "logo"})
		)
	else:
		brand_children.append(
			block("span", {"fontSize": "22px", "fontWeight": "700", "color": "#ffffff"},
				inner_html=site_name or "Mon site", name="brand")
		)

	links = [
		block("a", {"color": "#ffffff", "fontSize": "15px", "textDecoration": "none", "opacity": "0.9"},
			inner_html=item["label"], name=f"nav-{i}", attributes={"href": item["url"]})
		for i, item in enumerate(menu_items)
	]

	right = [block("nav", {"display": "flex", "gap": "26px", "alignItems": "center"}, links, name="nav")]
	if cta:
		right.append(
			block("a", {"background": ACCENT, "color": "#ffffff", "padding": "10px 22px",
				"borderRadius": "999px", "fontSize": "14px", "fontWeight": "600",
				"textDecoration": "none", "marginLeft": "10px"},
				inner_html=cta["label"], name="cta", attributes={"href": cta["url"]})
		)

	return block(
		"header",
		{"display": "flex", "justifyContent": "space-between", "alignItems": "center",
			"width": "100%", "padding": "14px 40px", "background": "#111111",
			"position": "sticky", "top": "0px", "zIndex": "50"},
		[
			block("a", {"display": "flex", "alignItems": "center"}, brand_children,
				name="brand-link", attributes={"href": "/"}),
			block("div", {"display": "flex", "alignItems": "center"}, right, name="header-right"),
		],
		name="site-header",
	)


def build_footer_block(menu_items, contacts, logo_url=None, site_name="", copyright_text=""):
	"""contacts: [{label, href}] (mailto:/tel:)."""
	cols = []

	brand = []
	if logo_url:
		brand.append(block("img", {"height": "30px", "width": "auto", "opacity": "0.9"},
			name="footer-logo", attributes={"src": logo_url, "alt": site_name}))
	elif site_name:
		brand.append(block("div", {"fontSize": "18px", "fontWeight": "700", "color": "#ffffff"},
			inner_html=site_name, name="footer-brand"))
	cols.append(block("div", {"display": "flex", "flexDirection": "column", "gap": "12px"}, brand, name="footer-col-brand"))

	if menu_items:
		cols.append(block(
			"nav", {"display": "flex", "flexDirection": "column", "gap": "8px"},
			[block("a", {"color": "#d4d4d8", "fontSize": "14px", "textDecoration": "none"},
				inner_html=i["label"], name=f"footer-nav-{n}", attributes={"href": i["url"]})
				for n, i in enumerate(menu_items)],
			name="footer-col-nav",
		))

	if contacts:
		cols.append(block(
			"div", {"display": "flex", "flexDirection": "column", "gap": "8px"},
			[block("a", {"color": "#d4d4d8", "fontSize": "14px", "textDecoration": "none"},
				inner_html=c["label"], name=f"footer-contact-{n}", attributes={"href": c["href"]})
				for n, c in enumerate(contacts)],
			name="footer-col-contact",
		))

	return block(
		"footer",
		{"width": "100%", "background": "#111111", "padding": "48px 40px 28px"},
		[
			block("div", {"display": "flex", "justifyContent": "space-between", "gap": "40px",
				"flexWrap": "wrap", "maxWidth": "1100px", "margin": "0 auto"}, cols, name="footer-cols"),
			block("div", {"textAlign": "center", "color": "#71717a", "fontSize": "12.5px",
				"marginTop": "36px"}, inner_html=copyright_text, name="footer-copyright"),
		],
		name="site-footer",
	)


def _mirror_children(node, prefix):
	"""extend_block() rebuilds a component's children FROM the reference
	block's children (matched by referenceBlockId) — so a reference must
	carry a structural mirror of the component tree, like the Builder UI
	creates when a component is dropped on a page."""
	return [
		{
			"blockId": f"{prefix}-{child['blockId']}",
			"referenceBlockId": child["blockId"],
			"children": _mirror_children(child, prefix),
		}
		for child in (node.get("children") or [])
	]


def component_ref(component_id, block_id, component_tree):
	"""A page block that renders a Builder Component."""
	return {
		"blockId": block_id,
		"extendedFromComponent": component_id,
		"children": _mirror_children(component_tree, block_id),
	}
