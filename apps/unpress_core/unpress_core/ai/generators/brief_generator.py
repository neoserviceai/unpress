"""
Brief Generator - Design Brief Generation for Site Consistency
Generates a design brief ONCE at the start, then used for ALL pages.
"""

import random
import re
from typing import Optional
import frappe

from unpress_core.ai.config import get_ai_settings, AIConfig
from unpress_core.ai.providers import get_provider
from unpress_core.ai.design_system import get_theme
from unpress_core.ai.schemas.design_brief import DesignBrief, TypographyScale, SectionHeights
from unpress_core.ai.validators.brief_validator import BriefValidator, BriefValidationResult
from unpress_core.ai.logging import ai_log


def _hero_background_for_style(hero_style: str, primary: str, secondary: str) -> str:
    """Return a hero background CSS value appropriate for the hero style."""
    if hero_style == "gradient":
        angle = random.choice([120, 135, 150, 160, 180])
        return f"linear-gradient({angle}deg, {primary} 0%, {secondary} 100%)"
    elif hero_style == "solid":
        return primary
    elif hero_style == "minimal":
        return "#ffffff"
    elif hero_style in ("split", "asymmetric", "cards"):
        # Light background — the visual interest comes from layout, not bg
        return "#f8fafc"
    elif hero_style == "image":
        return f"linear-gradient(135deg, {primary}cc 0%, {secondary}99 100%)"
    # Fallback
    return primary


def _hero_text_color_for_style(hero_style: str) -> str:
    """Return hero text color based on hero style."""
    if hero_style in ("minimal", "split", "asymmetric", "cards"):
        return "var(--text-color)"
    return "#ffffff"


HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")

# Fallback palettes — used ONLY when the brief LLM fails or returns an unusable
# color (the LLM normally derives the palette from the business context).
DEFAULT_COLOR_PALETTES = [
    {"primary": "#6366f1", "secondary": "#8b5cf6"},  # Indigo/Violet (original)
    {"primary": "#059669", "secondary": "#10b981"},  # Emerald
    {"primary": "#dc2626", "secondary": "#f97316"},  # Red/Orange
    {"primary": "#7c3aed", "secondary": "#a855f7"},  # Purple
    {"primary": "#0891b2", "secondary": "#06b6d4"},  # Cyan
    {"primary": "#ca8a04", "secondary": "#eab308"},  # Yellow/Gold
    {"primary": "#be185d", "secondary": "#ec4899"},  # Pink/Fuchsia
    {"primary": "#2563eb", "secondary": "#3b82f6"},  # Blue
    {"primary": "#16a34a", "secondary": "#22c55e"},  # Green
    {"primary": "#ea580c", "secondary": "#f97316"},  # Orange
]


def _get_random_palette() -> dict:
    """Get a random color palette for variety."""
    return random.choice(DEFAULT_COLOR_PALETTES)


# Multiple font pairs per theme (heading, body) for variety
# Mix of serif headings + sans-serif body for typographic contrast
THEME_FONT_OPTIONS = {
    "modern": [
        ("Playfair Display", "Open Sans"),
        ("Montserrat", "Lato"),
        ("Raleway", "Source Sans 3"),
        ("Lora", "Inter"),
    ],
    "minimal": [
        ("DM Sans", "Inter"),
        ("Manrope", "Inter"),
        ("Cormorant Garamond", "DM Sans"),
    ],
    "corporate": [
        ("Merriweather", "Source Sans 3"),
        ("Playfair Display", "Lato"),
        ("Roboto Slab", "Roboto"),
    ],
    "creative": [
        ("Playfair Display", "Poppins"),
        ("Sora", "DM Sans"),
        ("Cormorant Garamond", "Montserrat"),
    ],
    "glassmorphism": [
        ("Plus Jakarta Sans", "Inter"),
        ("Outfit", "DM Sans"),
        ("Lora", "Inter"),
    ],
    "neobrutalist": [
        ("Space Grotesk", "Space Grotesk"),
        ("Archivo Black", "Space Grotesk"),
        ("Bebas Neue", "DM Sans"),
    ],
}


