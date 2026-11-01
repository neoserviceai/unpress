# Prototype: convert Elementor `_elementor_data` trees into Frappe Builder
# `blocks` JSON (Unpress PoC, phase 1.3 - tree-to-tree conversion).
#
# Scope: structural fidelity (sections/columns/widgets), content (text, images,
# links) and the most common style settings. Unknown widgets fall back to a
# tagged placeholder block so nothing is silently dropped (rule from the
# EmDash test: no CSS soup in content, explicit leftovers instead).
import json
import secrets
import sys
from collections import Counter
from xml.etree import ElementTree as ET

try:
    from frappe import _
except ImportError:  # standalone prototype run (see __main__): no bench, no i18n
    def _(msg):
        return msg

WXR = "wordpress-export.xml"
NS = {"wp": "http://wordpress.org/export/1.2/"}

stats = Counter()

# Optional live-render data injected by the caller (seed/import) for widgets
# whose data WordPress does not export: {widgetType: [{title, link, img}]}
LIVE_DATA = {}


def gen_id():
    return secrets.token_hex(4)  # 8 hex chars, mirrors frappe.generate_hash(length=8)


def px(value):
    """Elementor size dict -> CSS string."""
    if isinstance(value, dict):
        size = value.get("size")
        unit = value.get("unit", "px")
        if size in (None, ""):
            return None
        if unit == "custom":
            return str(size)
        return f"{size}{unit}"
    if value in (None, ""):
        return None
    return f"{value}px"


def box(value):
    """Elementor spacing dict -> CSS shorthand (top right bottom left)."""
    if not isinstance(value, dict):
        return None
    unit = value.get("unit", "px")
    parts = []
    for side in ("top", "right", "bottom", "left"):
        v = value.get(side)
        parts.append(f"{v}{unit}" if v not in (None, "") else "0px")
    if all(p == "0px" for p in parts):
        return None
    return " ".join(parts)


def map_common_styles(settings, styles):
    """Map the most frequent Elementor style settings to CSS."""
    if not isinstance(settings, dict):
        return
    if box(settings.get("padding")):
        styles["padding"] = box(settings.get("padding"))
    if box(settings.get("margin")):
        styles["margin"] = box(settings.get("margin"))
    if settings.get("background_background") == "classic":
        if settings.get("background_color"):
            styles["background"] = settings["background_color"]
        bg_img = (settings.get("background_image") or {}).get("url")
        if bg_img:
            styles["backgroundImage"] = f"url('{bg_img}')"
            styles["backgroundSize"] = settings.get("background_size", "cover")
            styles["backgroundPosition"] = settings.get("background_position", "center center")
    if settings.get("border_radius"):
        r = box(settings.get("border_radius"))
        if r:
            styles["borderRadius"] = r
    for key in ("align", "text_align"):
        if settings.get(key) in ("left", "center", "right", "justify"):
            styles["textAlign"] = settings[key]


def typo_styles(settings, prefix, styles):
    """Map typography_* / <prefix>_typography settings."""
    color_keys = {"title_color", "color", "text_color", "heading_color"}
    for ck in color_keys:
        if settings.get(ck):
            styles["color"] = settings[ck]
            break
    fs = px(settings.get(f"{prefix}_font_size") or settings.get("typography_font_size"))
    if fs:
        styles["fontSize"] = fs
    fw = settings.get(f"{prefix}_font_weight") or settings.get("typography_font_weight")
    if fw:
        styles["fontWeight"] = str(fw)
    ff = settings.get(f"{prefix}_font_family") or settings.get("typography_font_family")
    if ff:
        styles["fontFamily"] = ff
    lh = px(settings.get(f"{prefix}_line_height") or settings.get("typography_line_height"))
    if lh:
        styles["lineHeight"] = lh


def block(element, styles=None, children=None, inner_html=None, attributes=None,
          classes=None, name=None, extra=None):
    b = {
        "blockId": gen_id(),
        "element": element,
        "baseStyles": styles or {},
        "mobileStyles": {},
        "tabletStyles": {},
        "attributes": attributes or {},
        "classes": classes or [],
        "children": children or [],
    }
    if inner_html is not None:
        b["innerHTML"] = inner_html
    if name:
        b["blockName"] = name
    if extra:
        b.update(extra)
    return b


# --- widget converters ------------------------------------------------------

def conv_heading(s):
    tag = s.get("header_size", "h2")
    styles = {}
    typo_styles(s, "typography", styles)
    map_common_styles(s, styles)
    stats["widget:heading"] += 1
    return block(tag, styles, inner_html=s.get("title", ""), name="heading")


def conv_text_editor(s):
    styles = {}
    typo_styles(s, "typography", styles)
    map_common_styles(s, styles)
    stats["widget:text-editor"] += 1
    return block("div", styles, inner_html=s.get("editor", ""), name="text")


