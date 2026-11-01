"""
Match real client photos to generated page image slots.

After pages are generated they carry placeholder images (placehold.co). This
module replaces those placeholders with the client's OWN photos — drawn from
the understood `Builder Content Asset` library — picking the best photo per
slot by section, slot type, orientation, quality and keyword overlap.

Flux image generation (builder.api._generate_images_worker) stays as the
fallback for slots no real photo fits. The matcher is fast (DB + block edits,
no LLM/Flux call) and is NOT gated by the Flux `image_generation_enabled` flag.
"""

import json
import re

import frappe
from frappe import _

from unpress_core.ai.logging import ai_log


# Route/title keyword → canonical page section.
SECTION_KEYWORDS = {
    "accueil": "home", "home": "home", "index": "home",
    "propos": "about", "about": "about", "histoire": "about", "entreprise": "about", "qui-sommes": "about",
    "service": "services", "prestation": "services", "expertise": "services", "metier": "services",
    "galerie": "gallery", "gallery": "gallery", "realisation": "gallery", "projet": "gallery", "portfolio": "gallery",
    "equipe": "team", "team": "team",
    "contact": "contact",
    "tarif": "pricing", "pricing": "pricing", "prix": "pricing",
}

# Which asset slots are acceptable for a given page slot (best-first).
SLOT_COMPAT = {
    "hero": ["hero", "background", "gallery"],
    "background": ["background", "hero", "gallery"],
    "gallery": ["gallery", "service", "detail", "hero"],
    "team": ["team", "gallery"],
}


def _page_section(meta: dict) -> str:
    hay = f"{meta.get('route') or ''} {meta.get('page_title') or ''}".lower()
    for kw, sec in SECTION_KEYWORDS.items():
        if kw in hay:
            return sec
    return "home"


def _dims(size: str):
    m = re.match(r"(\d+)x(\d+)", size or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _slot_type(size: str, img_type: str) -> str:
    if img_type == "background":
        return "background"
    w, h = _dims(size)
    if not w:
        return "gallery"
    if w >= 1000 and w >= h:
        return "hero"
    if abs(w - h) <= max(w, h) * 0.15:
        return "team"  # ~square content slot (avatars < 200px are skipped upstream)
    return "gallery"


def _orientation(size: str) -> str:
    w, h = _dims(size)
    if not w:
        return "landscape"
    if abs(w - h) <= max(w, h) * 0.1:
        return "square"
    return "landscape" if w > h else "portrait"


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-zàâçéèêëîïôûùüœ]{4,}", (text or "").lower()))


def _score(slot: dict, asset: dict, reuse_count: int) -> float:
    score = 0.0
    a_slots = [s.strip() for s in (asset.get("suggested_slots") or "").split(",") if s.strip()]
    a_section = (asset.get("suggested_section") or "generic").lower()

    # Section affinity
    if a_section == slot["section"]:
        score += 3
    elif a_section == "generic":
        score += 1

    # Slot-type affinity
    compat = SLOT_COMPAT.get(slot["slot_type"], [slot["slot_type"]])
    if slot["slot_type"] in a_slots:
        score += 3
    elif any(c in a_slots for c in compat):
        score += 1.5

    # Orientation
    if (asset.get("orientation") or "") == slot["orientation"]:
        score += 2

    # Quality (and never put a low-quality photo in a hero/background)
    quality = asset.get("quality") or "medium"
    score += {"high": 2, "medium": 1, "low": -1}.get(quality, 0)
    if slot["slot_type"] in ("hero", "background") and quality == "low":
        score -= 5

    # Semantic overlap between the slot's alt/context and the photo's keywords
    overlap = _tokens(slot["context"]) & (_tokens(asset.get("tags")) | _tokens(asset.get("vision_description")))
    score += min(len(overlap), 3)

    # Discourage overusing the same photo
    score -= reuse_count * 1.5
    return score


def match_and_apply(session_id: str, page_names: list = None, min_score: float = 2.5) -> dict:
    """Replace placeholder image slots in the session's pages with the best
    matching client photos. Returns a coverage report. Slots with no good
    match are left as placeholders (Flux can fill them afterwards)."""
    from unpress_core.generation import _scan_placeholder_images, _replace_image_in_page

    assets = frappe.get_all(
        "Builder Content Asset",
        filters={"session_id": session_id, "asset_type": "Image", "status": ["in", ["understood", "used"]]},
        fields=["name", "file", "suggested_section", "suggested_slots",
                "orientation", "quality", "tags", "vision_description"],
    )
    # Logos are brand chrome, not page content.
    assets = [a for a in assets if "logo" not in (a.get("suggested_slots") or "").lower()]
    if not assets:
        return {"matched": 0, "slots": 0, "assets": 0, "message": "no client images"}

    if not page_names:
        session = frappe.get_doc("Builder Chat Session", {"session_id": session_id})
        pages = json.loads(session.generated_pages) if session.generated_pages else []
        page_names = [p["name"] for p in pages if p.get("name")]
    if not page_names:
        return {"matched": 0, "slots": 0, "assets": len(assets), "message": "no pages"}

    raw_slots = _scan_placeholder_images(page_names)
    if not raw_slots:
        return {"matched": 0, "slots": 0, "assets": len(assets), "message": "no placeholders"}

    page_meta = {
        pn: (frappe.db.get_value("Builder Page", pn, ["route", "page_title"], as_dict=True) or {})
        for pn in {s["page_name"] for s in raw_slots}
    }

    slots = []
    for s in raw_slots:
        slots.append({
            **s,
            "section": _page_section(page_meta.get(s["page_name"], {})),
            "slot_type": _slot_type(s["size"], s["type"]),
            "orientation": _orientation(s["size"]),
            "context": s.get("alt", ""),
        })

    # Fill the most important slots first.
    priority = {"hero": 0, "background": 1, "gallery": 2, "team": 3}
    slots.sort(key=lambda s: priority.get(s["slot_type"], 9))

    reuse = {}
    matched = 0
    report = []
    for slot in slots:
        best, best_score = None, min_score
        for asset in assets:
            sc = _score(slot, asset, reuse.get(asset["name"], 0))
            if sc > best_score:
                best, best_score = asset, sc
        if not best:
            continue
        _replace_image_in_page(slot["page_name"], slot["block_id"], best["file"], img_type=slot["type"])
        reuse[best["name"]] = reuse.get(best["name"], 0) + 1
        matched += 1
        report.append({
            "page": slot["page_name"],
            "slot": slot["slot_type"],
            "section": slot["section"],
            "asset": best["name"],
            "file": best["file"],
            "score": round(best_score, 1),
        })

    frappe.db.commit()
    ai_log("info", "Client photos matched to page slots",
           session=session_id, matched=matched, slots=len(slots), assets=len(assets))
    return {
        "matched": matched,
        "slots": len(slots),
        "assets": len(assets),
        "unmatched": len(slots) - matched,
        "report": report,
    }


@frappe.whitelist()
def chat_apply_client_images(session_id: str) -> dict:
    """Whitelisted entry: place the client's real photos into the generated
    pages. Synchronous and fast; not gated by the Flux image flag."""
    if not session_id:
        frappe.throw(_("Session ID is required"))
    result = match_and_apply(session_id)
    result["success"] = True
    return result
