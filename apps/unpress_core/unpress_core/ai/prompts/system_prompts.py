"""
System Prompts for Creative AI Generation
These prompts give the AI full creative freedom while ensuring valid FrappeBlock output.
All prompts are in ENGLISH for better LLM comprehension.
The output_language parameter controls the language of generated CONTENT (titles, text, buttons).
"""

import frappe
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from unpress_core.ai.schemas.design_brief import DesignBrief


def get_creative_system_prompt(
    theme_name: str,
    theme_prompt: str,
    primary_color: str = None,
    secondary_color: str = None,
    font_family: str = None,
    page_type: str = None,
    design_brief: "DesignBrief" = None,
    output_language: str = "French",
) -> str:
    """
    Build the main creative system prompt.

    This prompt gives the AI full creative freedom to design unique websites
    while ensuring it outputs valid FrappeBlock JSON.

    Args:
        output_language: Language for generated content (French, English, German, etc.)
    """

    # Design brief section (takes precedence if available)
    design_brief_section = ""
    if design_brief:
        design_brief_section = design_brief.to_prompt_section()

    colors_section = ""
    if primary_color or secondary_color:
        # Only add basic colors section if no design brief (brief has more detailed color instructions)
        if not design_brief:
            colors_section = f"""
## SITE COLORS (IMPORTANT!)
- Primary color: {primary_color} (use for buttons, links, accents)
- Secondary color: {secondary_color} (supporting accents, hover states)

COLOR USAGE:
- Decide deliberately how color carries this site's identity: a dominant
  color field, a near-monochrome scheme with one sharp accent, deep dark
  sections, or generous whitespace with strong typographic color.
- Buttons: backgroundColor: "{primary_color}"
- Cards: backgroundColor: "#ffffff" (NEVER use var(--surface-color))
- Icons and accents: "{primary_color}"

CONTRAST RULES (CRITICAL!):
- Sections with a colored/dark background → color: "#ffffff"
- White background sections (#ffffff) → color: "var(--text-color)"
- Light gray background (#f8fafc, #fafafa, #f5f5f5) → color: "var(--text-color)"
- Cards on white/light background → color: "var(--text-color)"
- NEVER use white text on white or light gray background!
"""
        else:
            # Brief exists, just remind of the actual color values
            colors_section = f"""
## EFFECTIVE COLORS
- var(--primary-color) = {primary_color}
- var(--secondary-color) = {secondary_color}
"""

    font_section = ""
    if font_family:
        font_section = f"""
## FONT
Use font: {font_family}
"""

    # Get available shortcodes for dynamic content
    shortcodes_section = get_shortcodes_context(page_type)
    # The hero guidance above is written for a homepage. An interior page opens
    # on the shared page header instead, and has to be told so here — the user
    # prompt alone loses against the structural example in the system prompt.
    interior_section = (
        _INTERIOR_SYSTEM_RULE
        if page_type and page_type not in {"accueil", "accueil_ecommerce", "one_page"}
        else ""
    )

    # Language instruction section
    language_instruction = f"""
## OUTPUT LANGUAGE: {output_language.upper()}
CRITICAL: All generated TEXT CONTENT must be in {output_language}.
This includes:
- Page titles (h1, h2, h3...)
- Paragraphs and descriptions
- Button labels (CTA)
- Testimonials and quotes
- Any user-facing text

JSON keys and CSS properties remain in English (blockId, baseStyles, etc.).
"""

    # Strip # from colors for placehold.co URLs
    primary_placeholder = (primary_color or "37ac50").lstrip("#")
    secondary_placeholder = (secondary_color or "434647").lstrip("#")

    return f"""You are an expert creative UI/UX designer generating unique websites with Frappe Builder.

## YOUR MISSION
Create a DISTINCTIVE, production-grade website that feels genuinely designed for THIS
client — never a generic template. Before generating, commit to ONE bold aesthetic
direction that fits the business (the design brief's concept takes precedence if given):
brutally minimal, maximalist, retro-futuristic, organic/natural, luxury/refined,
playful/toy-like, editorial/magazine, brutalist/raw, art-deco/geometric, soft/pastel,
industrial/utilitarian... Execute that direction with precision and intentionality in
every section.

Every site MUST have a SIGNATURE — one memorable visual idea a visitor would describe
afterwards: an oversized display headline treatment (the headline ITSELF set huge —
NOT a watermark word laid over other text), a recurring graphic motif, an
unexpected accent color, a distinctive section rhythm, dramatic image treatments,
an asymmetric layout system. Carry the signature consistently across sections.

## FORBIDDEN — GENERIC AI AESTHETICS (CRITICAL!)
These patterns scream "AI-generated template". NEVER produce them:
- The cliché hero: diagonal violet/indigo gradient + centered white title + white
  pill button. Banned in ALL its variations.
- Identical 3-card rows repeated section after section with icon + title + text.
- Predictable section order applied regardless of the business.
- Timid, evenly-distributed color palettes. Commit: dominant colors with sharp
  accents beat washed-out gradients.
- Gradients as a default background filler. A gradient is allowed only as a
  deliberate, characterful choice (e.g. a dramatic duotone matching the brand) —
  not as decoration reflex.
- Ghost/watermark words over content: a giant low-opacity decorative word that
  crosses a headline or paragraph is BANNED (observed failure across models).
  If you want a background word: fully BEHIND the composition (zIndex below all
  text, never intersecting any text's box), set in the DISPLAY font of the site
  (never a fallback sans-serif), opacity 0.08 max, aria-hidden. When in doubt,
  drop the effect — readable typography always wins over decoration.
- Decorative strokes/underline accents that cross or strike through words of a
  headline. An accent line sits UNDER or BESIDE text, never on top of it.
Two consecutive sites you generate must NEVER look like siblings.

{language_instruction}

## MANDATORY OUTPUT FORMAT
You MUST return ONLY a JSON array of blocks. No explanation, no markdown.

Block structure:
{{
  "blockId": "unique-id",           // REQUIRED - format: "section-name-001"
  "element": "section",             // REQUIRED - see list below
  "classes": ["u-btn", "u-btn--primary"],  // the design system: see below
  "innerHTML": "Text here",         // For text elements (h1, p, span, etc.)
  "baseStyles": {{                   // CSS styles in camelCase
    "display": "flex",
    "padding": "80px 24px",
    "backgroundColor": "var(--primary-color)"
  }},
  "mobileStyles": {{                 // Styles for mobile (<576px)
    "padding": "40px 16px",
    "flexDirection": "column"
  }},
  "attributes": {{                   // For links and images
    "href": "/contact",
    "src": "/image.jpg",
    "alt": "Description"
  }},
  "children": [ ... ]              // Nested child blocks
}}

## SUPPORTED HTML ELEMENTS
- Structure: section, div, main, article, aside, nav
- Headings: h1, h2, h3, h4, h5, h6
- Text: p, span, label, blockquote
- Links/Buttons: a, button
- Media: img, video, iframe
- Lists: ul, ol, li
- Forms: form, input, textarea, select
- Other: hr, figure, figcaption

## THE DESIGN SYSTEM — ASK FOR A ROLE, DO NOT RESTATE IT

The site's corners, elevation, motion and hover behaviour are decided once and
live in CSS. Put a role in `classes` and the site supplies the rest:

| Role | classes | Never set on it |
|---|---|---|
| button | `["u-btn", "u-btn--primary"]` — also `--secondary`, `--outline`, `--ghost` | borderRadius, boxShadow, transition, hover styles |
| card / tile | `["u-card"]` — also `u-card--raised`, `u-card--flat` | borderRadius, boxShadow, border, padding |
| image | `["u-media"]` | borderRadius, overflow |
| text input | `["u-input"]` | borderRadius, border |
| a section whose background is a photo, with text on it | add `["u-over-image"]` — plus `--bottom`, `--diagonal` or `--soft` | any full-surface overlay of your own |
| a secondary button sitting ON that photo | `["u-btn", "u-btn--on-image"]` | backgroundColor, border, backdropFilter |

**Text over a photograph.** You cannot see the image you asked for, so you
cannot judge whether the text will read on it. Do not guess, and do not wash
the whole picture with a flat dark layer — that kills the photo, which is the
reason the section exists.

Put `u-over-image` on the section instead: it darkens only the side where the
text sits and fades to nothing across the rest, so the image still breathes.
Pick the variant that matches where your text is — the default covers a left
column, `--bottom` a caption, `--diagonal` a corner, `--soft` an image that is
already dark.

And a secondary button on a photo must be `u-btn--on-image`, never
`u-btn--outline`: a thin border over a photograph disappears into it. That is
the single most common way a generated hero comes out with an invisible
button.

Colours stay yours: a primary button may carry a different backgroundColor
when the section calls for it. What must not vary page to page is the SHAPE.

Two pages whose buttons have different corners look like two different sites.
That is the single most visible tell of a generated site — and the reason
these classes exist. Use them.

## CRITICAL CSS RULES
1. Properties in camelCase: backgroundColor (NOT background-color)
2. Use CSS variables for colors:
   - var(--primary-color): main color
   - var(--secondary-color): secondary color
   - var(--text-color): main text
   - var(--muted-color): secondary text
   - var(--surface-color): card backgrounds
   - var(--border-color): borders
3. Each blockId must be UNIQUE

## TYPOGRAPHY - USE CSS VARIABLES (IMPORTANT!)
Typography is managed globally via CSS variables. You do NOT need to specify fontSize/fontWeight for standard text elements:
- For h1, h2, h3, h4, p: DO NOT specify fontSize or fontWeight
- Global CSS automatically applies correct sizes via var(--h1-size), var(--h2-size), etc.
- Mobile styles are also handled automatically

EXCEPTION: You can override size ONLY for:
- Text on colored/hero backgrounds that needs specific color (color: "#ffffff")
- Elements that need to be larger than standard (display headlines)
- Labels, spans, or small UI text

CORRECT EXAMPLE (let CSS handle size):
{{
  "element": "h1",
  "innerHTML": "My title",
  "baseStyles": {{ "color": "#ffffff", "marginBottom": "24px" }}
}}

AVOID EXAMPLE (unnecessary override):
{{
  "element": "h1",
  "innerHTML": "My title",
  "baseStyles": {{ "fontSize": "48px", "fontWeight": "700" }}
}}

{design_brief_section}
{colors_section}
{font_section}

## THEME: {theme_name}
{theme_prompt}

## TEXT/BACKGROUND CONTRAST RULES (CRITICAL!)
ALWAYS ensure good contrast between text and background:

| Section background | Text color |
|--------------------|------------|
| Colored gradient (primary/secondary) | "#ffffff" |
| Colored background (var(--primary-color), etc.) | "#ffffff" |
| White background (#ffffff) | "var(--text-color)" |
| Light gray background (#f8fafc, #fafafa, #f5f5f5) | "var(--text-color)" |
| var(--surface-color) | "var(--text-color)" |

⚠️ COMMON ERROR TO AVOID: NEVER use color: "#ffffff" on a white or light gray section!

## CREATIVE GUIDELINES

### Structure
- Create a LOGICAL structure for the requested site type
- A florist ≠ a tech agency ≠ a restaurant
- Adapt the number of sections to content (4-8 depending on page)
- Homepage/one-page: 6-8 sections for a complete, rich site
- Inner pages: 4-6 sections

### Hero — the opening statement
The hero sets the aesthetic direction. Design it AS that direction, don't pick from
a menu. Strong, distinct approaches include (non-exhaustive — invent your own):
- Full-bleed photography with a treatment that matches the brand (deep solid-color
  overlay, duotone, partial image masking) — NOT the reflex semi-transparent gradient
- Split or off-center composition (60/40, 70/30) with overlapping elements
- Typography-led: an enormous display headline as the visual itself, generous space
- Editorial: headline + standfirst + full-width image below, magazine style
- Dark, atmospheric opening with one luminous accent
- Stacked/collage compositions with layered images and labels
Match the hero to the BUSINESS: a stone mason, a pediatric dentist and a jazz club
deserve radically different openings.

### Layout systems (vary per site, stay coherent within the site)
- **Grids**: 2, 3, 4, 5 columns depending on content
- **Asymmetric**: 60/40, 70/30, not always 50/50
- **Bento Grid**: Cards of varying sizes (1 large + 2 small)
- **Zigzag**: Left/right alternation for features
- **Full-bleed**: Sections that take 100% width
- **Centered narrow**: Narrow content (max-width: 700px) for reading
- **Overlap & grid-breaking**: elements crossing section boundaries, offset cards,
  images bleeding out of their column
- Density is a choice too: generous negative space OR controlled density — commit.

### FORBIDDEN - NEVER DO:
- **NEVER generate <nav> element** - header is managed globally
### CONTENT RHYTHM — ONE INSET FOR THE WHOLE SITE (CRITICAL)
The site header and footer put their content in a container of
`max-width: var(--container-width, 1280px); margin: 0 auto; padding: 0 24px`.
Every section you write MUST use that same container, or the page reads as a
staircase: the logo starts at one x, the headline at another, the footer at a
third.

So a section is TWO elements, never one:
1. the `<section>`: background, vertical padding, `padding-left/right: 24px`
2. a `<div>` inside it: `max-width: var(--container-width, 1280px)`,
   `margin-left/right: auto`, and ALL the layout (display grid/flex, columns,
   gap, alignment)

NEVER put `display: grid` or `display: flex` on the `<section>` itself, and
NEVER give a section a horizontal padding other than 24px — no `48px`, no `6vw`,
no `5%`. The background stays full-bleed; only the content is constrained.

- **NEVER generate <footer> element** - footer is managed globally
- **NEVER generate navigation menu** - it's managed globally
- ALWAYS start with a <section> (hero, main content, etc.)
- ALWAYS end with a <section> (CTA, contact, etc.)

### LAYOUT RULES — flex vs grid (CRITICAL)
Pick ONE display mode per block. NEVER mix flex-only and grid-only props
on the same element — the browser ignores the contradicting rules and
the layout collapses.

- If `display: flex`:
  ✓ ALLOWED: flexDirection, flexFlow, flexWrap, justifyContent, alignItems,
    alignContent, gap, order, flexGrow, flexShrink, flexBasis
  ✗ FORBIDDEN: gridTemplateColumns, gridTemplateRows, gridTemplateAreas,
    gridAutoColumns, gridAutoRows, gridAutoFlow, gridArea, gridColumn,
    gridRow

- If `display: grid`:
  ✓ ALLOWED: gridTemplateColumns, gridTemplateRows, gap, rowGap, columnGap,
    justifyContent, alignItems, placeItems, placeContent
  ✗ FORBIDDEN: flexDirection, flexFlow, flexWrap, flexGrow, flexShrink,
    flexBasis, order

- `gap`, `justifyContent`, `alignItems` work in BOTH — no restriction.

- For 2-4 column card layouts (collections, features, team members),
  PREFER `display: grid` with
  `gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))"` — it
  auto-wraps cleanly on mobile.

- For mobile override, set `gridTemplateColumns: "1fr"` in `mobileStyles`
  (keep display: grid).

### Content
- Write REALISTIC text ADAPTED to the business
- NO Lorem ipsum, NO "[Placeholder]"
- Invent the supporting cast: testimonial authors, partner names, credible stats
- NEVER invent a name for the site's own business. It has one, it is given to
  you, and it is the only one that may appear as the brand, in an eyebrow, in a
  signature or in a footer credit. A generated site that credits a studio nobody
  has ever heard of is the kind of mistake the client notices first.

### Design
- Vary layouts: 2/3/4 column grids, flex, asymmetric
- Build atmosphere and depth deliberately: dramatic or soft shadows, decorative
  borders, subtle layered backgrounds, big numerals, rule lines — whatever serves
  the chosen direction (rounded corners and gradients are options, not defaults)
- Ensure clear visual hierarchy (headings > subheadings > text)

### Section Heights
- Hero sections: use minHeight "70vh" to "90vh" for visual impact
- Other sections: let content determine height naturally
- Use generous padding (80px-120px) for comfortable spacing
- Hero minHeight ensures a strong first impression above the fold

### Background Colors (FORBIDDEN!)
⚠️ NEVER use var(--surface-color) or var(--background-color) for backgrounds.
ALWAYS use hex colors (#ffffff, #f8fafc) or gradients with real colors.

### Responsive
- ALWAYS include mobileStyles for main sections
- On mobile: stacked columns, reduced padding, smaller text

### Images (CRITICAL: Alt Text = AI Image Prompt)
- For images, use placehold.co placeholders with these sizes:
  - Hero/Banner: "https://placehold.co/1200x600/{primary_placeholder}/{primary_placeholder}"
  - Cards/Features: "https://placehold.co/400x300/{secondary_placeholder}/{secondary_placeholder}"
  - Team/Avatars: "https://placehold.co/80x80/{primary_placeholder}/ffffff?text=<INITIALS>"
  - Adapt the colors to the site's palette (background and text colors identical = clean solid block)
  - NEVER add ?text= on hero/card/banner placeholders: the service prints that text as a
    giant word across the image — it reads as a broken watermark crossing the content.
    (?text= is allowed ONLY for 80x80 avatar initials.)

- CRITICAL: The "alt" attribute MUST be a DETAILED description suitable for AI image generation.
  DO NOT use generic text like "Hero Image", "Feature", "Photo".
  Write a vivid description matching the BUSINESS CONTEXT:
  - GOOD: "Modern open office with developers collaborating around laptops, natural light"
  - GOOD: "Freshly baked sourdough bread on rustic wooden board, warm bakery lighting"
  - BAD: "Hero Image" / "Team photo" / "Feature"
- The placehold.co "text=" should be a SHORT version (2-4 words), URL-encoded with +
  Example: alt="Modern office with team collaborating" -> text=Team+Office

### Background images (technique)
For full-bleed imagery, CSS backgroundImage on the section works well:
- backgroundSize: "cover", backgroundPosition: "center"
- If text sits on the image, guarantee readability with a DELIBERATE treatment that
  matches your aesthetic direction: a deep solid-color overlay div (one brand color
  at high opacity), a dark scrim at the text side only, a duotone-colored placeholder,
  or text on a solid panel overlapping the image. Pick the one that serves the design.
- placehold.co URLs: 1920x1080 for full-bleed backgrounds.
- <img> elements (with detailed alt) are often the better choice for split,
  editorial and collage layouts.

{shortcodes_section}

## OUTPUT EXAMPLE — STRUCTURAL MECHANICS ONLY
This shows the JSON mechanics (nesting, styles, attributes), NOT a design to imitate.
Its layout, spacing and colors are placeholders — your output must follow YOUR
aesthetic direction for this site, not this shape.
[
  {{
    "blockId": "hero-section",
    "element": "section",
    "baseStyles": {{
      "display": "grid",
      "gridTemplateColumns": "7fr 5fr",
      "gap": "48px",
      "alignItems": "center",
      "minHeight": "80vh",
      "padding": "96px 48px",
      "backgroundColor": "#ffffff"
    }},
    "mobileStyles": {{ "gridTemplateColumns": "1fr", "padding": "56px 16px" }},
    "children": [
      {{
        "blockId": "hero-copy",
        "element": "div",
        "baseStyles": {{ "display": "flex", "flexDirection": "column", "gap": "24px" }},
        "children": [
          {{
            "blockId": "hero-title",
            "element": "h1",
            "innerHTML": "Headline written for this exact business",
            "baseStyles": {{ "color": "var(--text-color)" }}
          }},
          {{
            "blockId": "hero-sub",
            "element": "p",
            "innerHTML": "Supporting line in the brand's voice",
            "baseStyles": {{ "color": "var(--muted-color)" }}
          }},
          {{
            "blockId": "hero-cta",
            "element": "a",
            "classes": ["u-btn", "u-btn--primary"],
            "innerHTML": "Action label",
            "attributes": {{ "href": "/contact" }}
          }}
        ]
      }},
      {{
        "blockId": "hero-media",
        "element": "img",
        "classes": ["u-media"],
        "attributes": {{
          "src": "https://placehold.co/900x1100/{primary_placeholder}/ffffff?text=Scene",
          "alt": "Vivid, business-specific description used as an AI image prompt"
        }},
        "baseStyles": {{ "width": "100%", "height": "100%", "objectFit": "cover" }}
      }}
    ]
  }}
]

IMPORTANT: Return ONLY the JSON, without ```json or explanation.{interior_section}
"""


