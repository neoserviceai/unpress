"""
Glassmorphism Theme
Frosted glass effect with blur, transparency, and subtle borders.
"""

GLASSMORPHISM_THEME = {
    "name": "Glassmorphism",
    "description": "Frosted glass aesthetic with blur effects and transparency",

    "colors": {
        "primary": "#8b5cf6",       # Violet
        "primaryLight": "#a78bfa",
        "secondary": "#ec4899",     # Pink
        "accent": "#06b6d4",        # Cyan
        "background": "#0f0f1a",    # Dark blue-black
        "backgroundGradient": "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
        "surface": "rgba(255, 255, 255, 0.05)",
        "surfaceHover": "rgba(255, 255, 255, 0.1)",
        "text": "#ffffff",
        "textMuted": "rgba(255, 255, 255, 0.7)",
        "border": "rgba(255, 255, 255, 0.1)",
        "borderLight": "rgba(255, 255, 255, 0.2)",
    },

    "characteristics": [
        "Frosted glass effect with backdrop-filter blur",
        "Semi-transparent backgrounds (rgba)",
        "Subtle white/light borders",
        "Dark gradient backgrounds",
        "Neon/bright accent colors that pop",
        "Soft glow effects on interactive elements",
        "Rounded corners (12-24px)",
        "Layered depth with multiple transparent surfaces",
    ],

    "typography": {
        "headingFont": "'Poppins', 'Inter', sans-serif",
        "bodyFont": "'Inter', sans-serif",
        "headingWeight": "600",
        "bodyWeight": "400",
    },

    "styles": {
        "glass_card": {
            "backgroundColor": "rgba(255, 255, 255, 0.05)",
            "backdropFilter": "blur(10px)",
            "WebkitBackdropFilter": "blur(10px)",
            "border": "1px solid rgba(255, 255, 255, 0.1)",
            "borderRadius": "16px",
            "padding": "24px",
        },
        "button": {
            "backgroundColor": "rgba(139, 92, 246, 0.8)",
            "backdropFilter": "blur(4px)",
            "border": "1px solid rgba(255, 255, 255, 0.2)",
            "borderRadius": "12px",
            "padding": "12px 24px",
            "color": "#ffffff",
            "fontWeight": "600",
            "boxShadow": "0 0 20px rgba(139, 92, 246, 0.3)",
            "transition": "all 300ms ease",
        },
        "section": {
            "padding": "80px 24px",
        },
        "hero": {
            "background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
            "minHeight": "100vh",
        },
    },

    "anti_patterns": [
        "Avoid solid, opaque backgrounds on cards",
        "Don't use harsh borders - keep them subtle and transparent",
        "Avoid light/white page backgrounds - needs dark background for effect",
        "Don't overuse blur - it's performance-heavy",
        "Avoid flat design without depth layers",
        "Don't use muted accent colors - they need to pop against dark bg",
    ],

    "prompt": """
STYLE: Glassmorphism
You are creating a glassmorphic design with these principles:

VISUAL LANGUAGE:
- Frosted glass effect using backdrop-filter: blur(10px)
- Semi-transparent backgrounds: rgba(255, 255, 255, 0.05-0.1)
- Subtle borders: 1px solid rgba(255, 255, 255, 0.1)
- Dark gradient page backgrounds
- Neon accent colors that glow
- Rounded corners (12-24px)

BACKGROUND:
- Page must have dark gradient background
- Deep, atmospheric backgrounds derived from the brief's palette (dark, layered)
- Without dark background, glass effect doesn't work

GLASS CARDS:
{
  "backgroundColor": "rgba(255, 255, 255, 0.05)",
  "backdropFilter": "blur(10px)",
  "border": "1px solid rgba(255, 255, 255, 0.1)",
  "borderRadius": "16px"
}

GLOW EFFECTS:
- Buttons/CTAs: boxShadow with color glow
- Example: "0 0 20px rgba(139, 92, 246, 0.3)"
- Hover: increase glow intensity

TYPOGRAPHY:
- White text on dark backgrounds
- Use rgba for muted text: "rgba(255, 255, 255, 0.7)"
- Clean sans-serif fonts
- Can use text-shadow for subtle glow on headings

LAYERING:
- Create depth with multiple glass layers
- Foreground elements more opaque than background
- Use z-index strategically
""",
}