def conv_image(s):
    img = s.get("image") or {}
    styles = {"maxWidth": "100%", "height": "auto"}
    w = px(s.get("width"))
    if w:
        styles["width"] = w
    map_common_styles(s, styles)
    stats["widget:image"] += 1
    return block("img", styles, name="image",
                 attributes={"src": img.get("url", ""), "alt": img.get("alt", "") or ""})


def conv_button(s):
    styles = {"display": "inline-block", "textDecoration": "none",
              "textAlign": "center", "cursor": "pointer"}
    if s.get("background_color"):
        styles["background"] = s["background_color"]
    if s.get("button_text_color"):
        styles["color"] = s["button_text_color"]
    typo_styles(s, "typography", styles)
    if box(s.get("text_padding")):
        styles["padding"] = box(s["text_padding"])
    r = box(s.get("border_radius"))
    if r:
        styles["borderRadius"] = r
    href = (s.get("link") or {}).get("url", "#")
    stats["widget:button"] += 1
    return block("a", styles, inner_html=s.get("text", ""), name="button",
                 attributes={"href": href})


def conv_spacer(s):
    h = px((s.get("space") or {})) or "20px"
    stats["widget:spacer"] += 1
    return block("div", {"height": h}, name="spacer")


def conv_icon(s):
    icon = (s.get("selected_icon") or {}).get("value", "")
    styles = {}
    if s.get("primary_color"):
        styles["color"] = s["primary_color"]
    size = px(s.get("size"))
    if size:
        styles["fontSize"] = size
    stats["widget:icon"] += 1
    # Font Awesome class kept as-is; real app will inline SVG like Elementor does
    return block("span", styles, name="icon", classes=[c for c in icon.split() if c])


def conv_image_box(s):
    img = (s.get("image") or {}).get("url", "")
    children = []
    if img:
        children.append(block("img", {"maxWidth": "100%"}, attributes={"src": img, "alt": ""}))
    if s.get("title_text"):
        tstyles = {}
        typo_styles(s, "title_typography", tstyles)
        children.append(block(s.get("title_size", "h3"), tstyles, inner_html=s["title_text"]))
    if s.get("description_text"):
        children.append(block("p", {}, inner_html=s["description_text"]))
    styles = {"display": "flex", "flexDirection": "column", "gap": "12px"}
    map_common_styles(s, styles)
    stats["widget:image-box"] += 1
    return block("div", styles, children, name="image-box")


def conv_icon_box(s):
    children = []
    icon = (s.get("selected_icon") or {}).get("value", "")
    if icon:
        children.append(block("span", {}, classes=[c for c in icon.split() if c]))
    if s.get("title_text"):
        children.append(block(s.get("title_size", "h3"), {}, inner_html=s["title_text"]))
    if s.get("description_text"):
        children.append(block("p", {}, inner_html=s["description_text"]))
    stats["widget:icon-box"] += 1
    return block("div", {"display": "flex", "flexDirection": "column", "gap": "8px"},
                 children, name="icon-box")


def conv_testimonial(s):
    children = [block("p", {"fontStyle": "italic"}, inner_html=s.get("testimonial_content", ""))]
    img = (s.get("testimonial_image") or {}).get("url", "")
    if img:
        children.append(block("img", {"width": "56px", "borderRadius": "50%"},
                              attributes={"src": img, "alt": ""}))
    if s.get("testimonial_name"):
        children.append(block("strong", {}, inner_html=s["testimonial_name"]))
    if s.get("testimonial_job"):
        children.append(block("span", {"opacity": "0.7"}, inner_html=s["testimonial_job"]))
    stats["widget:testimonial"] += 1
    return block("div", {"display": "flex", "flexDirection": "column", "gap": "8px"},
                 children, name="testimonial")


def conv_counter(s):
    children = [
        block("span", {"fontSize": "40px", "fontWeight": "700"},
              inner_html=str(s.get("ending_number", "0")), name="counter-number"),
    ]
    if s.get("title"):
        children.append(block("span", {}, inner_html=s["title"]))
    stats["widget:counter"] += 1
    return block("div", {"display": "flex", "flexDirection": "column"}, children, name="counter")


def conv_google_maps(s):
    addr = s.get("address", "")
    src = f"https://maps.google.com/maps?q={addr}&t=m&z=15&output=embed&iwloc=near"
    stats["widget:google_maps"] += 1
    return block("iframe", {"width": "100%", "height": px(s.get("height")) or "300px",
                            "border": "none"},
                 attributes={"src": src, "loading": "lazy"}, name="map")


def conv_video(s):
    url = s.get("youtube_url") or s.get("vimeo_url") or ""
    stats["widget:video"] += 1
    return block("iframe", {"width": "100%", "aspectRatio": "16/9", "border": "none"},
                 attributes={"src": url}, name="video")


