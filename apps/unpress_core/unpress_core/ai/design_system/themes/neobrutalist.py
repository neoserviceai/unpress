"""
Neobrutalist Theme
Bold, high-contrast design with thick borders and offset shadows.
"""

NEOBRUTALIST_THEME = {
    "name": "Neobrutalist",
    "description": "Bold, unapologetic design with thick borders and stark contrasts",

    "colors": {
        "primary": "#000000",
        "secondary": "#ff6b6b",     # Coral
        "accent": "#4ecdc4",        # Teal
        "background": "#fffef0",    # Warm cream
        "surface": "#ffffff",
        "text": "#000000",
        "textMuted": "#333333",
        "border": "#000000",
        "yellow": "#ffd93d",
        "pink": "#ff6b9d",
    },

    "characteristics": [
        "Thick borders (2-4px solid black)",
        "Offset box shadows (4-8px solid, no blur)",
        "High contrast color combinations",
        "Bold, impactful typography",
        "No subtle gradients - solid colors only",
        "Zero or minimal border-radius",
        "Uppercase headings with tight letter-spacing",
        "Geometric, blocky shapes",
    ],

    "typography": {
        "headingFont": "'Space Grotesk', 'Inter', sans-serif",
        "bodyFont": "'Inter', sans-serif",
        "headingWeight": "800",
        "bodyWeight": "400",
    },

    "styles": {
        "button": {
            "border": "3px solid #000000",
            "boxShadow": "4px 4px 0 #000000",
            "borderRadius": "0px",
            "padding": "14px 28px",
            "fontWeight": "700",
            "textTransform": "uppercase",
            "letterSpacing": "0.05em",
            "transition": "transform 150ms ease, box-shadow 150ms ease",
        },
        "card": {
            "border": "2px solid #000000",
            "boxShadow": "6px 6px 0 #000000",
            "borderRadius": "0px",
            "padding": "24px",
        },
        "section": {
            "padding": "80px 24px",
            "borderBottom": "2px solid #000000",
        },
        "hero": {
            "backgroundColor": "#ffd93d",
            "minHeight": "90vh",
            "border": "none",
        },
    },

    "anti_patterns": [
        "NO gradients - use solid colors only",
        "NO blurred shadows - offset shadows only (Xpx Ypx 0 color)",
        "NO rounded corners - use 0px border-radius",
        "NO subtle/muted colors - high contrast only",
        "NO thin borders - minimum 2px",
        "NO soft, corporate aesthetics",
        "NO generic stock photo feel",
    ],

    "prompt": """
STYLE: Neobrutalist
You are creating a bold neobrutalist design with these principles:

VISUAL LANGUAGE:
- Thick black borders (2-4px) on all containers
- Offset shadows with NO blur (e.g., "6px 6px 0 #000000")
- Sharp corners - NO border-radius
- High contrast: black on bright colors
- Bold accent colors from the brief's palette (loud, unapologetic)
- Cream/warm white backgrounds (#fffef0)

LAYOUT PRINCIPLES:
- Blocky, geometric compositions
- Intentional "rough" aesthetic
- Overlapping elements are encouraged
- Asymmetric but balanced
- Elements should feel "floating" with offset shadows

TYPOGRAPHY:
- Bold, impactful headlines (700-900 weight)
- Uppercase for emphasis with letter-spacing
- High contrast text
- Can mix serif and sans-serif dramatically

EFFECTS:
- Hover: transform translateY(-2px) with shadow growing
- No smooth transitions - can be snappy (150ms)
- Interactive elements should feel tactile

EXAMPLE BUTTON:
{
  "border": "3px solid #000000",
  "boxShadow": "4px 4px 0 #000000",
  "borderRadius": "0px",
  "backgroundColor": "#ff6b6b",
  "color": "#000000",
  "fontWeight": "700",
  "textTransform": "uppercase"
}
""",
}
