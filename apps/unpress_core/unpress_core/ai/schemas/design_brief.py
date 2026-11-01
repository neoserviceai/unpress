"""
Design Brief Schema for AI Site Generation
Ensures visual consistency across all generated pages.
"""

from __future__ import annotations
import json
from typing import ClassVar, Literal, Optional
from pydantic import BaseModel, Field, PrivateAttr


class TypographyScale(BaseModel):
    """Typography scale for consistent sizing across all pages."""
    h1_size: str = Field(default="48px", description="H1 font size desktop")
    h1_size_mobile: str = Field(default="32px", description="H1 font size mobile")
    h1_weight: str = Field(default="700", description="H1 font weight")
    h1_line_height: str = Field(default="1.2", description="H1 line height")

    h2_size: str = Field(default="36px", description="H2 font size desktop")
    h2_size_mobile: str = Field(default="26px", description="H2 font size mobile")
    h2_weight: str = Field(default="600", description="H2 font weight")
    h2_line_height: str = Field(default="1.25", description="H2 line height")

    h3_size: str = Field(default="24px", description="H3 font size desktop")
    h3_size_mobile: str = Field(default="20px", description="H3 font size mobile")
    h3_weight: str = Field(default="600", description="H3 font weight")

    body_size: str = Field(default="16px", description="Body font size desktop")
    body_size_mobile: str = Field(default="15px", description="Body font size mobile")
    body_line_height: str = Field(default="1.6", description="Body line height")

    class Config:
        extra = "ignore"


class SectionHeights(BaseModel):
    """Suggested section heights - AI has freedom to adapt."""
    hero_min_height: Optional[str] = Field(default=None, description="Hero minimum height desktop (suggested)")
    hero_min_height_mobile: Optional[str] = Field(default=None, description="Hero minimum height mobile (suggested)")
    standard_min_height: str = Field(default="auto", description="Standard section min height")

    class Config:
        extra = "ignore"