def _get_random_fonts(theme: str) -> tuple[str, str]:
    """Get a random font pair (heading, body) for the given theme."""
    return random.choice(
        THEME_FONT_OPTIONS.get(theme, [("Playfair Display", "Open Sans")])
    )


# Default fallback brief when generation fails
def get_default_brief(
    theme: str = "modern",
    primary_color: str = None,
    secondary_color: str = None,
) -> DesignBrief:
    """Get a default design brief based on theme."""
    theme_data = get_theme(theme)
    theme_colors = theme_data.get("colors", {})

    # If no colors provided, pick a random palette for variety
    if not primary_color and not secondary_color:
        random_palette = _get_random_palette()
        effective_primary = theme_colors.get("primary") or random_palette["primary"]
        effective_secondary = theme_colors.get("secondary") or random_palette["secondary"]
        ai_log("debug", "Using random color palette", primary=effective_primary, secondary=effective_secondary)
    else:
        effective_primary = primary_color or theme_colors.get("primary", "#6366f1")
        effective_secondary = secondary_color or theme_colors.get("secondary", "#8b5cf6")

    # Theme-specific typography scales
    theme_typography = {
        "neobrutalist": TypographyScale(
            h1_size="56px", h1_size_mobile="36px", h1_weight="900",
            h2_size="40px", h2_size_mobile="28px", h2_weight="800",
            body_size="18px",
        ),
        "minimal": TypographyScale(
            h1_size="42px", h1_size_mobile="28px", h1_weight="500",
            h2_size="32px", h2_size_mobile="24px", h2_weight="500",
            body_size="16px",
        ),
        "corporate": TypographyScale(
            h1_size="44px", h1_size_mobile="30px", h1_weight="700",
            h2_size="34px", h2_size_mobile="26px", h2_weight="600",
        ),
    }

    # Pick random font pair for this theme
    fonts = _get_random_fonts(theme)

    # Theme-specific section heights - empty to avoid forcing heights
    # Heights should be determined by content, not fixed vh values
    theme_heights = {}

    # Theme-specific defaults with varied hero styles
    theme_briefs = {
        "neobrutalist": {
            "site_tone": "bold",
            "border_radius_style": "none",
            "use_shadows": True,
            "use_gradients": False,
            "hero_style": "asymmetric",
            "section_backgrounds": ["#ffffff", "#fef3c7", "#ffffff", effective_primary],
            "card_style": {
                "backgroundColor": "#ffffff",
                "borderRadius": "0",
                "boxShadow": "8px 8px 0 #000000",
                "padding": "24px",
                "border": "3px solid #000000",
            },
            "section_paddings": {
                "hero": "120px 24px",
                "standard": "100px 24px",
                "compact": "80px 24px",
                "cta": "80px 24px",
            },
        },
        "glassmorphism": {
            "site_tone": "elegant",
            "border_radius_style": "rounded",
            "use_shadows": True,
            "use_gradients": True,
            "hero_style": random.choice(["image", "split", "asymmetric"]),
            "card_style": {
                "backgroundColor": "rgba(255, 255, 255, 0.15)",
                "borderRadius": "16px",
                "boxShadow": "0 8px 32px rgba(0, 0, 0, 0.1)",
                "padding": "24px",
                "border": "1px solid rgba(255, 255, 255, 0.2)",
            },
        },
        "minimal": {
            "site_tone": "minimal",
            "border_radius_style": "subtle",
            "use_shadows": False,
            "use_gradients": False,
            "hero_style": "minimal",
            "section_backgrounds": ["#ffffff", "#fafafa", "#ffffff", "#f5f5f5"],
            "card_style": {
                "backgroundColor": "#ffffff",
                "borderRadius": "4px",
                "boxShadow": "none",
                "padding": "24px",
                "border": "1px solid #e5e5e5",
            },
            "section_paddings": {
                "hero": "80px 24px",
                "standard": "60px 24px",
                "compact": "40px 24px",
                "cta": "40px 24px",
            },
        },
        "corporate": {
            "site_tone": "professional",
            "border_radius_style": "subtle",
            "use_shadows": True,
            "use_gradients": False,
            "hero_style": "split",
        },
        "creative": {
            "site_tone": "playful",
            "border_radius_style": "rounded",
            "use_shadows": True,
            "use_gradients": True,
            "hero_style": "cards",
        },
        "modern": {
            "site_tone": "professional",
            "border_radius_style": "rounded",
            "use_shadows": True,
            "use_gradients": True,
            "hero_style": random.choice(["image", "split", "minimal", "asymmetric"]),
        },
    }

    # Get theme-specific overrides
    overrides = theme_briefs.get(theme, {})
    fallback_hero_style = overrides.get("hero_style") or random.choice(
        ["image", "split", "minimal", "solid", "asymmetric", "cards"]
    )

    # Build the brief
    brief_data = {
        # Generic art direction so the fallback brief PASSES validation —
        # without it, an LLM outage degrades into 3 failed retries and an
        # incoherent merged brief (seen on a real brief: vision error → defaults
        # without design_concept → "Brief still invalid after merge").
        "design_concept": (
            f"A clean, {overrides.get('site_tone', 'professional')} direction in the "
            f"{theme} register: clear hierarchy, generous spacing, consistent use of the "
            "palette with one accent, and restrained, purposeful imagery."
        ),
        "signature_element": (
            "A consistent section rhythm with oversized numbered markers and a single "
            "accent color used sparingly for emphasis."
        ),
        "inner_page_header": (
            "A compact solid band in the primary color (about 220px tall, 80px top "
            "padding), left-aligned h1 at the standard scale in white, one short "
            "intro line below — identical on every interior page."
        ),
        "site_tone": overrides.get("site_tone", "professional"),
        # Store actual colors for consistency
        "primary_color": effective_primary,
        "secondary_color": effective_secondary,
        "primary_usage": "CTA buttons, links, key highlights, icons",
        "secondary_usage": "Gradients, hover states, secondary accents",
        "section_backgrounds": overrides.get(
            "section_backgrounds",
            ["#ffffff", "#f8fafc", "#ffffff", effective_primary]
        ),
        "button_primary": {
            "backgroundColor": "var(--primary-color)",
            "color": "#ffffff",
            "padding": "14px 28px",
            "borderRadius": overrides.get("card_style", {}).get("borderRadius", "8px"),
            "fontWeight": "600",
            "border": "none",
            "cursor": "pointer",
        },
        "button_secondary": {
            "backgroundColor": "transparent",
            "color": "var(--primary-color)",
            "padding": "14px 28px",
            "borderRadius": overrides.get("card_style", {}).get("borderRadius", "8px"),
            "fontWeight": "600",
            "border": "2px solid var(--primary-color)",
            "cursor": "pointer",
        },
        "card_style": overrides.get("card_style", {
            "backgroundColor": "#ffffff",
            "borderRadius": "12px",
            "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.08)",
            "padding": "24px",
            "border": "1px solid rgba(0, 0, 0, 0.05)",
        }),
        # Fallback hero: varied, never a systematic gradient
        "hero_background": _hero_background_for_style(
            fallback_hero_style, effective_primary, effective_secondary
        ),
        "hero_text_color": _hero_text_color_for_style(fallback_hero_style),
        "hero_style": fallback_hero_style,
        "section_padding": "80px 24px",
        "section_padding_mobile": "48px 16px",
        # The site's token, never a number — see DesignBrief.content_max_width.
        # Left at "1200px" here, this fallback failed the Literal and took the
        # whole generation down with it.
        "content_max_width": "var(--container-width, 1280px)",
        "heading_color": "var(--text-color)",
        "body_color": "var(--muted-color)",
        "link_color": "var(--primary-color)",
        "use_shadows": overrides.get("use_shadows", True),
        "use_gradients": overrides.get("use_gradients", True),
        "border_radius_style": overrides.get("border_radius_style", "rounded"),
        # NEW: Typography and fonts
        "typography": theme_typography.get(theme, TypographyScale()),
        "heading_font": fonts[0],
        "body_font": fonts[1],
        # NEW: Section heights
        "section_heights": theme_heights.get(theme, SectionHeights()),
        # NEW: Section paddings by type
        "section_paddings": overrides.get("section_paddings", {
            "hero": "100px 24px",
            "standard": "80px 24px",
            "compact": "60px 24px",
            "cta": "60px 24px",
        }),
    }

    brief = DesignBrief(**brief_data)
    brief._is_fallback = True
    return brief


