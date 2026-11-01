"""
Existing-site extractor — seed the brief from a client's CURRENT website.

Inspired by the AI-website-cloner inspection methodology (design-token
extraction), but for OUR goal: we don't clone pixel-for-pixel — we lift the
real signal (palette, fonts, radius, headings, copy + a screenshot) from the
client's existing site and feed it to the brief, so generation starts from
their real identity instead of inventing one.

Reuses Playwright (already used by WebsiteScreenshotter). Server-side only.
"""

import colorsys
import re

import frappe
from frappe import _

from unpress_core.ai.logging import ai_log


# JS run in the page to collect design tokens + content via getComputedStyle.
_COLLECT_JS = r"""
() => {
  const bg = {}, fg = {}, bd = {};
  const bump = (m, c) => {
    if (!c || c === 'transparent' || c.startsWith('rgba(0, 0, 0, 0')) return;
    m[c] = (m[c] || 0) + 1;
  };
  let n = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (n++ > 4000) break;
    const r = el.getBoundingClientRect();
    if (r.width < 3 || r.height < 3) continue;
    const s = getComputedStyle(el);
    bump(bg, s.backgroundColor); bump(fg, s.color); bump(bd, s.borderColor);
  }
  const font = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).fontFamily : ''; };
  const btn = document.querySelector('button, .btn, a.button, [class*="btn"]');
  const headings = [...document.querySelectorAll('h1, h2, h3')]
    .map(h => (h.innerText || '').trim()).filter(Boolean).slice(0, 15);
  return {
    bg, fg, bd,
    headingFont: font('h1') || font('h2') || font('h3'),
    bodyFont: font('p') || font('body'),
    radius: btn ? getComputedStyle(btn).borderRadius : '',
    headings,
    title: document.title || '',
    text: (document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 6000),
  };
}
"""


def _to_hex(css_color: str):
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", css_color or "")
    if not m:
        return None
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    return f"#{r:02x}{g:02x}{b:02x}"


def _hsl(hex_color: str):
    raw = hex_color.lstrip("#")
    r, g, b = (int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, lightness


def _derive_palette(color_counts: dict) -> list:
    """Pick up to 2 brand colors: most-frequent SATURATED, non-neutral colors,
    distinct in hue. Neutrals (grey/white/black) are skipped — they're chrome."""
    scored = []
    for css, count in color_counts.items():
        hexv = _to_hex(css)
        if not hexv:
            continue
        h, s, lightness = _hsl(hexv)
        if s < 0.2 or lightness > 0.92 or lightness < 0.08:
            continue  # neutral / near-white / near-black
        scored.append((count, h, hexv))
    scored.sort(reverse=True)
    palette, hues = [], []
    for _, h, hexv in scored:
        if all(min(abs(h - hh), 1 - abs(h - hh)) > 0.08 for hh in hues):
            palette.append(hexv)
            hues.append(h)
        if len(palette) >= 2:
            break
    return palette


def _first_font(font_family: str) -> str:
    if not font_family:
        return ""
    first = font_family.split(",")[0].strip().strip('"').strip("'")
    return first


def _radius_style(radius: str) -> str:
    m = re.match(r"(\d+)", radius or "")
    if not m:
        return ""
    px = int(m.group(1))
    if px >= 9999 or px >= 40:
        return "pill"
    if px >= 10:
        return "rounded"
    if px >= 3:
        return "subtle"
    return "none"


def extract_site(url: str, timeout: int = 30000) -> dict:
    """Load a live site and extract brand tokens + content + a screenshot.

    Returns: {palette[], heading_font, body_font, radius_style, headings[],
    text, screenshot (bytes), title}. Raises on Playwright/browser errors.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("Playwright required: pip install playwright && playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(url, timeout=timeout, wait_until="networkidle")
            page.wait_for_timeout(800)
            data = page.evaluate(_COLLECT_JS)
            shot = page.screenshot(full_page=False, type="png")
        finally:
            browser.close()

    all_colors = {}
    for bucket in ("bg", "fg", "bd"):
        for css, cnt in (data.get(bucket) or {}).items():
            all_colors[css] = all_colors.get(css, 0) + cnt

    result = {
        "url": url,
        "title": data.get("title", ""),
        "palette": _derive_palette(all_colors),
        "heading_font": _first_font(data.get("headingFont", "")),
        "body_font": _first_font(data.get("bodyFont", "")),
        "radius_style": _radius_style(data.get("radius", "")),
        "headings": data.get("headings", []),
        "text": data.get("text", ""),
        "screenshot": shot,
    }
    ai_log("info", "Existing-site extraction",
           url=url, palette=result["palette"],
           heading_font=result["heading_font"], chars=len(result["text"]))
    return result


@frappe.whitelist()
def import_existing_site(url: str, session_id: str = None) -> dict:
    """Whitelisted: extract a client's existing site and seed the session brief
    (palette + fonts) + store its content as a Builder Content Asset + the
    screenshot as design inspiration. The 'we already have a site' path."""
    if not url:
        frappe.throw(_("A site URL is required"))
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    data = extract_site(url)

    # 1) Screenshot → public File (design reference / brief vision)
    screenshot_url = None
    try:
        fdoc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"existing_site_{frappe.generate_hash(length=6)}.png",
            "is_private": 0,
            "content": data["screenshot"],
        }).insert(ignore_permissions=True)
        screenshot_url = fdoc.file_url
    except Exception as e:
        ai_log("warning", "Existing-site screenshot save failed", error=str(e)[:150])

    # 2) Content → a Builder Content Asset (Document, already understood)
    if session_id and data.get("text"):
        asset = frappe.new_doc("Builder Content Asset")
        asset.session_id = session_id
        asset.asset_type = "Document"
        asset.original_filename = f"{data.get('title') or url}"
        asset.status = "understood"
        asset.suggested_section = "home"
        asset.summary = (data.get("title") or "")[:240]
        asset.extracted_text = ("\n".join(data.get("headings", [])) + "\n\n" + data.get("text", ""))[:140000]
        asset.tags = "existing-site"
        if screenshot_url:
            asset.file = screenshot_url
        asset.insert(ignore_permissions=True)

    # 3) Seed brief palette/fonts on the session (set-if-absent — don't clobber
    #    explicit user choices made earlier in the chat)
    if session_id:
        sess = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
        palette = data.get("palette") or []
        if palette and not sess.primary_color:
            sess.primary_color = palette[0]
        if len(palette) >= 2 and not sess.secondary_color:
            sess.secondary_color = palette[1]
        if data.get("heading_font") and not sess.heading_font:
            sess.heading_font = data["heading_font"]
        if data.get("body_font") and not sess.body_font:
            sess.body_font = data["body_font"]
        if screenshot_url:
            existing = frappe.parse_json(sess.inspiration_urls) if sess.inspiration_urls else []
            existing.append({"url": screenshot_url, "name": data.get("title") or url, "type": "existing_site"})
            sess.inspiration_urls = frappe.as_json(existing)
        sess.save(ignore_permissions=True)
        frappe.db.commit()

    return {
        "success": True,
        "title": data.get("title"),
        "palette": data.get("palette"),
        "heading_font": data.get("heading_font"),
        "body_font": data.get("body_font"),
        "radius_style": data.get("radius_style"),
        "headings": data.get("headings", [])[:8],
        "text_chars": len(data.get("text", "")),
        "screenshot_url": screenshot_url,
    }
