"""
Visual verification loop — the second half: see → critique → FIX → re-check.

For a generated page: screenshot it server-side, critique the screenshot with a
vision model (Nora — fast/free), turn the actionable defects into a targeted
block revision (page code model), save, re-render and re-critique. Up to a few
iterations, stopping as soon as the page reads as professional.

Site-chrome defects (header/footer/logo/nav) are skipped here — they live in the
Website Header Footer Config, not in the page blocks.
"""

import json

import frappe
from frappe import _

from unpress_core.ai.config import get_ai_settings
from unpress_core.ai.logging import ai_log
from unpress_core.ai.ingestion.visual_critique import critique_screenshot


# Critique areas the page-block revision cannot fix (they're site chrome).
CHROME_AREAS = ("header", "footer", "nav", "logo", "menu")


def _page_url(page_name: str) -> str:
    route = frappe.db.get_value("Builder Page", page_name, "route") or ""
    return frappe.utils.get_url().rstrip("/") + "/" + route.lstrip("/")


def _actionable(critique) -> list:
    """High/medium issues that belong to the page body (not site chrome)."""
    out = []
    for i in critique.issues:
        if i.severity not in ("high", "medium"):
            continue
        if any(c in (i.area or "").lower() for c in CHROME_AREAS):
            continue
        out.append({"area": i.area, "severity": i.severity, "problem": i.problem, "fix": i.fix})
    return out


def refine_page(page_name: str, max_iterations: int = 2, critique_with: str = "nora",
                session_id: str = None, design_brief=None, primary: str = None,
                secondary: str = None) -> dict:
    """Run the see→critique→fix→recheck loop on one page. Returns a report.

    When session_id is given, the saved brief and the ingested real content are
    loaded and fed to the revision, so fixes use real copy (not generic filler).
    """
    from unpress_core.ai.generators.page_generator import PageGenerator
    from unpress_core.ai.inspiration.screenshotter import capture_website_screenshot
    from unpress_core.ai.ingestion.content_understanding import get_content_context
    from unpress_core.generation import _blocks_fingerprint

    cfg = get_ai_settings()
    gen = PageGenerator(config=cfg)

    # Load brief + palette from the session so revisions stay on-brand.
    if session_id and not design_brief:
        sess = frappe.db.get_value(
            "Builder Chat Session", {"session_id": session_id},
            ["saved_brief", "primary_color", "secondary_color"], as_dict=True)
        if sess:
            primary = primary or sess.primary_color
            secondary = secondary or sess.secondary_color
            if sess.saved_brief:
                try:
                    from unpress_core.ai.schemas.design_brief import DesignBrief
                    design_brief = DesignBrief(**json.loads(sess.saved_brief))
                except Exception:
                    pass

    url = _page_url(page_name)
    report = {"page": page_name, "url": url, "iterations": [], "fixed": 0}

    for it in range(max_iterations):
        shot = capture_website_screenshot(url, full_page=False)
        frappe.db.commit()  # persist the screenshot File so the vision model can read it
        if not shot.get("success"):
            report["error"] = "screenshot failed"
            break

        critique, label = critique_screenshot(shot["file_url"], which=critique_with)
        actionable = _actionable(critique)
        report["iterations"].append({
            "iteration": it,
            "critic": label,
            "professional": critique.looks_professional,
            "issues": len(critique.issues),
            "actionable": len(actionable),
            "overall": (critique.overall or "")[:200],
            "problems": [f"[{a['severity']}] {a['area']}: {a['problem'][:90]}" for a in actionable],
        })

        if not actionable:
            break  # clean (or only chrome-level issues left)

        page = frappe.get_doc("Builder Page", page_name)
        blocks = json.loads(page.blocks or "[]")
        real_content = ""
        if session_id:
            try:
                real_content = get_content_context(session_id, page.route or page.page_title)
            except Exception:
                real_content = ""
        revised = gen.revise_blocks(blocks, actionable, design_brief=design_brief,
                                    primary=primary, secondary=secondary,
                                    page_title=page.page_title, real_content=real_content)
        new_json = json.dumps(revised, ensure_ascii=False)
        if new_json == json.dumps(blocks, ensure_ascii=False):
            ai_log("info", "Revision produced no change — stopping loop", page=page_name)
            break
        # Save via the doc so Builder regenerates the published page; keep the
        # AI stamp so the page stays "untouched AI" for the replace policy.
        page.blocks = new_json
        page.draft_blocks = new_json
        page.save(ignore_permissions=True)
        frappe.db.set_value("Builder Page", page_name, "ai_blocks_hash",
                            _blocks_fingerprint(new_json), update_modified=False)
        frappe.db.commit()
        frappe.clear_cache()
        report["fixed"] += len(actionable)

    return report


@frappe.whitelist()
def chat_refine_page(page_name: str, max_iterations: int = 2, session_id: str = None) -> dict:
    """Whitelisted entry: run the visual refinement loop on one page."""
    if not page_name:
        frappe.throw(_("page_name is required"))
    return refine_page(page_name, int(max_iterations), session_id=session_id)