BRIEF_SYSTEM_PROMPT = """You are the CREATIVE DIRECTOR for this website. Your brief is the single
source of art direction for every page another AI will generate — it decides whether the
result feels genuinely designed or like yet another AI template.

## 1. ART DIRECTION (the most important part)
- `design_concept`: 3-5 sentences. Commit to ONE bold aesthetic direction that fits THIS
  business (brutally minimal, maximalist, retro-futuristic, organic/natural, luxury/refined,
  playful/toy-like, editorial/magazine, brutalist/raw, art-deco/geometric, soft/pastel,
  industrial/utilitarian...). Describe the atmosphere, how color and typography carry the
  brand, and what makes this site UNFORGETTABLE. A stone mason, a pediatric dentist and a
  jazz club must get radically different directions.
- `signature_element`: ONE memorable visual idea carried across all pages (oversized display
  headline treatment, recurring graphic motif, unexpected accent usage, distinctive image
  treatment, asymmetric layout system...).
- FORBIDDEN as direction: the generic AI look — diagonal violet gradient hero with centered
  white text, interchangeable 3-card rows, timid evenly-spread palettes.

## 2. COLOR
- If colors are imposed (client brand/logo), build the direction around them.
- Otherwise CHOOSE the palette from the business's world (materials, environment, emotion) —
  a dominant color + sharp accent beats evenly-distributed pastels. Avoid the indigo/violet
  default and cliché tech palettes unless the business genuinely calls for them.
- primary_color / secondary_color must be real hex values.

## 3. TYPOGRAPHY
- If fonts are imposed, keep them as provided. Otherwise choose a DISTINCTIVE Google Fonts
  pairing serving the direction: a characterful display/heading face + a readable body face.
  Avoid defaulting to Inter/Roboto/Arial/Open Sans; avoid converging on the same trendy
  face across sites.
- TYPOGRAPHY SCALE - precise sizes, scaled to the direction (an editorial site can push
  h1 to 64-80px; a dense corporate tool stays tighter):
   - h1: 42-80px desktop, 28-40px mobile
   - h2: 30-44px desktop, 24-28px mobile
   - h3: 22-30px desktop, 20-24px mobile
   - body: 16-18px desktop, 15-16px mobile
   - line-height: 1.1-1.3 for headings, 1.5-1.7 for body

## 4. STRUCTURE & RHYTHM
- hero_style: a DELIBERATE choice for THIS site (image / split / minimal / solid /
  asymmetric / cards — gradient only as a characterful statement, never as default).
- hero_background + hero_text_color: concrete values that contrast properly.
- section_backgrounds: an alternation that creates rhythm IN the chosen direction
  (not necessarily white/gray/white — a dark or colored field can be part of it).
- Section paddings: hero 80-120px, standard 64-100px, cta 56-80px vertical.
  Heroes may use minHeight 60-90vh when the composition needs presence.
- button_primary / button_secondary / card_style: styled IN the direction (square,
  pill, bordered, shadowed — one deliberate system, used consistently).

## 4a. LAYOUT SYSTEM (one grid, one interior page header)
- content_max_width: ONE canonical content width for the whole site (e.g. "1140px",
  "1200px", "1280px"). Every page aligns to it — mixed widths across pages is the
  #1 thing that makes a site feel stitched together from parts.
- inner_page_header: design the ONE standard header that every interior page
  (about, services, team… — everything except home) opens with. Prescribe it in
  2-3 sentences: exact height/padding, background treatment (a solid or image
  field from the palette), title alignment and scale. Sibling pages must open
  IDENTICALLY — only the texts change.

## 4b. SITE CHROME (header & footer — applied site-wide, choose deliberately)
The site's locked header/footer take their design from YOUR brief:
- header_height: Slim reads refined/editorial, Standard neutral, Tall bold.
- header_border: Subtle fine line, or None for seamless chrome.
- header_style: Classic (full-width bar — the safe default), Floating
  (detached rounded bar, modern/premium), Transparent (blends into the hero,
  turns solid on scroll — ONLY when the first section is a full-bleed image
  or a deep colour, otherwise the menu is unreadable), Minimal (no background,
  no border, editorial).
- CTA: cta_style (Primary solid / Secondary / Outline = border only, refined),
  cta_shape (Pill = soft/refined, Rounded, Square = editorial/brutalist),
  cta_size (Small = discreet; Medium = bolder).
- footer_template (Minimal one line / Standard columns / Extended rich
  columns + newsletter / Centered logo + one row of links, for few links)
  + footer_bg_color /
  footer_text_color: often a deep field of the palette (dark footer) or the
  surface tone — text MUST contrast with it.
All chrome choices must express the same art direction as the pages.

## 5. NON-NEGOTIABLE TECHNICAL RULES
- CONTRAST: colored/dark background → "#ffffff" text; light background (#fff, #f8fafc)
  → "var(--text-color)". NEVER white text on light background!
- Cards: use "#ffffff" or a concrete hex (NEVER var(--surface-color)).
- HEADER COLORS: you MUST choose header_bg_color and header_text_color.
  If a logo image is provided: analyze its dominant colors — dark/colored logo on
  transparent bg → light header (#ffffff or very light); light logo → dark header.
  The logo must be clearly readable on the chosen header background.
  header_text_color must be readable on header_bg_color.

## 6. DESIGN CANDIDATES (when provided in the user prompt)
A "DESIGN CANDIDATES" block may list styles, palettes, typography pairings and UX
rules matched to this business from a professional database. Use it as a moodboard:
pick what genuinely serves THIS business and ADAPT it (hexes, pairings) to the brand —
or overrule it with a stronger idea. The UX "Don'ts" are the only part to always
respect. Never copy a candidate verbatim; §1 stays in charge.

Consistency matters — all pages share ONE visual language (this brief) — but the
language itself must be distinctive to this site, never a reusable template.
Output a valid JSON object matching the DesignBrief schema with ALL fields populated.
"""