class DesignBrief(BaseModel):
    """
    Design brief for visual consistency across pages.
    Generated ONCE at the start, then used for ALL page generations.
    """

    # True when this brief is the hand-built fallback, not the model's answer.
    #
    # The fallback used to be indistinguishable from a real brief: the caller
    # logged "generated and validated" either way, because a fallback IS valid.
    # A schema the endpoint rejected therefore produced identical chrome on
    # every site for as long as nobody compared the values with the defaults.
    _is_fallback: bool = PrivateAttr(default=False)

    # Art direction — the creative core of the brief. Written by the brief LLM,
    # injected verbatim at the top of every page-generation prompt.
    design_concept: str = Field(
        default="",
        description=(
            "3-5 sentence art direction for this specific site: the chosen aesthetic "
            "direction (e.g. editorial/magazine, luxury/refined, brutalist/raw...), the "
            "atmosphere, how color and typography carry the brand, what makes it distinctive."
        ),
    )
    signature_element: str = Field(
        default="",
        description=(
            "ONE memorable visual idea carried across all pages: an oversized display "
            "headline treatment, a recurring graphic motif, an unexpected accent color "
            "usage, a distinctive section rhythm or image treatment."
        ),
    )
    inner_page_header: str = Field(
        default="",
        description=(
            "Standard page header shared by ALL interior pages (everything except home): "
            "exact height/padding, background treatment (solid/image field from the "
            "palette), title alignment and scale. 2-3 prescriptive sentences — sibling "
            "pages (about, services...) must open identically, only the texts change."
        ),
    )

    # Site tone
    site_tone: Literal["professional", "playful", "elegant", "bold", "minimal"] = Field(
        default="professional",
        description="Overall tone of the site"
    )

    # Actual colors (stored for consistency across pages)
    primary_color: str = Field(
        default="#6366f1",
        description="Primary color hex value chosen for this site"
    )
    secondary_color: str = Field(
        default="#8b5cf6",
        description="Secondary color hex value chosen for this site"
    )

    # Color usage rules
    primary_usage: str = Field(
        default="CTA buttons, links, icons, key highlights",
        description="How to use the primary color"
    )
    secondary_usage: str = Field(
        default="Gradients, hover states, secondary accents, badges",
        description="How to use the secondary color"
    )

    # Section background alternation pattern
    section_backgrounds: list[str] = Field(
        default_factory=lambda: ["#ffffff", "#f8fafc", "#ffffff", "var(--primary-color)"],
        description="Ordered list of backgrounds to alternate between sections"
    )

    # Button styles (CSS camelCase)
    button_primary: dict = Field(
        default_factory=lambda: {
            "backgroundColor": "var(--primary-color)",
            "color": "#ffffff",
            "padding": "14px 28px",
            "borderRadius": "8px",
            "fontWeight": "600",
            "border": "none",
            "cursor": "pointer",
        },
        # A bare `dict` becomes `{"type": "object"}` with no properties, and the
        # strict structured-output schema turns that into an object allowing no
        # keys at all — which the API rejects with HTTP 400. Every brief then
        # fell back to the hand-built defaults, silently, which is why every
        # generated site wore the same header, footer, colours and band. The
        # shape is declared here so the model can actually fill it; the runtime
        # type stays `dict`, so nothing that reads it has to change.
        json_schema_extra={
            "properties": {
                    "backgroundColor": {"type": "string"},
                    "color": {"type": "string"},
                    "padding": {"type": "string"},
                    "borderRadius": {"type": "string"},
                    "fontWeight": {"type": "string"},
                    "border": {"type": "string"},
                    "cursor": {"type": "string"}
            },
            "required": ["backgroundColor", "color", "padding", "borderRadius", "fontWeight", "border", "cursor"],
            "additionalProperties": False,
        },
        description="Primary button styles"
    )
    button_secondary: dict = Field(
        default_factory=lambda: {
            "backgroundColor": "transparent",
            "color": "var(--primary-color)",
            "padding": "14px 28px",
            "borderRadius": "8px",
            "fontWeight": "600",
            "border": "2px solid var(--primary-color)",
            "cursor": "pointer",
        },
        # A bare `dict` becomes `{"type": "object"}` with no properties, and the
        # strict structured-output schema turns that into an object allowing no
        # keys at all — which the API rejects with HTTP 400. Every brief then
        # fell back to the hand-built defaults, silently, which is why every
        # generated site wore the same header, footer, colours and band. The
        # shape is declared here so the model can actually fill it; the runtime
        # type stays `dict`, so nothing that reads it has to change.
        json_schema_extra={
            "properties": {
                    "backgroundColor": {"type": "string"},
                    "color": {"type": "string"},
                    "padding": {"type": "string"},
                    "borderRadius": {"type": "string"},
                    "fontWeight": {"type": "string"},
                    "border": {"type": "string"},
                    "cursor": {"type": "string"}
            },
            "required": ["backgroundColor", "color", "padding", "borderRadius", "fontWeight", "border", "cursor"],
            "additionalProperties": False,
        },
        description="Secondary/outline button styles"
    )

    # Card styles
    card_style: dict = Field(
        default_factory=lambda: {
            "backgroundColor": "#ffffff",
            "borderRadius": "12px",
            "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.08)",
            "padding": "24px",
            "border": "1px solid rgba(0, 0, 0, 0.05)",
        },
        # A bare `dict` becomes `{"type": "object"}` with no properties, and the
        # strict structured-output schema turns that into an object allowing no
        # keys at all — which the API rejects with HTTP 400. Every brief then
        # fell back to the hand-built defaults, silently, which is why every
        # generated site wore the same header, footer, colours and band. The
        # shape is declared here so the model can actually fill it; the runtime
        # type stays `dict`, so nothing that reads it has to change.
        json_schema_extra={
            "properties": {
                    "backgroundColor": {"type": "string"},
                    "borderRadius": {"type": "string"},
                    "boxShadow": {"type": "string"},
                    "padding": {"type": "string"},
                    "border": {"type": "string"}
            },
            "required": ["backgroundColor", "borderRadius", "boxShadow", "padding", "border"],
            "additionalProperties": False,
        },
        description="Card container styles"
    )

    # Hero section. No gradient default: the brief LLM must make a deliberate
    # choice per site (empty values are filled by get_default_brief's varied
    # fallback, never by a hardcoded gradient).
    hero_background: str = Field(
        default="",
        description="Hero section background (a deliberate choice — solid, image treatment, dark field...)"
    )
    hero_text_color: str = Field(
        default="",
        description="Hero section text color (must contrast with hero_background)"
    )
    hero_style: Literal[
        "image",        # Image with a deliberate treatment (solid overlay, duotone, scrim)
        "split",        # Split layout (image + text, 60/40, 70/30...)
        "minimal",      # Typography-led, generous space
        "solid",        # Solid color field
        "asymmetric",   # Off-center/overlapping composition
        "cards",        # Content cards integrated in the hero
        "gradient",     # Only as a deliberate, characterful choice
    ] = Field(
        default="split",
        description="Hero composition — choose what serves THIS site's direction"
    )

    # Spacing
    section_padding: str = Field(
        default="80px 24px",
        description="Desktop section padding"
    )
    section_padding_mobile: str = Field(
        default="48px 16px",
        description="Mobile section padding"
    )
    #: NOT a decision. The site's content width belongs to the chrome, which
    #: the header and the footer already obey, so this carries the token rather
    #: than a number.
    #:
    #: It used to default to "1200px" while another rule in the same prompt
    #: asked for `var(--container-width, 1280px)` — and the list of forbidden
    #: widths right below it named 1200px. Two instructions fighting: measured
    #: on a generated page, the header sat at x=248 and the body copy at x=264.
    #: Sixteen pixels of staircase, from a contradiction we wrote ourselves.
    content_max_width: Literal["var(--container-width, 1280px)"] = Field(
        default="var(--container-width, 1280px)",
        description=(
            "The site's content width. Always this token — never a number, so "
            "the page and the chrome cannot drift apart."
        )
    )

    # NEW: Typography Scale (prescriptive sizes)
    typography: TypographyScale = Field(
        default_factory=TypographyScale,
        description="Typography scale for consistent sizing"
    )

    # NEW: Font families (empty defaults — chosen per site by the brief LLM or
    # the varied theme fallback, never a hardcoded generic face)
    #: The fonts the SITE can actually wear.
    #:
    #: This list must match the `heading_font` / `body_font` Select on
    #: `Website Header Footer Config`. It used to be a free string here and a
    #: Select of 22 there: the brief picked "Syne", the chrome refused it, and
    #: the propagation failed silently — so the header, the footer and the page
    #: header kept the PREVIOUS site's fonts while the pages wore the new ones.
    #: A font the site cannot store is not a choice, it is a bug waiting.
    heading_font: Literal["Inter", "Montserrat", "Poppins", "Roboto", "Open Sans", "Lato", "Raleway", "Playfair Display", "Source Sans 3", "Nunito", "Lora", "DM Sans", "Manrope", "Cormorant Garamond", "Sora", "Plus Jakarta Sans", "Outfit", "Space Grotesk", "Archivo Black", "Bebas Neue", "Merriweather", "Roboto Slab"] = Field(
        default="Inter",
        description=(
            "Font for headings — characterful, fits the art direction. Pick the "
            "one that says what this business is, not the safest one."
        )
    )
    body_font: Literal["Inter", "Montserrat", "Poppins", "Roboto", "Open Sans", "Lato", "Raleway", "Playfair Display", "Source Sans 3", "Nunito", "Lora", "DM Sans", "Manrope", "Cormorant Garamond", "Sora", "Plus Jakarta Sans", "Outfit", "Space Grotesk", "Archivo Black", "Bebas Neue", "Merriweather", "Roboto Slab"] = Field(
        default="Inter",
        description="Font for body text — readable at length, pairs with heading_font"
    )

    # NEW: Section Heights
    section_heights: SectionHeights = Field(
        default_factory=SectionHeights,
        description="Section height constraints"
    )

    # NEW: Padding by section type
    section_paddings: dict = Field(
        default_factory=lambda: {
            "hero": "100px 24px",
            "standard": "80px 24px",
            "compact": "60px 24px",
            "cta": "60px 24px",
        },
        # A bare `dict` becomes `{"type": "object"}` with no properties, and the
        # strict structured-output schema turns that into an object allowing no
        # keys at all — which the API rejects with HTTP 400. Every brief then
        # fell back to the hand-built defaults, silently, which is why every
        # generated site wore the same header, footer, colours and band. The
        # shape is declared here so the model can actually fill it; the runtime
        # type stays `dict`, so nothing that reads it has to change.
        json_schema_extra={
            "properties": {
                    "hero": {"type": "string"},
                    "standard": {"type": "string"},
                    "compact": {"type": "string"},
                    "cta": {"type": "string"}
            },
            "required": ["hero", "standard", "compact", "cta"],
            "additionalProperties": False,
        },
        description="Padding values per section type"
    )

    # NEW: Dark background detection pattern
    dark_background_threshold: str = Field(
        default="gradient|primary|secondary|#[0-5]",
        description="Regex pattern for dark backgrounds requiring white text"
    )

    # Typography colors
    heading_color: str = Field(
        default="var(--text-color)",
        description="Heading text color"
    )
    body_color: str = Field(
        default="var(--muted-color)",
        description="Body text color"
    )
    link_color: str = Field(
        default="var(--primary-color)",
        description="Link text color"
    )

    # Visual effects
    use_shadows: bool = Field(
        default=True,
        description="Use box shadows on cards/elements"
    )
    use_gradients: bool = Field(
        default=True,
        description="Use gradients for backgrounds/buttons"
    )
    border_radius_style: Literal["none", "subtle", "rounded", "pill"] = Field(
        default="rounded",
        description="Border radius style"
    )

    # ------------------------------------------------------------------
    # Design system — decided ONCE here, written to the site's CSS
    # variables, and then never repeated on a block. Their whole purpose is
    # that a page does not carry its own radius, shadow or hover: it asks
    # for a role (u-btn, u-card) and the site answers.
    # ------------------------------------------------------------------
    button_hover: Literal["None", "Darken", "Lift", "Grow"] = Field(
        default="Darken",
        description=(
            "What every button on the site does on hover. One behaviour for "
            "the whole site — Darken is the safe default, Lift adds elevation, "
            "Grow scales slightly."
        )
    )
    motion_style: Literal["None", "Calm", "Brisk"] = Field(
        default="Calm",
        description="Transition speed for hovers and state changes."
    )

    # Inspiration context (from user-provided reference sites/images)
    inspiration_context: Optional[str] = Field(
        default=None,
        description="Context from inspiration sources (liked/disliked colors, styles)"
    )
    colors_to_avoid: Optional[list[str]] = Field(
        default=None,
        description="Colors to avoid based on disliked inspirations"
    )

    # Site chrome — the locked, site-wide header/footer take their design from
    # the brief (applied to Website Header Footer Config by the worker).
    header_bg_color: str = Field(
        default="#ffffff",
        description="Header background color — MUST be chosen based on logo analysis if logo is provided. Use white (#ffffff) for dark logos, dark for light logos. Must ensure logo readability."
    )
    header_text_color: str = Field(
        default="#1a1a1a",
        description="Header text color — MUST contrast with header_bg_color. Use dark text (#1a1a1a) on light header, white (#ffffff) on dark header."
    )
    header_height: Literal["Standard", "Slim", "Tall"] = Field(
        default="Standard",
        description="Header bar height — Slim (56px) reads refined/editorial, Tall (76px) reads bold"
    )
    header_border: Literal["None", "Subtle"] = Field(
        default="Subtle",
        description="Fine separation line under the header — Subtle or None"
    )
    header_style: Literal["Classic", "Floating", "Transparent", "Minimal"] = Field(
        default="Classic",
        description=(
            "How the bar sits on the page. Classic: full-width bar, the safe "
            "default. Floating: detached rounded bar above the content, reads "
            "modern/premium. Transparent: blends into the hero and turns solid "
            "on scroll — only when the first section is a full-bleed image or "
            "a deep colour, otherwise the menu is unreadable. Minimal: no "
            "background, no border, for editorial sites."
        )
    )
    cta_style: Literal["Primary", "Secondary", "Outline"] = Field(
        default="Primary",
        description="Header CTA fill: Primary (solid accent), Secondary, Outline (border only — refined)"
    )
    cta_shape: Literal["Rounded", "Pill", "Square"] = Field(
        default="Rounded",
        description="Header CTA shape: Pill (soft/refined), Rounded, Square (editorial/brutalist)"
    )
    cta_size: Literal["Medium", "Small"] = Field(
        default="Small",
        description="Header CTA size — Small reads discreet and refined"
    )
    page_header_template: Literal["Minimal", "Standard", "Centered", "Split", "None"] = Field(
        default="Standard",
        description=(
            "The band that opens every interior page — breadcrumb, title, one "
            "line. The SITE draws it, once, on every page except home; you pick "
            "which of OUR presets it uses, never its markup. Minimal: breadcrumb "
            "and title only, announces and steps aside — for a site with many "
            "short pages. Standard: breadcrumb, title, one line. Centered: the "
            "same, centred, for a site whose pages open on a statement rather "
            "than a label. Split: title left, the line to its right, editorial. "
            "None: no band, only for a site whose every page genuinely opens on "
            "its own full-bleed image."
        )
    )
    page_header_background: Literal["None", "Tinted", "Solid", "Image"] = Field(
        default="None",
        description=(
            "What that band sits on. None: the page background, quiet, lets the "
            "content start. Tinted: a light wash of the primary colour, when the "
            "section should announce itself. Solid: a full colour block, bold — "
            "the title turns white. Image: a photograph with a scrim, the title "
            "white on top; only when the site HAS photography worth showing on "
            "every interior page, otherwise it reads like a stock-photo header."
        )
    )
    page_header_bg_color: str = Field(
        default="",
        description=(
            "The colour that band sits on, as #rrggbb — only meaningful when "
            "the background is Solid or Tinted. Leave EMPTY to wash the site's "
            "primary colour, which is the right answer most of the time. Give a "
            "colour only when the band should read differently from the rest of "
            "the chrome: a deep neutral under a colourful site, for instance. "
            "It must pass contrast with white text when the background is Solid."
        )
    )
    show_breadcrumbs: bool = Field(
        default=True,
        description=(
            "Breadcrumb trail in that band. True on any site with more than a "
            "handful of pages; False on a very short site where every page is "
            "one click from home."
        )
    )
    footer_template: Literal["Minimal", "Standard", "Extended", "Centered"] = Field(
        default="Standard",
        description=(
            "Footer density — Minimal (one line), Standard (columns), Extended "
            "(rich columns + newsletter), Centered (logo, one row of links, "
            "social underneath — for sites with few links)"
        )
    )
    footer_bg_color: str = Field(
        default="",
        description="Footer background — often a deep field of the palette or the surface tone"
    )
    footer_text_color: str = Field(
        default="",
        description="Footer text color — must contrast with footer_bg_color"
    )

    # ------------------------------------------------------------------
    # The design system, derived — never asked of the model twice.
    # border_radius_style and use_shadows are decisions it already makes (and
    # that every theme preset already sets). Asking for a second field saying
    # the same thing is how a brief ends up contradicting itself.
    # ------------------------------------------------------------------
    RADIUS_TOKENS: ClassVar[dict] = {
        "none": "Sharp",
        "subtle": "Subtle",
        "rounded": "Rounded",
        # "pill" means "as round as it goes" — on cards and inputs that reads
        # as Soft; genuinely pill-shaped buttons come from cta_shape.
        "pill": "Soft",
    }

    @property
    def radius_style(self) -> str:
        """The site's corners, for --radius."""
        return self.RADIUS_TOKENS.get(self.border_radius_style, "Subtle")

    @property
    def shadow_style(self) -> str:
        """How much raised surfaces lift, for --shadow.

        A bold site earns the heavier scale: flat shadows are what make a
        neobrutalist page look timid.
        """
        if not self.use_shadows:
            return "None"
        return "Strong" if self.site_tone == "bold" else "Soft"

    def get_border_radius(self) -> str:
        """Get border radius value based on style."""
        radii = {
            "none": "0",
            "subtle": "4px",
            "rounded": "12px",
            "pill": "9999px",
        }
        return radii.get(self.border_radius_style, "12px")

    def _get_inspiration_section(self) -> str:
        """Get inspiration context section for prompt."""
        parts = []

        if self.inspiration_context:
            parts.append(f"\n### User Inspiration Context\n{self.inspiration_context}")

        if self.colors_to_avoid:
            colors_str = ", ".join(self.colors_to_avoid[:5])
            parts.append(f"\n### Colors to AVOID\n{colors_str}")

        if parts:
            return "\n".join(parts) + "\n"
        return ""

    def to_prompt_section(self) -> str:
        """Convert to a suggestive prompt section for the AI - guidelines not mandates."""
        bg_sequence = " → ".join(self.section_backgrounds)
        typo = self.typography
        heights = self.section_heights
        paddings = self.section_paddings

        # Heights section - recommend minHeight for heroes
        heights_section = """
### Section Heights
- Hero sections: use minHeight "70vh" to "90vh" for visual impact
- Other sections: let content determine height naturally
- Use generous padding (80px-120px) for comfortable spacing
"""

        concept_section = ""
        if self.design_concept:
            concept_section = f"""### ART DIRECTION (follow this — it defines the site)
{self.design_concept}
"""
        if self.signature_element:
            concept_section += f"""
### SIGNATURE ELEMENT (must appear, consistently, on every page)
{self.signature_element}
"""

        return f"""## DESIGN BRIEF
{concept_section}
### Site Tone: {self.site_tone}

### Typography suggestions
Consider these sizes, but feel free to adapt:
| Element | Desktop | Mobile | Weight |
|---------|---------|--------|--------|
| h1 | ~{typo.h1_size} | ~{typo.h1_size_mobile} | {typo.h1_weight} |
| h2 | ~{typo.h2_size} | ~{typo.h2_size_mobile} | {typo.h2_weight} |
| h3 | ~{typo.h3_size} | ~{typo.h3_size_mobile} | {typo.h3_weight} |
| p  | ~{typo.body_size} | ~{typo.body_size_mobile} | 400 |

### Fonts (CONTRACT — exactly these on every page)
- Headings: "{self.heading_font}"
- Body: "{self.body_font}"
- Include fontFamily in baseStyles for text elements
{heights_section}
### Section Paddings (suggestions)
| Type | Desktop | Mobile |
|------|---------|--------|
| Hero | ~{paddings.get('hero', '100px 24px')} | ~60px 16px |
| Standard | ~{paddings.get('standard', '80px 24px')} | ~48px 16px |

### COLOR CONTRACT (STRICT — every page, no exceptions)
The ONLY colors allowed on this site:
- Primary: {self.primary_color} → write it as var(--primary-color)
- Secondary: {self.secondary_color} → write it as var(--secondary-color)
- Neutrals: #ffffff, light grays (#f8fafc, #fafafa, #f5f5f5), var(--text-color), var(--muted-color), and dark fields derived from the palette above
- **Primary color usage**: {self.primary_usage}
- **Secondary color usage**: {self.secondary_usage}
⚠️ Any OTHER saturated hex (a new gold, teal, coral...) is FORBIDDEN — including
inside inline SVG fill/stroke attributes. Pages must read as chapters of ONE
book: same palette, same fonts, same button system on every page.

### LAYOUT CONTRACT (STRICT — one grid for the whole site)
- Every non-full-bleed section wraps its content in a container with
  maxWidth: "{self.content_max_width}", marginLeft/marginRight: "auto" and consistent
  horizontal padding. Full-bleed color/image fields are welcome, but the CONTENT
  inside them still aligns to this same {self.content_max_width} grid.
- NEVER introduce a content width of your own (1140px, 1200px, 1320px…), and
  never a horizontal padding of your own on a <section> (48px, 6vw, 5%…). The
  site header and footer already sit in `var(--container-width, 1280px)`; a
  section that invents its own inset puts the body copy on a different x from
  the logo above it. One site = ONE grid — pages of different widths read as
  different websites.
- INTERIOR PAGE HEADER — the SITE draws it, you do not. Every page except the
  home page is rendered underneath one shared band (breadcrumb, page title, one
  line), styled once from the theme, identical everywhere. So do NOT open an
  interior page with a header, a title band or any section whose job is to
  announce the page: it would sit directly under the real one. Start on the
  first section of actual content.

### Section Background Alternation (suggested pattern)
{bg_sequence}

### Button Styles (CONTRACT — identical on every page)
Primary: {json.dumps(self.button_primary)}
Secondary: {json.dumps(self.button_secondary)}

### Card Style (CONTRACT — identical on every page)
- background: {self.card_style.get('backgroundColor')}

### THE DESIGN SYSTEM IS ALREADY WRITTEN — DO NOT REPEAT IT
The site's corners, elevation, motion and hover behaviour are set once, in
CSS. Ask for a role and you get them:

| You want | Put in `classes` | Then DO NOT set |
|---|---|---|
| a button | `["u-btn", "u-btn--primary"]` (or `--secondary`, `--outline`, `--ghost`) | borderRadius, boxShadow, transition, any :hover |
| a card | `["u-card"]` (or `u-card--raised`, `u-card--flat`) | borderRadius, boxShadow, border, padding |
| an image | `["u-media"]` | borderRadius, overflow |
| a section over a photo | `["u-over-image"]` (+ `--bottom`/`--diagonal`/`--soft`) | any full-surface overlay |
| a secondary button on that photo | `["u-btn", "u-btn--on-image"]` | backgroundColor, border |
| a text input | `["u-input"]` | borderRadius, border |

Corners: {self.radius_style} · Elevation: {self.shadow_style} · Hover: {self.button_hover}

Setting those properties on a block is not an error the site will show — it
is how two pages end up with different buttons. Leave them out.

### Hero Section
- Background: {self.hero_background}
- Text color: {self.hero_text_color}
- Style: {self.hero_style}

### Typography Colors
- Headings: {self.heading_color}
- Body text: {self.body_color}
- Links: {self.link_color}

### TEXT CONTRAST (CRITICAL - always follow!)
| Background | Text Color |
|------------|------------|
| Gradient or colored (primary/secondary) | "#ffffff" |
| White (#ffffff) | "var(--text-color)" |
| Light gray (#f8fafc, #fafafa, #f5f5f5) | "var(--text-color)" |

⚠️ NEVER use white text on white or light backgrounds!

### Visual Effects
- Shadows: {"Yes" if self.use_shadows else "No"}
- Gradients: {"Yes" if self.use_gradients else "No"}
- Border radius: {self.border_radius_style} ({self.get_border_radius()}) — the
  site already applies it through `--radius`; use the `u-` classes rather than
  writing it per block
{self._get_inspiration_section()}
Section composition WITHIN the grid is yours to design creatively, page by
page. The GRID ({self.content_max_width}), the INTERIOR PAGE HEADER, COLORS,
FONTS, BUTTONS and CARDS are a binding contract: identical on every page.
"""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump()

    def get_missing_fields(self) -> list[str]:
        """
        Return list of fields that are still at default values.
        Useful for checking if AI properly filled all fields.
        """
        defaults = DesignBrief()
        missing = []

        # Fonts are pre-selected by theme, no need to check for defaults

        # Check hero fields
        if self.hero_background == defaults.hero_background:
            missing.append("hero_background")
        if self.hero_text_color == defaults.hero_text_color:
            missing.append("hero_text_color")

        # Check button styles (compare backgroundColor)
        if self.button_primary.get("backgroundColor") == defaults.button_primary.get("backgroundColor"):
            missing.append("button_primary")

        # Check section paddings
        if self.section_paddings == defaults.section_paddings:
            missing.append("section_paddings")

        return missing

    def merge_with_defaults(self, defaults: "DesignBrief") -> "DesignBrief":
        """
        Merge this brief with defaults, filling in missing values.
        Returns a new DesignBrief with all fields populated.
        """
        data = self.model_dump()
        defaults_data = defaults.model_dump()

        # Merge missing/empty string fields
        for field in ["heading_font", "body_font", "hero_background", "hero_text_color"]:
            if not data.get(field) or data.get(field) == "":
                data[field] = defaults_data[field]

        # Merge incomplete dict fields
        for field in ["button_primary", "button_secondary", "card_style", "section_paddings"]:
            if not data.get(field) or not isinstance(data.get(field), dict):
                data[field] = defaults_data[field]
            else:
                # Fill missing keys
                for key, value in defaults_data.get(field, {}).items():
                    if key not in data[field] or not data[field][key]:
                        data[field][key] = value

        # Merge typography if needed
        if data.get("typography"):
            typo_data = data["typography"]
            typo_defaults = defaults_data.get("typography", {})
            for key, value in typo_defaults.items():
                if key not in typo_data or not typo_data[key]:
                    typo_data[key] = value
            data["typography"] = typo_data

        return DesignBrief(**data)

    class Config:
        extra = "ignore"


__all__ = ["DesignBrief", "TypographyScale", "SectionHeights"]
