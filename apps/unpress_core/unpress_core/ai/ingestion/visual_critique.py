"""
Visual verification loop — a vision model reviews a SCREENSHOT of a generated
page and reports concrete visible problems, so the generator can fix them
("the LLM sees what it made").

Screenshots are captured server-side via WebsiteScreenshotter (Playwright +
chromium-headless-shell — see deployment deps). The critique runs on the Olares
"nora" vision model when configured (fast + free); pass which="kimi" to use
Kimi K2.6 instead — better-calibrated judgement, kept as the fallback / for the
critique step if nora proves too weak at design critique.
"""

import frappe
from frappe import _

from unpress_core.ai.config import get_ai_settings
from unpress_core.ai.providers import get_provider
from unpress_core.ai.schemas.page_critique import PageCritique
from unpress_core.ai.logging import ai_log


CRITIQUE_TIMEOUT = 120

_CRITIQUE_SYSTEM = (
    "You are a senior web designer doing a final review of a SCREENSHOT of a "
    "generated web page before it goes live for a client. Judge it as a human "
    "would at first glance. Report ONLY real, visible problems: empty or "
    "unbalanced areas, placeholder/dummy/wrong text, a brand name that doesn't "
    "match the business, broken or squished/stretched images, unreadable text "
    "or poor contrast, misalignment, content that clearly doesn't belong. Be "
    "concrete and specific to what you actually SEE. If it looks good, return "
    "few or no issues."
)


def _critique_provider(which: str = "auto"):
    """Return (provider, label). 'nora' = Olares vision (fast/free); 'kimi' =
    Kimi K2.6 (general/brief model); 'auto' = nora when configured else kimi."""
    cfg = get_ai_settings()
    conf = frappe.conf
    use_nora = which in ("nora", "auto") and conf.get("nora_base_url") and conf.get("nora_api_key")
    if use_nora:
        return get_provider(
            "openai",
            model=conf.get("nora_ocr_model") or conf.get("nora_model") or "nora",
            api_key=conf.get("nora_api_key"),
            base_url=conf.get("nora_base_url"),
            temperature=0.2,
            timeout=CRITIQUE_TIMEOUT,
        ), "nora"
    return get_provider(
        cfg.provider,
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        temperature=0.3,
        timeout=CRITIQUE_TIMEOUT,
    ), cfg.model


def critique_screenshot(screenshot_url: str, which: str = "auto"):
    """Critique a page screenshot. Returns (PageCritique, model_label)."""
    llm, label = _critique_provider(which)
    prompt = (
        "Review this web page screenshot. Give a one-line overall impression, "
        "whether it looks professional, and the concrete visible problems "
        "(area, severity, problem, fix), most important first."
    )
    critique = llm.generate_structured(
        prompt=prompt,
        schema=PageCritique,
        system_prompt=_CRITIQUE_SYSTEM,
        images=[screenshot_url],
        think=False,
    )
    ai_log("info", "Page critique done", model=label,
           issues=len(critique.issues), professional=critique.looks_professional)
    return critique, label
