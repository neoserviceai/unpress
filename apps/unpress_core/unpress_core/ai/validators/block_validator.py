"""
Block Validator - Validation + auto-repair for FrappeBlock structures.
Fixes common LLM output issues instead of rejecting the entire generation.
"""

import uuid
from typing import Optional
import frappe
from unpress_core.ai.logging import ai_log


class BlockValidator:
    """
    Validator and auto-repairer for FrappeBlock structures.
    Fixes common issues (missing blockId, invalid elements) instead of failing.
    """

    VALID_ELEMENTS = {
        # Layout
        "div", "section", "article", "aside", "main", "header", "footer", "nav",
        # Headings & text
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "label", "blockquote",
        "small", "strong", "em", "b", "i", "u", "sub", "sup", "mark", "code", "pre",
        "cite", "abbr", "time", "address", "q", "del", "ins", "kbd", "samp", "var",
        "dl", "dt", "dd", "data", "wbr",
        # Interactive
        "a", "button", "img", "video", "iframe", "audio", "source",
        # Lists
        "ul", "ol", "li",
        # Forms
        "form", "input", "textarea", "select", "option",
        # Table
        "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup", "col",
        # Misc
        "hr", "br", "figure", "figcaption", "details", "summary",
        # SVG (LLM sometimes generates inline SVG icons)
        "svg", "path", "circle", "rect", "line", "polyline", "polygon", "g", "defs",
        "clipPath", "use", "symbol", "text", "tspan",
    }

    def __init__(self):
        self._repairs = 0

    def repair_block(self, block: dict, _depth: int = 0) -> Optional[dict]:
        """
        Validate and auto-repair a single block.
        Returns the repaired block, or None if unfixable.
        """
        if not isinstance(block, dict):
            return None

        # Auto-generate missing blockId
        if "blockId" not in block or not block["blockId"]:
            element = block.get("element", "div")
            block["blockId"] = f"{element}-auto-{uuid.uuid4().hex[:8]}"
            self._repairs += 1

        # Default to div if element missing
        if "element" not in block or not block["element"]:
            block["element"] = "div"
            self._repairs += 1

        # Fix invalid element type — map to closest valid or use div
        element = block.get("element")
        if element not in self.VALID_ELEMENTS:
            ai_log("debug", "Replacing invalid element with div",
                   invalid_element=element, blockId=block.get("blockId"))
            block["element"] = "div"
            self._repairs += 1

        # Recursively repair children
        children = block.get("children")
        if children:
            if not isinstance(children, list):
                block["children"] = []
                self._repairs += 1
            else:
                repaired_children = []
                for child in children:
                    repaired = self.repair_block(child, _depth=_depth + 1)
                    if repaired:
                        repaired_children.append(repaired)
                block["children"] = repaired_children

        return block

    def validate_and_repair(self, blocks: list[dict]) -> list[dict]:
        """
        Validate and auto-repair a list of blocks.
        Returns the repaired blocks list. Only returns empty if input was completely invalid.
        """
        self._repairs = 0

        if not isinstance(blocks, list):
            ai_log("warning", "Blocks is not a list", type=str(type(blocks)))
            return []

        if not blocks:
            ai_log("warning", "Blocks list is empty")
            return []

        # Deduplicate blockIds
        seen_ids = set()

        def dedup_ids(block):
            if not isinstance(block, dict):
                return
            block_id = block.get("blockId", "")
            if block_id in seen_ids:
                new_id = f"{block_id}-{uuid.uuid4().hex[:6]}"
                block["blockId"] = new_id
                self._repairs += 1
            seen_ids.add(block.get("blockId", ""))
            for child in block.get("children", []):
                dedup_ids(child)

        # Repair each block
        repaired = []
        for block in blocks:
            fixed = self.repair_block(block)
            if fixed:
                repaired.append(fixed)

        # Dedup after repair
        for block in repaired:
            dedup_ids(block)

        # Mechanical safety-net rules (behind the prompts — prompts steer,
        # these guarantee):
        #  R1: a root section laid out as flex WITHOUT an explicit
        #      flexDirection and holding >=2 wide children renders side-by-side
        #      columns of full sections (diagnosed on a k2.7 run) -> force column.
        #  R2: ghost/watermark display words (absolute + huge font) must sit
        #      behind the content with a capped opacity, or they cross the copy.
        for block in repaired:
            self._apply_root_flex_rule(block)
        for block in repaired:
            self._apply_ghost_text_rule(block)
        for block in repaired:
            self._apply_placeholder_text_rule(block)

        if self._repairs > 0:
            ai_log("info", "Blocks auto-repaired",
                   repairs=self._repairs, blocks_count=len(repaired))

        return repaired

    @staticmethod
    def _is_wide_child(child: dict) -> bool:
        if not isinstance(child, dict):
            return False
        width = str((child.get("baseStyles") or {}).get("width", "")).strip()
        if not width or width in ("100%", "auto"):
            return True
        if width.endswith("%"):
            try:
                return float(width[:-1]) > 50
            except ValueError:
                return True
        return False

    def _apply_root_flex_rule(self, block: dict) -> None:
        """R1 — root-level flex sections without explicit direction stack."""
        if not isinstance(block, dict):
            return
        styles = block.get("baseStyles") or {}
        if str(styles.get("display", "")).strip() == "flex" and not styles.get("flexDirection"):
            children = [c for c in (block.get("children") or []) if isinstance(c, dict)]
            wide = [c for c in children if self._is_wide_child(c)]
            if len(wide) >= 2:
                styles["flexDirection"] = "column"
                block["baseStyles"] = styles
                self._repairs += 1
                ai_log("info", "mechanical rule applied", rule="root-flex-column",
                       block=block.get("blockId"))

    _FONT_HUGE_PX = 64.0

    @classmethod
    def _font_size_px(cls, value) -> float:
        import re as _re

        raw = str(value or "")
        nums = [float(n) for n in _re.findall(r"(\d+(?:\.\d+)?)", raw)]
        if not nums:
            return 0.0
        biggest = max(nums)
        if "rem" in raw or ("em" in raw and "rem" not in raw):
            return biggest * 16.0
        return biggest

    def _apply_ghost_text_rule(self, block: dict, _depth: int = 0) -> None:
        """R2 — oversized absolute display text goes behind content, faded."""
        if not isinstance(block, dict) or _depth > 30:
            return
        styles = block.get("baseStyles") or {}
        text = str(block.get("innerHTML") or "").strip()
        if (
            text
            and str(styles.get("position", "")).strip() == "absolute"
            and self._font_size_px(styles.get("fontSize")) >= self._FONT_HUGE_PX
        ):
            try:
                opacity = float(str(styles.get("opacity", "1")))
            except ValueError:
                opacity = 1.0
            changed = False
            if opacity > 0.08:
                styles["opacity"] = "0.08"
                changed = True
            if str(styles.get("zIndex", "")).strip() not in ("-1",):
                styles["zIndex"] = "-1"
                changed = True
            if changed:
                styles.setdefault("pointerEvents", "none")
                block["baseStyles"] = styles
                self._repairs += 1
                ai_log("info", "mechanical rule applied", rule="ghost-text-behind",
                       block=block.get("blockId"))
        for child in block.get("children") or []:
            self._apply_ghost_text_rule(child, _depth + 1)

    _PLACEHOLDER_TEXT_RE = None

    def _strip_placeholder_text(self, value: str):
        """Drop ?text=… from large placehold.co URLs (the service prints the
        text as a giant word across the image). Avatar-sized (<300px wide)
        placeholders keep their initials."""
        import re as _re

        if "placehold.co" not in value:
            return value, False
        changed = False

        def _sub(match):
            nonlocal changed
            url = match.group(0)
            size = _re.search(r"placehold\.co/(\d+)x(\d+)", url)
            width = int(size.group(1)) if size else 1000
            if width < 300:
                return url
            before = url
            url = _re.sub(r"\?text=[^\s\"'\)]*", "", url)
            # placehold.co prints its dimensions when no text is given — make
            # the label invisible by using the background color for the text
            url = _re.sub(
                r"(placehold\.co/\d+x\d+/)([0-9a-fA-F]{3,8})/([0-9a-fA-F]{3,8})",
                lambda m: m.group(1) + m.group(2) + "/" + m.group(2),
                url,
            )
            if url != before:
                changed = True
            return url

        value = _re.sub(r"https?://[^\s\"'\)]*placehold\.co[^\s\"'\)]*", _sub, value)
        return value, changed

    def _apply_placeholder_text_rule(self, block: dict, _depth: int = 0) -> None:
        """R3 — text-bearing large placeholders become plain color blocks."""
        if not isinstance(block, dict) or _depth > 30:
            return
        for container_key in ("baseStyles", "mobileStyles", "tabletStyles", "attributes", "rawStyles"):
            container = block.get(container_key)
            if not isinstance(container, dict):
                continue
            for key, value in list(container.items()):
                if isinstance(value, str) and "placehold.co" in value:
                    new_value, changed = self._strip_placeholder_text(value)
                    if changed:
                        container[key] = new_value
                        self._repairs += 1
                        ai_log("info", "mechanical rule applied",
                               rule="placeholder-text-stripped", block=block.get("blockId"))
        inner = block.get("innerHTML")
        if isinstance(inner, str) and "placehold.co" in inner:
            new_inner, changed = self._strip_placeholder_text(inner)
            if changed:
                block["innerHTML"] = new_inner
                self._repairs += 1
                ai_log("info", "mechanical rule applied",
                       rule="placeholder-text-stripped", block=block.get("blockId"))
        for child in block.get("children") or []:
            self._apply_placeholder_text_rule(child, _depth + 1)

    def validate(self, block: dict, _depth: int = 0) -> bool:
        """Legacy validation — still returns bool for backward compat."""
        if not isinstance(block, dict):
            return False
        if "blockId" not in block:
            return False
        if "element" not in block:
            return False
        if block.get("element") not in self.VALID_ELEMENTS:
            return False
        children = block.get("children")
        if children:
            if not isinstance(children, list):
                return False
            for child in children:
                if not self.validate(child, _depth=_depth + 1):
                    return False
        return True

    def validate_blocks(self, blocks: list[dict]) -> bool:
        """Legacy validation — returns True if all blocks valid."""
        if not isinstance(blocks, list) or not blocks:
            return False
        for i, block in enumerate(blocks):
            if not self.validate(block):
                ai_log("warning", "Block validation failed at index",
                       index=i, element=block.get("element"), blockId=block.get("blockId"))
                return False
        return True


__all__ = [
    "BlockValidator",
]
