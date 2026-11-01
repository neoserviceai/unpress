# Widget inventory from a WXR export containing _elementor_data postmeta.
# Phase 1.2 of the Unpress PoC: quantify mechanical vs agentic conversion work.
import json
import re
import sys
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

WXR = "wordpress-export.xml"

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

# Elementor core (free) widgets — mechanical conversion expected
CORE_FREE = {
    "heading", "image", "text-editor", "video", "button", "divider", "spacer",
    "google_maps", "icon", "icon-box", "image-box", "image-gallery",
    "image-carousel", "icon-list", "counter", "progress", "testimonial",
    "tabs", "accordion", "toggle", "social-icons", "alert", "audio",
    "shortcode", "html", "menu-anchor", "sidebar", "read-more", "text-path",
    "rating", "inner-section", "container",
}
# Elementor Pro widgets — mechanical-ish (need a Builder equivalent per widget)
CORE_PRO = {
    "form", "posts", "portfolio", "slides", "nav-menu", "animated-headline",
    "price-list", "price-table", "flip-box", "call-to-action",
    "media-carousel", "testimonial-carousel", "countdown", "share-buttons",
    "blockquote", "login", "search-form", "sitemap", "table-of-contents",
    "lottie", "code-highlight", "hotspot", "video-playlist",
    "progress-tracker", "mega-menu", "loop-grid", "loop-carousel",
    "theme-post-title", "theme-post-content", "theme-post-excerpt",
    "theme-post-featured-image", "theme-site-logo", "theme-site-title",
    "theme-page-title", "theme-archive-title", "archive-posts",
    "breadcrumbs", "post-navigation", "post-comments", "author-box",
    "post-info", "global", "template",
}
ADDON_PREFIXES = {
    "ucaddon_": "Unlimited Elements",
    "uael-": "Ultimate Addons",
    "eael-": "Essential Addons",
    "elementskit-": "ElementsKit",
    "ekit-": "ElementsKit",
    "premium-": "Premium Addons",
    "marvy-": "Marvy",
    "mvy-": "Marvy",
}


def classify(widget_type):
    if widget_type in CORE_FREE:
        return "core-free"
    if widget_type in CORE_PRO:
        return "core-pro"
    for prefix, addon in ADDON_PREFIXES.items():
        if widget_type.startswith(prefix):
            return f"addon:{addon}"
    return "unknown"


def walk(elements, page_counter, structure_counter):
    for el in elements or []:
        el_type = el.get("elType")
        if el_type == "widget":
            page_counter[el.get("widgetType", "?")] += 1
        else:
            structure_counter[el_type or "?"] += 1
        walk(el.get("elements"), page_counter, structure_counter)


tree = ET.parse(WXR)
root = tree.getroot()
items = root.findall("./channel/item")

pages = {}          # title -> Counter of widgets
structures = Counter()
post_types = Counter()
statuses = defaultdict(Counter)

for item in items:
    post_type = item.findtext("wp:post_type", default="?", namespaces=NS)
    status = item.findtext("wp:status", default="?", namespaces=NS)
    post_types[post_type] += 1
    statuses[post_type][status] += 1
    if post_type not in ("page", "elementor_library"):
        continue
    title = item.findtext("title", default="(sans titre)") or "(sans titre)"
    edata = None
    for meta in item.findall("wp:postmeta", NS):
        if meta.findtext("wp:meta_key", default="", namespaces=NS) == "_elementor_data":
            edata = meta.findtext("wp:meta_value", default="", namespaces=NS)
            break
    if not edata or not edata.strip() or edata.strip() == "[]":
        continue
    try:
        blocks = json.loads(edata)
    except json.JSONDecodeError as e:
        print(f"!! JSON invalide pour {title}: {e}", file=sys.stderr)
        continue
    counter = Counter()
    label = f"{title} [{post_type}/{status}]"
    walk(blocks, counter, structures)
    pages[label] = counter

# --- report ---
print("## Post types dans l'export\n")
for pt, count in post_types.most_common():
    st = ", ".join(f"{s}:{c}" for s, c in statuses[pt].most_common())
    print(f"- {pt}: {count} ({st})")

all_widgets = Counter()
for c in pages.values():
    all_widgets.update(c)

print(f"\n## Structure totale : {dict(structures)}")
print(f"\n## Widgets par type ({sum(all_widgets.values())} widgets, {len(all_widgets)} types)\n")
print("| Widget | Occurrences | Classe |")
print("|---|---|---|")
for w, count in all_widgets.most_common():
    print(f"| {w} | {count} | {classify(w)} |")

by_class = Counter()
for w, count in all_widgets.items():
    by_class[classify(w)] += count
total = sum(by_class.values())
print(f"\n## Répartition par classe ({total} widgets)\n")
for cl, count in by_class.most_common():
    print(f"- {cl}: {count} ({100 * count / total:.0f} %)")

print("\n## Détail par page/template\n")
for label, counter in sorted(pages.items(), key=lambda kv: -sum(kv[1].values())):
    widgets = ", ".join(f"{w}×{c}" for w, c in counter.most_common())
    print(f"- **{label}** ({sum(counter.values())} widgets) : {widgets}")
