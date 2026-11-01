"""
Minimal Theme
Ultra-clean design with maximum whitespace and typography focus.
"""

MINIMAL_THEME = {
    "name": "Minimal",
    "description": "Ultra-clean design focused on typography and whitespace",

    "colors": {
        "primary": "#000000",
        "secondary": "#666666",
        "accent": "#000000",
        "background": "#ffffff",
        "surface": "#fafafa",
        "text": "#1a1a1a",
        "textMuted": "#666666",
        "border": "#eaeaea",
    },

    "characteristics": [
        "Maximum whitespace - let content breathe",
        "Typography as the main design element",
        "Monochromatic or very limited color palette",
        "Subtle or no shadows",
        "Thin, delicate borders (1px max)",
        "Simple, elegant interactions",
        "Grid-based layouts",
        "No decorative elements",
    ],

    "typography": {
        "headingFont": "'Inter', system-ui, sans-serif",
        "bodyFont": "'Inter', system-ui, sans-serif",
        "headingWeight": "500",
        "bodyWeight": "400",
        # Can also use serif for elegant minimal
        "altHeadingFont": "'Playfair Display', Georgia, serif",
    },

    "styles": {
        "button": {
            "backgroundColor": "#000000",
            "color": "#ffffff",
            "border": "none",
            "borderRadius": "0px",
            "padding": "14px 32px",
            "fontSize": "14px",
            "fontWeight": "500",
            "letterSpacing": "0.05em",
            "textTransform": "uppercase",
            "transition": "opacity 200ms ease",
        },
        "button_outline": {
            "backgroundColor": "transparent",
            "color": "#000000",
            "border": "1px solid #000000",
            "borderRadius": "0px",
            "padding": "14px 32px",
            "fontSize": "14px",
            "fontWeight": "500",
            "letterSpacing": "0.05em",
            "textTransform": "uppercase",
        },
        "card": {
            "backgroundColor": "#ffffff",
            "border": "1px solid #eaeaea",
            "borderRadius": "0px",
            "padding": "32px",
        },
        "section": {
            "padding": "120px 24px",  # Extra generous spacing
        },
        "hero": {
            "backgroundColor": "#ffffff",
            "minHeight": "100vh",
            "display": "flex",
            "alignItems": "center",
        },
    },

    "anti_patterns": [
        "NO decorative elements or ornaments",
        "NO heavy shadows",
        "NO bright/saturated colors (except as rare accent)",
        "NO rounded corners (or very minimal, 4px max)",
        "NO busy layouts - embrace emptiness",
        "NO multiple font families (stick to one)",
        "NO gradients",
    ],

    "prompt": """
STYLE: Minimal
You are creating an ultra-minimal design with these principles:

VISUAL LANGUAGE:
- Whitespace is the primary design element
- Typography carries the design
- Black, white, and grays only (with rare accent)
- No decorative elements
- Thin borders (1px) or no borders
- No shadows or very subtle ones

LAYOUT PRINCIPLES:
- Generous vertical spacing (120px+ between sections)
- Asymmetric but balanced layouts
- Content should feel like it's floating in space
- Maximum 60-70 characters per line for readability
- Strong alignment to invisible grid

TYPOGRAPHY:
- One font family (Inter, system fonts, or elegant serif)
- Large, bold headlines that anchor the page
- Comfortable body text (16-18px, 1.7 line-height)
- Uppercase with letter-spacing for labels
- Typography IS the visual design

INTERACTIONS:
- Subtle - opacity changes, underlines appearing
- No dramatic hover effects
- Everything should feel effortless

COLOR:
- 90% black and white
- One accent color used sparingly (if at all)
- Gray tones for hierarchy (#666, #999, #ccc)

EXAMPLE SECTION:
{
  "backgroundColor": "#ffffff",
  "padding": "120px 24px",
  "textAlign": "center"
}

The goal is elegant restraint - if in doubt, remove it.
""",
}
