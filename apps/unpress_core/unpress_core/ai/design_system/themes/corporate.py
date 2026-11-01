"""
Corporate Theme
Professional, trustworthy design for business applications.
"""

CORPORATE_THEME = {
    "name": "Corporate",
    "description": "Professional and trustworthy design for business",

    "colors": {
        "primary": "#2563eb",       # Blue
        "primaryLight": "#3b82f6",
        "primaryDark": "#1d4ed8",
        "secondary": "#059669",     # Green (success/growth)
        "accent": "#f59e0b",        # Amber (CTA)
        "background": "#ffffff",
        "surface": "#f9fafb",
        "surfaceAlt": "#f3f4f6",
        "text": "#111827",
        "textMuted": "#6b7280",
        "border": "#e5e7eb",
        "success": "#10b981",
        "warning": "#f59e0b",
        "error": "#ef4444",
    },

    "characteristics": [
        "Clean, organized layouts",
        "Trustworthy blue color palette",
        "Clear information hierarchy",
        "Professional typography",
        "Subtle shadows for depth",
        "Consistent spacing and alignment",
        "Data visualization friendly",
        "Accessible color contrasts",
    ],

    "typography": {
        "headingFont": "'Inter', -apple-system, sans-serif",
        "bodyFont": "'Inter', -apple-system, sans-serif",
        "headingWeight": "600",
        "bodyWeight": "400",
    },

    "styles": {
        "button": {
            "backgroundColor": "#2563eb",
            "color": "#ffffff",
            "border": "none",
            "borderRadius": "6px",
            "padding": "10px 20px",
            "fontSize": "14px",
            "fontWeight": "500",
            "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.05)",
            "transition": "all 200ms ease",
        },
        "button_secondary": {
            "backgroundColor": "#ffffff",
            "color": "#374151",
            "border": "1px solid #d1d5db",
            "borderRadius": "6px",
            "padding": "10px 20px",
            "fontSize": "14px",
            "fontWeight": "500",
        },
        "card": {
            "backgroundColor": "#ffffff",
            "border": "1px solid #e5e7eb",
            "borderRadius": "8px",
            "padding": "24px",
            "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
        },
        "section": {
            "padding": "64px 24px",
        },
        "hero": {
            "backgroundColor": "#1e40af",
            "backgroundImage": "linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)",
            "minHeight": "70vh",
        },
    },

    "anti_patterns": [
        "Avoid playful or casual design elements",
        "Don't use too many colors - stick to blue + 1-2 accents",
        "Avoid very large font sizes (keep heroes under 56px)",
        "Don't sacrifice readability for style",
        "Avoid trendy effects that may look dated",
        "Don't use informal language in UI text",
    ],

    "prompt": """
STYLE: Corporate Professional
You are creating a professional corporate design with these principles:

VISUAL LANGUAGE:
- Trust-building blue color palette
- Clean, organized information hierarchy
- Professional but not boring
- Subtle depth through shadows
- Consistent border-radius (6-8px)
- Data and metrics friendly

LAYOUT PRINCIPLES:
- Clear content structure
- Logical information flow
- Readable line lengths (60-75 characters)
- Balanced whitespace (not excessive)
- Grid-aligned elements

COLOR USAGE:
- Primary: the brief's primary color, used with institutional restraint
- Success/positive: a clearly positive tone fitting the palette
- CTA/attention: the brief's accent color
- Neutral grays for text and borders
- High contrast for accessibility

TYPOGRAPHY:
- System fonts or Inter for reliability
- Clear hierarchy (don't over-style)
- Body text at 14-16px
- Headlines 24-40px range
- Consistent font weights (400, 500, 600)

TRUST ELEMENTS:
- Social proof sections
- Client logos
- Statistics and data
- Testimonials with photos
- Security/certification badges

The goal is professional credibility - designs that make users trust the brand.
""",
}
