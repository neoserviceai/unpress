"""
Brief Validator - Validates design brief completeness and correctness.
Ensures all critical fields are filled before page generation.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from unpress_core.ai.schemas.design_brief import DesignBrief, TypographyScale
from unpress_core.ai.logging import ai_log


# Valid CSS size patterns
CSS_SIZE_PATTERN = re.compile(r"^\d+(\.\d+)?(px|rem|em|vh|vw|%)$")
CSS_COLOR_PATTERN = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|rgb\(|rgba\(|var\(--[\w-]+\)|transparent|white|black)"
)
HEX6_PATTERN = re.compile(r"^#([0-9a-fA-F]{6})$")


def _relative_luminance(hex_color: str) -> Optional[float]:
    """WCAG relative luminance of a #rrggbb color; None if not parseable."""
    match = HEX6_PATTERN.match((hex_color or "").strip())
    if not match:
        return None
    channels = []
    raw = match.group(1)
    for i in (0, 2, 4):
        c = int(raw[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio_with_white(hex_color: str) -> Optional[float]:
    lum = _relative_luminance(hex_color)
    if lum is None:
        return None
    return (1.0 + 0.05) / (lum + 0.05)


@dataclass
class BriefValidationResult:
    """Result of brief validation."""
    is_valid: bool = True
    missing_fields: list[str] = field(default_factory=list)
    invalid_fields: dict[str, str] = field(default_factory=dict)  # field: error message
    warnings: list[str] = field(default_factory=list)

    def add_missing(self, field_name: str) -> None:
        """Add a missing field."""
        self.missing_fields.append(field_name)
        self.is_valid = False

    def add_invalid(self, field_name: str, error: str) -> None:
        """Add an invalid field with error message."""
        self.invalid_fields[field_name] = error
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning (doesn't invalidate)."""
        self.warnings.append(message)

    def to_correction_prompt(self) -> str:
        """Generate a correction prompt for the AI."""
        parts = []

        if self.missing_fields:
            parts.append("MISSING FIELDS (must provide):")
            for f in self.missing_fields:
                parts.append(f"  - {f}")

        if self.invalid_fields:
            parts.append("\nINVALID FIELDS (must fix):")
            for f, err in self.invalid_fields.items():
                parts.append(f"  - {f}: {err}")

        if self.warnings:
            parts.append("\nWARNINGS (should consider):")
            for w in self.warnings:
                parts.append(f"  - {w}")

        return "\n".join(parts)


# Shortcodes expected per page type
PAGE_TYPE_SHORTCODES = {
    "about": ["team_grid", "company_timeline"],
    "contact": ["contact_form", "google_map", "contact_info"],
    "collection": ["product_carousel", "brand_carousel"],
}


class BriefValidator:
    """
    Validates design brief completeness and correctness.
    Ensures all critical fields are properly filled.
    """

    # Fields that must be non-empty
    REQUIRED_FIELDS = [
        "design_concept",
        "signature_element",
        "inner_page_header",
        "heading_font",
        "body_font",
        "hero_background",
        "hero_text_color",
    ]

    # Fields that must be valid dicts with specific keys
    REQUIRED_DICT_FIELDS = {
        "button_primary": ["backgroundColor", "color"],
        "section_paddings": ["hero", "standard"],
    }

    # Valid values for enum-like fields
    VALID_SITE_TONES = ["professional", "playful", "elegant", "bold", "minimal"]
    VALID_HERO_STYLES = ["gradient", "image", "solid", "split", "minimal", "cards", "asymmetric"]

    def validate(
        self,
        brief: DesignBrief,
        page_types: Optional[list[str]] = None,
    ) -> BriefValidationResult:
        """
        Validate brief completeness and return specific errors.

        Args:
            brief: The design brief to validate
            page_types: List of page types that will be generated

        Returns:
            BriefValidationResult with validation status and errors
        """
        result = BriefValidationResult()

        # Check required string fields
        self._validate_required_fields(brief, result)

        # Check required dict fields
        self._validate_dict_fields(brief, result)

        # Check typography values
        self._validate_typography(brief.typography, result)

        # Check color values
        self._validate_colors(brief, result)

        # Check enum values (warnings only)
        self._validate_enums(brief, result)

        # Check shortcodes if page types specified
        if page_types:
            self._validate_shortcodes_for_pages(page_types, result)

        # Log validation result
        if result.is_valid:
            ai_log("debug", "Brief validation passed")
        else:
            ai_log("warning", "Brief validation failed",
                missing=result.missing_fields,
                invalid=list(result.invalid_fields.keys()))

        return result

    def _validate_required_fields(
        self,
        brief: DesignBrief,
        result: BriefValidationResult,
    ) -> None:
        """Check that required string fields are non-empty."""
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(brief, field_name, None)
            if not value or (isinstance(value, str) and not value.strip()):
                result.add_missing(field_name)

    def _validate_dict_fields(
        self,
        brief: DesignBrief,
        result: BriefValidationResult,
    ) -> None:
        """Check that required dict fields have required keys."""
        for field_name, required_keys in self.REQUIRED_DICT_FIELDS.items():
            value = getattr(brief, field_name, None)
            if not value or not isinstance(value, dict):
                result.add_missing(field_name)
                continue

            missing_keys = [k for k in required_keys if k not in value or not value[k]]
            if missing_keys:
                result.add_invalid(
                    field_name,
                    f"Missing keys: {', '.join(missing_keys)}"
                )

    def _validate_typography(
        self,
        typo: TypographyScale,
        result: BriefValidationResult,
    ) -> None:
        """Check typography values are valid CSS sizes."""
        size_fields = [
            "h1_size", "h1_size_mobile",
            "h2_size", "h2_size_mobile",
            "h3_size", "h3_size_mobile",
            "body_size", "body_size_mobile",
        ]

        for field_name in size_fields:
            value = getattr(typo, field_name, None)
            if value and not CSS_SIZE_PATTERN.match(value):
                result.add_invalid(
                    f"typography.{field_name}",
                    f"Invalid CSS size format: '{value}' (expected: 16px, 1.5rem, etc.)"
                )

    def _validate_colors(
        self,
        brief: DesignBrief,
        result: BriefValidationResult,
    ) -> None:
        """Check color values are valid, and the palette passes basic contrast."""
        color_fields = [
            "hero_text_color", "heading_color", "body_color", "link_color",
            "header_bg_color", "header_text_color",
            "footer_bg_color", "footer_text_color",
        ]

        for field_name in color_fields:
            value = getattr(brief, field_name, None)
            if value and not CSS_COLOR_PATTERN.match(value):
                result.add_invalid(
                    field_name,
                    f"Invalid color format: '{value}' (expected: #hex, rgb(), var(--name))"
                )

        # Layout guard: the site grid must be a concrete px width — pages of
        # different widths read as different websites.
        cmw = (brief.content_max_width or "").strip()
        if not re.match(r"^\d{3,4}px$", cmw):
            result.add_invalid(
                "content_max_width",
                f"'{cmw}' is not a concrete grid width (expected e.g. '1200px')"
            )

        # WCAG guard: primary buttons carry white text — the chosen primary must
        # contrast with white (>= 3:1, large-text/UI threshold). Keeps the freely
        # chosen palette from producing unreadable pastel-on-white CTAs.
        ratio = _contrast_ratio_with_white(brief.primary_color)
        if ratio is not None and ratio < 3.0:
            result.add_invalid(
                "primary_color",
                f"'{brief.primary_color}' has only {ratio:.2f}:1 contrast against white "
                "text — pick a deeper shade of the same hue (>= 3:1 required for buttons)"
            )

    def _validate_enums(
        self,
        brief: DesignBrief,
        result: BriefValidationResult,
    ) -> None:
        """Check enum-like fields have valid values (warnings only)."""
        if brief.site_tone not in self.VALID_SITE_TONES:
            result.add_warning(
                f"site_tone '{brief.site_tone}' not in standard values: {self.VALID_SITE_TONES}"
            )

        if brief.hero_style not in self.VALID_HERO_STYLES:
            result.add_warning(
                f"hero_style '{brief.hero_style}' not in standard values: {self.VALID_HERO_STYLES}"
            )

    def _validate_shortcodes_for_pages(
        self,
        page_types: list[str],
        result: BriefValidationResult,
    ) -> None:
        """Check that relevant shortcodes are documented for page types."""
        for page_type in page_types:
            expected = PAGE_TYPE_SHORTCODES.get(page_type, [])
            if expected:
                # Just add as warnings - the page prompts will handle actual usage
                result.add_warning(
                    f"Page type '{page_type}' may need shortcodes: {', '.join(expected)}"
                )


__all__ = ["BriefValidator", "BriefValidationResult"]