_HOMEPAGE_HERO_RULE = """

HERO — MANDATORY STRUCTURE (homepage):
Open with a FULL-BLEED BACKGROUND-IMAGE hero. The hero photo goes on the <section> itself as a
cover background WITH a dark legibility overlay (a linear-gradient OVER the image url), e.g.
backgroundImage: "linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.30)), url('<HERO image placeholder per the image rules above>')",
backgroundSize: "cover", backgroundPosition: "center", minHeight: "85vh".
On top, in a centered max-width container (left-aligned): an uppercase eyebrow, the H1 headline,
ONE subtitle line, then the primary + secondary CTAs. Hero text must be light (#ffffff) over the overlay.
HARD RULES: the image IS the section background and covers the WHOLE hero — NOT a small side card,
NOT a floating image box, NOT a flat single-color block beside text.
"""

_INTERIOR_SYSTEM_RULE = """

THIS PAGE IS AN INTERIOR PAGE — IT HAS NO HERO:
The section above on heroes and openings describes the homepage. This page is
rendered underneath the site's shared page header — a band carrying the
breadcrumb, the page title and one subtitle line, the same on every interior
page. Drawing a second opening puts two titles on top of each other, which is
the most visible way a generated page looks unfinished.

So for THIS page, override the hero guidance:
- The first <section> is the first section of REAL CONTENT, not an announcement.
- No full-bleed opening image, no eyebrow + display title + subtitle + CTA band,
  no minHeight of 70-90vh on the first section.
- Do not repeat the page title as an H1 anywhere.
- 4-6 sections of substance, opening straight into the subject.
"""


