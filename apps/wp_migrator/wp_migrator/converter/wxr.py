# WXR (WordPress eXtended RSS) parser.
# Extracts pages/templates (with _elementor_data), attachments and menus
# from a WordPress export file. Pure functions, no Frappe dependency.
import json
from xml.etree import ElementTree as ET

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _postmeta(item, key):
    for meta in item.findall("wp:postmeta", NS):
        if meta.findtext("wp:meta_key", default="", namespaces=NS) == key:
            return meta.findtext("wp:meta_value", default="", namespaces=NS)
    return None


def parse_wxr(xml_text):
    """Parse a WXR string into a normalized structure.

    Returns dict with keys: site, pages, templates, attachments, other_counts.
    Elementor JSON is parsed leniently (real-world exports contain raw
    control characters — lesson from a real export).
    """
    root = ET.fromstring(xml_text)
    channel = root.find("channel")

    result = {
        "site": {
            "title": channel.findtext("title", default=""),
            "url": channel.findtext("wp:base_site_url", default="", namespaces=NS),
            "language": channel.findtext("language", default=""),
        },
        "pages": [],
        "templates": [],
        "attachments": [],
        "menu": [],
        "other_counts": {},
    }

    for item in channel.findall("item"):
        post_type = item.findtext("wp:post_type", default="", namespaces=NS)
        status = item.findtext("wp:status", default="", namespaces=NS)

        if post_type == "attachment":
            result["attachments"].append(
                {
                    "wp_id": item.findtext("wp:post_id", default="", namespaces=NS),
                    "title": item.findtext("title", default="") or "",
                    "url": item.findtext("wp:attachment_url", default="", namespaces=NS),
                }
            )
            continue

        if post_type == "nav_menu_item":
            result["menu"].append(
                {
                    "order": int(item.findtext("wp:menu_order", default="0", namespaces=NS) or 0),
                    "label": (item.findtext("title", default="") or "").strip(),
                    "object": _postmeta(item, "_menu_item_object"),
                    "object_id": _postmeta(item, "_menu_item_object_id"),
                    "url": _postmeta(item, "_menu_item_url") or "",
                }
            )
            continue

        if post_type in ("page", "elementor_library"):
            edata_raw = _postmeta(item, "_elementor_data")
            edata = None
            if edata_raw and edata_raw.strip() and edata_raw.strip() != "[]":
                try:
                    edata = json.loads(edata_raw, strict=False)
                except json.JSONDecodeError:
                    edata = None
            entry = {
                "wp_id": item.findtext("wp:post_id", default="", namespaces=NS),
                "title": item.findtext("title", default="") or "(sans titre)",
                "slug": item.findtext("wp:post_name", default="", namespaces=NS),
                "status": status,
                "content_html": item.findtext("content:encoded", default="", namespaces=NS) or "",
                "elementor_data": edata,
                "template_type": _postmeta(item, "_elementor_template_type"),
            }
            if post_type == "page":
                result["pages"].append(entry)
            else:
                result["templates"].append(entry)
            continue

        result["other_counts"][post_type] = result["other_counts"].get(post_type, 0) + 1

    result["menu"].sort(key=lambda m: m["order"])
    return result
