"""
Creative Theme
Bold, expressive design for creative agencies and portfolios.
"""

CREATIVE_THEME = {
    "name": "Creative",
    "description": "Bold, expressive design for creative work and portfolios",

    "colors": {
        "primary": "#ff3366",       # Hot pink
        "secondary": "#00d4ff",     # Electric cyan
        "accent": "#ffcc00",        # Yellow
        "background": "#0a0a0a",    # Near black
        "surface": "#141414",
        "surfaceAlt": "#1f1f1f",
        "text": "#ffffff",
        "textMuted": "#888888",
        "border": "#333333",
        "gradient1": "linear-gradient(135deg, #ff3366 0%, #ff6b6b 100%)",
        "gradient2": "linear-gradient(135deg, #00d4ff 0%, #00ff88 100%)",
    },

    "characteristics": [
        "Bold, saturated colors on dark backgrounds",
        "Large typography that makes a statement",
        "Animated/interactive elements",
        "Unexpected layouts and compositions",
        "Mix of imagery and geometric shapes",
        "Gradient accents",
        "Generous scale differences (contrast)",
        "Portfolio/gallery focused layouts",
    ],

    "typography": {
        "headingFont": "'Space Grotesk', 'Syne', sans-serif",
        "bodyFont": "'Inter', sans-serif",
        "headingWeight": "700",
        "bodyWeight": "400",
        "displaySize": "96px",  # Go big
    },

    "styles": {
        "button": {
            "background": "linear-gradient(135deg, #ff3366 0%, #ff6b6b 100%)",
            "color": "#ffffff",
            "border": "none",
            "borderRadius": "50px",
            "padding": "16px 32px",
            "fontSize": "16px",
            "fontWeight": "600",
            "boxShadow": "0 4px 20px rgba(255, 51, 102, 0.4)",
            "transition": "transform 300ms ease, box-shadow 300ms ease",
        },
        "button_outline": {
            "background": "transparent",
            "color": "#ffffff",
            "border": "2px solid #ffffff",
            "borderRadius": "50px",
            "padding": "14px 30px",
            "fontSize": "16px",
            "fontWeight": "600",
        },
        "card": {
            "backgroundColor": "#141414",
            "border": "1px solid #333333",
            "borderRadius": "16px",
            "padding": "32px",
            "overflow": "hidden",
        },
        "section": {
            "padding": "100px 24px",
        },
        "hero": {
            "backgroundColor": "#0a0a0a",
            "minHeight": "100vh",
            "overflow": "hidden",
        },
    },

    "anti_patterns": [
        "Avoid conservative/safe color choices",
        "Don't be afraid of large scale elements",
        "Avoid predictable grid layouts",
        "Don't use generic stock imagery",
        "Avoid small, timid typography",
        "Don't overload with text - let visuals speak",
        "Avoid light backgrounds (stay dark)",
    ],

    "prompt": """
STYLE: Creative / Portfolio
You are creating a bold creative design with these principles:

VISUAL LANGUAGE:
- Dark backgrounds (#0a0a0a, #141414)
- Vibrant accent colors that pop (hot pink, electric cyan, yellow)
- Large, confident typography
- Gradient accents on buttons and highlights
- Mix of organic and geometric elements
- Strong visual contrast

LAYOUT PRINCIPLES:
- Break the grid intentionally
- Overlapping elements
- Dramatic scale differences
- Full-bleed images
- Asymmetric but balanced
- Scroll-driven reveals

TYPOGRAPHY:
- Display fonts for headlines (Space Grotesk, Syne)
- Headlines can be MASSIVE (72-120px)
- Mix weights dramatically (100 vs 900)
- Creative text arrangements
- Can use vertical/rotated text

COLOR:
- Dark base (#0a0a0a)
- Vibrant accents from the brief's palette (saturated, high-energy)
- Gradients for CTAs and highlights
- White for primary text
- Gray (#888) for secondary text

INTERACTIVITY:
- Hover effects that transform
- Smooth but noticeable transitions
- Elements that respond to interaction
- Cursor effects if possible

IMAGERY:
- High quality, curated visuals
- Creative treatments (duotone, overlays)
- Full-width/bleed images
- Video backgrounds for heroes

The goal is to impress and inspire - this is a showcase of creativity.
""",
}