_INTERIOR_HEADER_RULE = """

INTERIOR PAGE OPENING — THE SITE ALREADY DRAWS ONE, DO NOT DRAW ANOTHER:
This page will be rendered underneath a shared page header: a band carrying the
breadcrumb, the page title and one subtitle line, identical on every interior
page of the site and styled from the theme.

So do NOT open with a hero, a title band, or any section whose job is to
announce the page. Start directly with the first section of real content. Do not
repeat the page title as an H1 — the band already prints it, and two titles
stacked is the most visible way a generated page looks unfinished.
"""


def get_page_generation_prompt(
    user_prompt: str,
    page_title: str = None,
    page_type: str = None,
    output_language: str = "French",
) -> str:
    """
    Build the user prompt for page generation.
    Includes specific instructions based on page type.

    Args:
        output_language: Language for generated content
    """
    context = f"Create a web page for: {user_prompt}"
    context += f"\n\nIMPORTANT: Generate all text content in {output_language}."

    if page_title:
        context += f"\n\nPage: {page_title}"

    if page_type:
        context += f"\nPage type: {page_type}"

        # Page instructions: context + goal + available tools
        # The AI has full creative freedom over structure and sections
        page_instructions = {
            "one_page": """
ONE-PAGE SITE:
This is a complete website on a single page with anchor navigation.
Present the business comprehensively: what they do, why they're great, and how to reach them.

A great one-page site feels like a journey — it draws the visitor in and keeps them scrolling.
Think of it as a story with many chapters: the hook, the promise, the proof, the details, and the call to action.
Aim for a rich, immersive experience with plenty of visual variety and content depth.

CRITICAL TECHNICAL REQUIREMENT — Anchor IDs:
Each main section MUST have an attributes: {"id": "..."} for anchor navigation.
The navigation menu uses these anchors: #hero, #services, #about, #contact
You may add more sections with custom IDs (e.g., #testimonials, #portfolio, #faq).

AVAILABLE SHORTCODE:
- Contact form: {% include 'builder/templates/includes/contact_form.html' %}
  Place it in the contact section to give visitors a way to reach out.""",

            "accueil": """
HOMEPAGE:
This is the front door of the website. First impressions matter.
Captivate the visitor immediately, tell the brand's story, and make them want to explore further.

A homepage should feel generous and complete — not like a teaser page.
The best homepages immerse visitors in the brand's world: they captivate with a strong hero,
build trust with social proof or values, showcase what the business offers, and leave
the visitor wanting to explore more. Don't hold back on content — a rich homepage
converts better than a sparse one.""",

            "accueil_ecommerce": """
E-COMMERCE HOMEPAGE:
This is a homepage first, shop second. The visitor should discover the brand's story,
feel trust and excitement, and be naturally drawn to explore products.
Balance storytelling with product showcase — don't just list products.

The best e-commerce homepages are rich and immersive. They combine brand storytelling,
product discovery, trust signals, and calls to action into a seamless experience.
Think about what makes a visitor trust and buy: a compelling hero, the brand's unique story,
product highlights, social proof (testimonials, trust badges, guarantees), clear advantages
(shipping, quality, returns), and inviting calls to action throughout.
Don't be minimal — give the visitor reasons to stay, explore, and buy.

AVAILABLE E-COMMERCE SHORTCODES (use where it feels natural):
- Product carousel: {%- set carousel_title = "Title here" -%}{%- set carousel_limit = 8 -%}{% include "webshop/templates/includes/product_carousel.html" %}
- Brand carousel: {%- set carousel_title = "Our Brands" -%}{% include "webshop/templates/includes/brand_carousel.html" %}
- Sale products: {%- set show_discounted_only = true -%}{% include "webshop/templates/includes/product_carousel.html" %}

TECHNICAL CONSTRAINTS:
- Shortcodes MUST be placed as innerHTML of a simple <section> or <div> — NOT inside grid/flex containers
- NEVER use dark backgrounds (#0a0a0a, #141414) for product sections — products need WHITE or LIGHT backgrounds
- Full shop link: /all-products""",

            "about": """
ABOUT PAGE:
Tell the company's story in an engaging way. Humanize the brand.
Create an emotional connection with the visitor through the company's history, values, and people.

AVAILABLE SHORTCODES (use if relevant):
- Team grid: {% include 'builder/templates/includes/team_grid.html' %}
- Company timeline: {% include 'builder/templates/includes/company_timeline.html' %}""",

            "services": """
SERVICES PAGE:
Present the company's services clearly and attractively.
Help visitors understand what's offered and why it matters to them.""",

            "contact": """
CONTACT PAGE:
Make it easy and inviting for visitors to get in touch. Build trust.
This page must have visual substance — not just a bare form.

After the standard interior page header, give the company's contact details, a map, and the
contact form. Add personality: a short intro message or a "Why reach out?" section.

AVAILABLE SHORTCODES:
- Contact form: {% include 'builder/templates/includes/contact_form.html' %}
- Google map: {% set address = "Full address" %}{% set height = "400px" %}{% include 'builder/templates/includes/google_map.html' %}
- Contact info block: {% include 'builder/templates/includes/contact_info.html' %}

NOTE: Create at least 4 sections — a contact page with only a form feels empty.""",

            "produits": """
PRODUCTS PAGE:
Showcase products attractively with images, prices, and key features.
Help visitors find what they're looking for.""",

            "blog": """
BLOG PAGE:
Display published blog articles dynamically using the Blog Listing shortcode.
Do NOT create fake static articles — use the shortcode which fetches real Blog Post data.

BLOG LISTING SHORTCODE:
{%- set blog_title = "Latest Articles" -%}
{%- set blog_limit = 6 -%}
{%- set blog_layout = "grid" -%}
{%- set view_more_link = "/blog" -%}
{% include "builder/templates/includes/blog_listing.html" %}

Parameters: blog_title, blog_category (filter), blog_limit (default 6), blog_sort_by (default published_on), blog_layout (grid/list), view_more_link, view_more_text.

TECHNICAL CONSTRAINT: The shortcode MUST be in a simple full-width container, not inside grid/flex.
Add a hero section above the blog listing with the page title and a short introduction.""",

            "collection": """
COLLECTION PAGE:
Showcase product collections or categories — not the full catalog.
Drive visitors toward specific product groups.

AVAILABLE E-COMMERCE SHORTCODES:
- Product carousel: {%- set carousel_title = "Title" -%}{%- set carousel_limit = 8 -%}{% include "webshop/templates/includes/product_carousel.html" %}
- Brand carousel: {%- set carousel_title = "Our Brands" -%}{% include "webshop/templates/includes/brand_carousel.html" %}
- Sale products: {%- set show_discounted_only = true -%}{% include "webshop/templates/includes/product_carousel.html" %}

TECHNICAL CONSTRAINTS:
- Shortcodes MUST be in a simple full-width container, not inside grid/flex
- Full shop link: /all-products""",

            "boutique": """
SHOP PAGE:
Present collections and product categories visually.
Same tools available as collection page.

AVAILABLE E-COMMERCE SHORTCODES:
- Product carousel: {%- set carousel_title = "Title" -%}{%- set carousel_limit = 8 -%}{% include "webshop/templates/includes/product_carousel.html" %}
- Brand carousel: {%- set carousel_title = "Our Brands" -%}{% include "webshop/templates/includes/brand_carousel.html" %}

TECHNICAL CONSTRAINT: Shortcodes must be in a full-width container, not inside grid/flex.""",
        }

        if page_type in page_instructions:
            context += _drop_unavailable_shortcodes(page_instructions[page_type])

        # Hero/header consistency: the homepage gets a full-bleed background-image
        # hero; EVERY interior page opens with the SAME compact header. Each page
        # is generated in a separate LLM call, so these rules must be prescriptive
        # enough that independent calls converge to one coherent design.
        if page_type in {"accueil", "accueil_ecommerce", "one_page"}:
            context += _HOMEPAGE_HERO_RULE
        elif page_type:
            context += _INTERIOR_HEADER_RULE

    return context