WIDGETS = {
    "heading": conv_heading,
    "text-editor": conv_text_editor,
    "image": conv_image,
    "button": conv_button,
    "spacer": conv_spacer,
    "icon": conv_icon,
    "image-box": conv_image_box,
    "icon-box": conv_icon_box,
    "testimonial": conv_testimonial,
    "counter": conv_counter,
    "google_maps": conv_google_maps,
    "video": conv_video,
}


def conv_expanding_cards(el):
    from .components import build_expanding_cards

    items = LIVE_DATA.get("ucaddon_expanding_content_cards")
    if not items:
        return conv_unknown(el)
    stats["widget:expanding-cards(rebuilt)"] += 1
    return build_expanding_cards(items[:10], uid=el.get("id", "ecc"))


def conv_post_grid(el):
    from .components import build_post_grid

    items = LIVE_DATA.get("ucaddon_post_grid")
    if not items:
        return conv_unknown(el)
    stats["widget:post-grid(rebuilt)"] += 1
    return build_post_grid(items, uid=el.get("id", "grid"))


def conv_lottie_silent(el):
    # decorative animation: keep a hidden marker instead of a loud placeholder
    stats["widget:lottie(hidden)"] += 1
    return block("div", {"display": "none"}, name="todo-lottie",
        extra={"customAttributes": {"data-unpress-todo": "lottie"}})


def conv_unknown(el):
    """Placeholder for widgets needing a dedicated Builder component."""
    wtype = el.get("widgetType", "?")
    stats[f"TODO:{wtype}"] += 1
    return block("div", {"padding": "24px", "border": "2px dashed #f59e0b",
                         "background": "#fef3c7", "color": "#92400e"},
                 inner_html=_('[Unpress TODO] widget "{0}" to rebuild as a Builder component').format(wtype),
                 name=f"todo-{wtype}",
                 extra={"customAttributes": {"data-unpress-todo": wtype}})


def conv_column(el):
    s = el.get("settings") or {}
    styles = {"display": "flex", "flexDirection": "column", "gap": "10px",
              "flexShrink": "0"}
    size = s.get("_column_size") or 100
    inline = s.get("_inline_size")
    width = inline if inline not in (None, "") else size
    styles["width"] = f"{width}%"
    map_common_styles(s, styles)
    children = [convert(c) for c in el.get("elements", [])]
    stats["column"] += 1
    b = block("div", styles, children, name="column")
    # responsive: columns stack on mobile
    b["mobileStyles"] = {"width": "100%"}
    return b


def conv_section(el):
    s = el.get("settings") or {}
    inner = {"display": "flex", "flexDirection": "row", "gap": "20px",
             "maxWidth": "1140px", "margin": "0 auto", "width": "100%"}
    outer = {"display": "flex", "width": "100%"}
    map_common_styles(s, outer)
    if s.get("min_height"):
        outer["minHeight"] = px(s["min_height"]) or ""
    children = [convert(c) for c in el.get("elements", [])]
    row = block("div", inner, children, name="section-row")
    row["mobileStyles"] = {"flexDirection": "column"}
    stats["section"] += 1
    return block("section", outer, [row], name="section")


def convert(el):
    el_type = el.get("elType")
    if el_type == "section":
        return conv_section(el)
    if el_type in ("column", "container"):
        return conv_column(el)
    if el_type == "widget":
        wtype = el.get("widgetType", "")
        if wtype == "ucaddon_expanding_content_cards":
            return conv_expanding_cards(el)
        if wtype == "ucaddon_post_grid":
            return conv_post_grid(el)
        if wtype == "lottie":
            return conv_lottie_silent(el)
        conv = WIDGETS.get(wtype)
        if conv:
            return conv(el.get("settings") or {})
        return conv_unknown(el)
    stats[f"skip:{el_type}"] += 1
    return conv_unknown(el)


def load_page(title_wanted):
    tree = ET.parse(WXR)
    for item in tree.getroot().findall("./channel/item"):
        title = item.findtext("title", default="")
        ptype = item.findtext("wp:post_type", default="", namespaces=NS)
        if title == title_wanted and ptype == "page":
            for meta in item.findall("wp:postmeta", NS):
                if meta.findtext("wp:meta_key", default="", namespaces=NS) == "_elementor_data":
                    return json.loads(meta.findtext("wp:meta_value", default="[]", namespaces=NS))
    raise SystemExit(f"page not found: {title_wanted}")


if __name__ == "__main__":
    page_title = sys.argv[1] if len(sys.argv) > 1 else "A propos"
    elementor_tree = load_page(page_title)
    builder_blocks = [convert(el) for el in elementor_tree]
    # Builder root: single wrapping container (matches editor expectations)
    root = block("div", {"display": "flex", "flexDirection": "column",
                         "alignItems": "center", "width": "100%"},
                 builder_blocks, name="root")
    out = f"builder-blocks-{page_title.replace(' ', '-').lower()}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump([root], f, ensure_ascii=False, indent="\t")
    print(f"OK -> {out}")
    print(json.dumps(dict(stats), indent=2, ensure_ascii=False))
