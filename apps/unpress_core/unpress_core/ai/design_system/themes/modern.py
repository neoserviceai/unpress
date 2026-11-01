"""
Modern Theme
Clean, professional design with subtle gradients and smooth transitions.
"""

MODERN_THEME = {
    "name": "Modern",
    "description": "Clean and professional design with subtle sophistication",

    "colors": {
        "primary": "#6366f1",       # Indigo
        "primaryLight": "#818cf8",
        "primaryDark": "#4f46e5",
        "secondary": "#8b5cf6",     # Violet
        "accent": "#06b6d4",        # Cyan
        "background": "#ffffff",
        "surface": "#f8fafc",
        "surfaceAlt": "#f1f5f9",
        "text": "#0f172a",
        "textMuted": "#64748b",
        "border": "#e2e8f0",
    },

    "characteristics": [
        "Clean lines and generous white space",
        "Subtle shadows for depth (soft, not harsh)",
        "Smooth border-radius (8-16px)",
        "Subtle gradients for backgrounds",
        "Clear visual hierarchy",
        "Professional typography with good contrast",
        "Consistent spacing throughout",
        "Hover states with smooth transitions",
    ],

    "typography": {
        "headingFont": "'Inter', sans-serif",
        "bodyFont": "'Inter', sans-serif",
        "headingWeight": "700",
        "bodyWeight": "400",
    },

    "styles": {
        "button": {
            "borderRadius": "8px",
            "padding": "12px 24px",
            "fontWeight": "600",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.1)",
            "transition": "all 250ms ease",
        },
        "card": {
            "borderRadius": "12px",
            "boxShadow": "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)",
            "padding": "24px",
        },
        "section": {
            "padding": "80px 24px",
        },
        "hero": {
            "background": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
            "minHeight": "90vh",
        },
    },

    "anti_patterns": [
        "Avoid harsh, solid shadows",
        "Don't use more than 2-3 accent colors",
        "Avoid tiny text (below 14px for body)",
        "Don't use pure black (#000) for text",
        "Avoid cramped layouts - use generous spacing",
        "Don't mix too many different border-radius values",
    ],

    "prompt": """
STYLE: Modern Professional
You are creating a modern, professional design with these principles:

VISUAL LANGUAGE:
- Clean, uncluttered layouts with generous white space
- Subtle depth through soft shadows (not harsh drop shadows)
- Smooth border-radius (8-16px) for a friendly feel
- Gradients used sparingly for hero sections or CTAs
- Color palette: the design brief's palette — one dominant color with sharp accents

LAYOUT PRINCIPLES:
- Clear visual hierarchy: one hero element per section
- Consistent 8px grid system
- Asymmetric layouts for visual interest (60/40, 70/30 splits)
- Cards with subtle elevation
- Generous padding in sections (80px vertical on desktop)

TYPOGRAPHY:
- Inter or similar clean sans-serif
- Headline sizes: 48-72px for heroes, 36px for section titles
- Body: 16-18px with 1.6 line-height
- Clear contrast between headings and body text

INTERACTIVITY:
- All interactive elements have hover states
- Smooth transitions (250ms ease)
- Buttons have subtle shadow lift on hover
- Links have color change on hover
""",
}