def _drop_unavailable_shortcodes(text: str) -> str:
    """Remove shortcode lines whose app is not on this bench.

    The webshop carousels exist on benches that carry the webshop app and
    nowhere else. Offering one to the model elsewhere produces a page that
    renders as a 500 — the sanitiser catches it afterwards, but a model told
    about a tool it cannot use spends its attention on it and writes a worse
    section around the hole.
    """
    import frappe
    import re as _re

    try:
        installed = set(frappe.get_installed_apps())
    except Exception:
        return text

    kept = []
    for line in text.split("\n"):
        apps = _re.findall(r'include\s+"([a-z_][a-z0-9_]*)/templates/', line)
        if apps and not all(app in installed for app in apps):
            continue
        kept.append(line)
    return "\n".join(kept)


def get_shortcodes_context(site_type: str = None) -> str:
    """
    Get shortcodes documentation for AI context.
    Includes both Builder Shortcodes and Builder AI Shortcodes.
    """
    import frappe

    lines = []

    # Get AI Shortcodes (Team Grid, Contact Form, etc.)
    try:
        ai_shortcodes = frappe.get_all(
            "Builder AI Shortcode",
            fields=["name1", "category", "shortcode", "description", "jinja_code", "use_when"]
        )
        if ai_shortcodes:
            lines.append("## AVAILABLE DYNAMIC SHORTCODES")
            lines.append("Use these shortcodes in innerHTML for dynamic content.\n")

            for sc in ai_shortcodes:
                lines.append(f"### {sc.name1} (`{sc.shortcode}`)")
                if sc.description:
                    lines.append(f"{sc.description}")
                if sc.use_when:
                    lines.append(f"**When to use:** {sc.use_when}")
                if sc.jinja_code:
                    lines.append(f"```jinja\n{sc.jinja_code}\n```")
                lines.append("")
    except Exception:
        pass

    # Whatever else is installed on this bench can add to the prompt through the
    # `unpress_ai_prompt_context` hook — one dotted path per contributor,
    # each returning a markdown block (or "" to stay out of it). That is how a
    # host application injects its own shortcodes without this app having to
    # know it exists.
    for method in frappe.get_hooks("unpress_ai_prompt_context") or []:
        try:
            contributor = frappe.get_attr(method)
            try:
                block = contributor(site_type=site_type)
            except TypeError:
                # a contributor that takes no argument is fine too
                block = contributor()
            if block:
                lines.append(block)
        except Exception as e:
            from unpress_core.ai.logging import ai_log

            ai_log("warning", "prompt context contributor failed", method=method, error=str(e)[:200])

    if not lines:
        return ""

    return "\n".join(lines)


__all__ = [
    "get_creative_system_prompt",
    "get_page_generation_prompt",
    "get_shortcodes_context",
]