class BriefGenerator:
    """
    Generates a design brief for visual consistency across pages.
    Uses low temperature (0.4) for deterministic, consistent decisions.
    """

    def __init__(
        self,
        provider: str = None,
        model: str = None,
        config: AIConfig = None
    ):
        self.config = config or get_ai_settings()

        if provider:
            self.config.provider = provider
        if model:
            self.config.model = model

        # Moderate temperature for creative variety while maintaining coherence
        self.llm = get_provider(
            self.config.provider,
            model=self.config.model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=0.7,  # Higher temperature for design variety
            timeout=self.config.request_timeout,
        )

        # Validator for brief completeness
        self.validator = BriefValidator()

    def generate_brief(
        self,
        prompt: str,
        site_name: str,
        site_type: str,
        theme: str = "modern",
        primary_color: str = None,
        secondary_color: str = None,
        pages_config: list[dict] = None,
        heading_font: str = None,
        body_font: str = None,
        revision_instructions: str = None,
        logo_image: str = None,
        inspiration_images: list[str] = None,
    ) -> DesignBrief:
        """
        Generate a design brief for the site.

        Args:
            prompt: User's site description
            site_name: Name of the site
            site_type: Type of site (vitrine, ecommerce, etc.)
            theme: Visual theme name
            primary_color: Custom primary color
            secondary_color: Custom secondary color
            pages_config: List of pages that will be generated
            heading_font: Heading font override (from company data)
            body_font: Body font override (from company data)

        Returns:
            DesignBrief: Generated design brief
        """
        ai_log("info", "BriefGenerator.generate_brief() starting",
            site_name=site_name, site_type=site_type, theme=theme)

        # Get theme data
        theme_data = get_theme(theme)
        theme_name = theme_data.get("name", theme)
        theme_prompt = theme_data.get("prompt", "")
        theme_colors = theme_data.get("colors", {})

        # Colors: imposed (client brand/logo) → forced onto the brief afterwards;
        # otherwise the brief LLM chooses them from the business context (the old
        # behavior — random.choice over 10 hardcoded Tailwind palettes — was a
        # major cause of same-looking sites).
        colors_imposed = bool(primary_color or secondary_color)
        effective_primary = primary_color or secondary_color
        effective_secondary = secondary_color or primary_color

        # Fonts: same logic — imposed (company data/config) or chosen by the LLM.
        fonts_imposed = bool(heading_font and body_font)

        # Build user prompt
        pages_list = ""
        if pages_config:
            pages_list = "\n".join([f"- {p['title']} ({p['type']})" for p in pages_config])

        if colors_imposed:
            colors_block = f"""**Colors (imposed by the client brand — build the direction around them):**
- Primary: {effective_primary}
- Secondary: {effective_secondary}"""
        else:
            colors_block = (
                "**Colors:** none imposed — CHOOSE the palette from this business's world "
                "(see system prompt §2)."
            )

        if fonts_imposed:
            fonts_block = f"""**Fonts (imposed — keep them as provided):**
- heading_font: "{heading_font}"
- body_font: "{body_font}\""""
        else:
            fonts_block = (
                "**Fonts:** none imposed — choose a distinctive Google Fonts pairing "
                "(see system prompt §3)."
            )

        user_prompt = f"""Create the design brief for this website:

**Site Name:** {site_name}
**Site Type:** {site_type}
**Description:** {prompt}

**Theme hint (a starting mood, not a cage):** {theme_name}
{theme_prompt}

{colors_block}

{fonts_block}

**Pages to generate:**
{pages_list}

Write the art direction (design_concept + signature_element) for THIS business first,
then derive every concrete value of the DesignBrief from it. All pages must share one
distinctive visual language.

Return ONLY the JSON object, no markdown code blocks."""

        # Professional design candidates (BM25 over the vendored UI/UX database).
        # Best-effort: None keeps the prompt exactly as before.
        from unpress_core.ai.design_intelligence import get_design_candidates

        design_candidates = get_design_candidates(
            description=prompt,
            site_type=site_type,
            theme=theme_name,
            colors_imposed=colors_imposed,
        )
        if design_candidates:
            user_prompt += f"\n\n{design_candidates}"

        # Build images list for vision capabilities
        images_for_vision = []
        if logo_image:
            images_for_vision.append(logo_image)
        if inspiration_images:
            images_for_vision.extend(inspiration_images[:3])

        # Add vision analysis prompts
        if logo_image:
            user_prompt += (
                "\n\nThe client's LOGO is attached — it is the single strongest brand "
                "signal you have. Analyze it carefully:\n"
                "- EXTRACT its exact color palette (estimate the hex values you see). "
                + (
                    "The client's colors above stay imposed, but echo the logo palette in your choices."
                    if colors_imposed
                    else "DERIVE primary_color and secondary_color FROM the logo palette — "
                    "the site must feel like it belongs to this logo, never clash with it."
                )
                + "\n- Read its typographic personality (serif/sans, weight, geometry, mood) "
                "and choose a font pairing that harmonizes with it.\n"
                "- Note whether it has a transparent background, and whether it reads "
                "better on light or dark surfaces.\n"
                "Choose header_bg_color and header_text_color accordingly — the logo "
                "must be perfectly readable on the header."
            )
        if inspiration_images:
            user_prompt += f"\n\n{len(inspiration_images)} inspiration image(s) are attached. Analyze them for color palettes, layout patterns, and visual style to inform your design brief."

        # Append revision instructions if provided (progressive generation feedback)
        if revision_instructions:
            user_prompt += f"""

REVISION INSTRUCTIONS (from user feedback):
{revision_instructions}

IMPORTANT: Apply these revision instructions to the design brief. Adjust colors, styles, spacing, or any other aspect mentioned in the feedback while keeping the overall site cohesive."""

        try:
            # Use configurable think level for creative design decisions
            think_value = self.config.get_think_value(self.config.brief_think_level)
            ai_log("debug", "Calling generate_structured for DesignBrief",
                think_level=self.config.brief_think_level, think_value=think_value)
            # Logo/inspiration vision is best-effort: a non-responsive vision
            # endpoint (observed with Moonshot kimi on image payloads — it
            # accepts the request but never answers) must not stall the whole
            # generation. Bound the vision attempt to a short timeout, then fall
            # back to a text-only brief (fully sufficient — only the visual cue
            # from the logo/inspiration is lost, the rest of the brief is intact).
            VISION_TIMEOUT = 90
            brief = None
            if images_for_vision:
                original_timeout = getattr(self.llm, "timeout", None)
                try:
                    if original_timeout:
                        self.llm.timeout = min(original_timeout, VISION_TIMEOUT)
                    brief = self.llm.generate_structured(
                        prompt=user_prompt,
                        schema=DesignBrief,
                        system_prompt=BRIEF_SYSTEM_PROMPT,
                        think=think_value,
                        images=images_for_vision,
                    )
                except Exception as vision_err:
                    ai_log("warning", "Brief vision attempt failed; using text-only brief",
                           error=str(vision_err)[:120])
                    brief = None
                finally:
                    self.llm.timeout = original_timeout
            if brief is None:
                brief = self.llm.generate_structured(
                    prompt=user_prompt,
                    schema=DesignBrief,
                    system_prompt=BRIEF_SYSTEM_PROMPT,
                    think=think_value,
                    images=None,
                )

            # Imposed values always win (the AI might return CSS variables or
            # drift from the client brand); free choices are kept but sanity-
            # checked, with a varied fallback when unusable.
            if colors_imposed:
                brief.primary_color = effective_primary
                brief.secondary_color = effective_secondary
            else:
                if not HEX_COLOR_RE.match(brief.primary_color or ""):
                    palette = _get_random_palette()
                    ai_log("warning", "LLM primary_color unusable, falling back to palette",
                           got=str(brief.primary_color)[:30])
                    brief.primary_color = palette["primary"]
                    brief.secondary_color = palette["secondary"]
                elif not HEX_COLOR_RE.match(brief.secondary_color or ""):
                    brief.secondary_color = brief.primary_color

            if fonts_imposed:
                brief.heading_font = heading_font
                brief.body_font = body_font
            else:
                if not (brief.heading_font or "").strip() or not (brief.body_font or "").strip():
                    fallback_heading, fallback_body = _get_random_fonts(theme)
                    brief.heading_font = (brief.heading_font or "").strip() or fallback_heading
                    brief.body_font = (brief.body_font or "").strip() or fallback_body

            ai_log("info", "Design brief generated successfully",
                site_tone=brief.site_tone, hero_style=brief.hero_style,
                primary_color=brief.primary_color, secondary_color=brief.secondary_color)
            return brief

        except Exception as e:
            # Fallback to default brief
            ai_log("warning", "Brief generation failed, using defaults", error=str(e)[:100])
            frappe.log_error("Brief generation failed", str(e))
            return get_default_brief(
                theme=theme,
                primary_color=effective_primary,
                secondary_color=effective_secondary,
            )

    def generate_brief_with_validation(
        self,
        prompt: str,
        site_name: str,
        site_type: str,
        theme: str = "modern",
        primary_color: str = None,
        secondary_color: str = None,
        pages_config: list[dict] = None,
        max_retries: int = 2,
        heading_font: str = None,
        body_font: str = None,
        revision_instructions: str = None,
        logo_image: str = None,
        inspiration_images: list[str] = None,
    ) -> tuple[DesignBrief, BriefValidationResult]:
        """
        Generate a design brief with validation and automatic retry.

        Args:
            prompt: User's site description
            site_name: Name of the site
            site_type: Type of site
            theme: Visual theme name
            primary_color: Custom primary color
            secondary_color: Custom secondary color
            pages_config: List of pages that will be generated
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            Tuple of (DesignBrief, BriefValidationResult)
        """
        ai_log("info", "Starting brief generation with validation",
            site_name=site_name, max_retries=max_retries)

        # Extract page types for validation
        page_types = [p.get("type", "") for p in (pages_config or [])]

        last_validation = None

        for attempt in range(max_retries + 1):
            ai_log("debug", f"Brief generation attempt {attempt + 1}/{max_retries + 1}")

            # Build prompt with corrections if this is a retry
            effective_prompt = prompt
            if attempt > 0 and last_validation:
                correction = last_validation.to_correction_prompt()
                effective_prompt = f"""{prompt}

IMPORTANT - CORRECTIONS NEEDED:
Your previous design brief was incomplete. Please fix these issues:

{correction}

Make sure ALL fields are properly filled with valid values."""
                ai_log("debug", "Added correction prompt for retry",
                    missing=last_validation.missing_fields)

            # Generate brief
            brief = self.generate_brief(
                prompt=effective_prompt,
                site_name=site_name,
                site_type=site_type,
                theme=theme,
                primary_color=primary_color,
                secondary_color=secondary_color,
                pages_config=pages_config,
                heading_font=heading_font,
                body_font=body_font,
                revision_instructions=revision_instructions if attempt == 0 else None,
                logo_image=logo_image,
                inspiration_images=inspiration_images,
            )

            # Validate
            validation = self.validator.validate(brief, page_types)

            if validation.is_valid:
                ai_log("info", "Brief validation passed",
                    attempt=attempt + 1, warnings=len(validation.warnings))
                return brief, validation

            # An IMPOSED brand color (from the client's real identity) is
            # authoritative — retrying can't change it (we re-impose the same
            # value every attempt), so a contrast-only rejection on
            # primary/secondary_color must NOT burn extra retries on a slow
            # model. Accept the brief; the page generator handles readable
            # button text on the brand color. Keeps generation fast and honors
            # the real palette.
            colors_imposed = bool(primary_color)
            non_color_invalid = {
                k for k in validation.invalid_fields
                if k not in ("primary_color", "secondary_color")
            }
            if colors_imposed and not validation.missing_fields and not non_color_invalid:
                ai_log("info", "Brief accepted with imposed-color contrast warning (no retry)",
                    invalid=list(validation.invalid_fields.keys()))
                for k in ("primary_color", "secondary_color"):
                    if k in validation.invalid_fields:
                        validation.add_warning(
                            f"{k} kept as imposed brand color despite low white-contrast")
                return brief, validation

            # Store for next iteration
            last_validation = validation
            ai_log("warning", f"Brief validation failed (attempt {attempt + 1})",
                missing=validation.missing_fields,
                invalid=list(validation.invalid_fields.keys()))

        # After max retries, merge with defaults
        ai_log("warning", "Max retries reached, merging with defaults",
            attempts=max_retries + 1)

        # Get theme-specific defaults
        default_brief = get_default_brief(
            theme=theme,
            primary_color=primary_color,
            secondary_color=secondary_color,
        )

        # Merge the generated brief with defaults
        merged_brief = brief.merge_with_defaults(default_brief)

        # Final validation (should pass now)
        final_validation = self.validator.validate(merged_brief, page_types)

        if not final_validation.is_valid:
            ai_log("error", "Brief still invalid after merge",
                missing=final_validation.missing_fields)
            # Return merged brief anyway - it's better than nothing
            final_validation.add_warning("Brief was merged with defaults after validation failures")

        return merged_brief, final_validation


__all__ = ["BriefGenerator", "get_default_brief", "BriefValidationResult"]
