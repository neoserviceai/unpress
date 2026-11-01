"""
Design Tokens
Centralized design values for consistent AI-generated UI.
"""

from typing import Any


DESIGN_TOKENS = {
    # Spacing scale (based on 4px base unit)
    "spacing": {
        "0": "0px",
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "5": "20px",
        "6": "24px",
        "8": "32px",
        "10": "40px",
        "12": "48px",
        "16": "64px",
        "20": "80px",
        "24": "96px",
        "32": "128px",
        # Semantic spacing
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px",
        "2xl": "48px",
        "3xl": "64px",
        "section": "80px",
        "section-lg": "120px",
    },

    # Typography
    "typography": {
        "fontFamily": {
            "sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "serif": "'Georgia', 'Times New Roman', serif",
            "mono": "'JetBrains Mono', 'Fira Code', Consolas, monospace",
            "display": "'Poppins', 'Inter', sans-serif",
        },
        "fontSize": {
            "xs": "12px",
            "sm": "14px",
            "base": "16px",
            "lg": "18px",
            "xl": "20px",
            "2xl": "24px",
            "3xl": "30px",
            "4xl": "36px",
            "5xl": "48px",
            "6xl": "60px",
            "7xl": "72px",
            "8xl": "96px",
        },
        "fontWeight": {
            "thin": "100",
            "light": "300",
            "normal": "400",
            "medium": "500",
            "semibold": "600",
            "bold": "700",
            "extrabold": "800",
            "black": "900",
        },
        "lineHeight": {
            "none": "1",
            "tight": "1.25",
            "snug": "1.375",
            "normal": "1.5",
            "relaxed": "1.625",
            "loose": "2",
        },
        "letterSpacing": {
            "tighter": "-0.05em",
            "tight": "-0.025em",
            "normal": "0em",
            "wide": "0.025em",
            "wider": "0.05em",
            "widest": "0.1em",
        },
    },

    # Colors (using CSS variables for theming)
    "colors": {
        # Semantic colors (reference Frappe Builder variables)
        "primary": "var(--primary-color)",
        "secondary": "var(--secondary-color)",
        "accent": "var(--accent-color)",
        "background": "var(--surface-color)",
        "surface": "var(--surface-color)",
        "text": "var(--text-color)",
        "textMuted": "var(--muted-color)",
        "border": "var(--border-color)",

        # Fixed colors for specific use cases
        "white": "#ffffff",
        "black": "#000000",
        "transparent": "transparent",

        # Grayscale
        "gray": {
            "50": "#f9fafb",
            "100": "#f3f4f6",
            "200": "#e5e7eb",
            "300": "#d1d5db",
            "400": "#9ca3af",
            "500": "#6b7280",
            "600": "#4b5563",
            "700": "#374151",
            "800": "#1f2937",
            "900": "#111827",
            "950": "#030712",
        },

        # Status colors
        "success": "#10b981",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "info": "#3b82f6",
    },

    # Shadows
    "shadows": {
        "none": "none",
        "xs": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        "sm": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
        "md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
        "lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
        "xl": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
        "2xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        "inner": "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
        # Colored shadows
        "primary": "0 4px 14px 0 rgba(99, 102, 241, 0.25)",
        "soft": "0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)",
        "elevated": "0 10px 40px rgba(0, 0, 0, 0.15)",
    },

    # Border radius
    "borderRadius": {
        "none": "0px",
        "sm": "4px",
        "md": "6px",
        "lg": "8px",
        "xl": "12px",
        "2xl": "16px",
        "3xl": "24px",
        "full": "9999px",
    },

    # Border widths
    "borderWidth": {
        "0": "0px",
        "1": "1px",
        "2": "2px",
        "3": "3px",
        "4": "4px",
        "8": "8px",
    },

    # Transitions
    "transitions": {
        "fast": "150ms ease",
        "normal": "250ms ease",
        "slow": "350ms ease",
        "bounce": "500ms cubic-bezier(0.68, -0.55, 0.265, 1.55)",
    },

    # Z-index scale
    "zIndex": {
        "auto": "auto",
        "0": "0",
        "10": "10",
        "20": "20",
        "30": "30",
        "40": "40",
        "50": "50",
        "dropdown": "1000",
        "sticky": "1020",
        "fixed": "1030",
        "modal": "1050",
        "popover": "1060",
        "tooltip": "1070",
    },

    # Breakpoints (for reference in prompts)
    "breakpoints": {
        "mobile": "576px",
        "tablet": "768px",
        "desktop": "1024px",
        "wide": "1280px",
        "ultrawide": "1536px",
    },

    # Container widths
    "containers": {
        "sm": "640px",
        "md": "768px",
        "lg": "1024px",
        "xl": "1280px",
        "2xl": "1536px",
        "prose": "65ch",
    },

    # Aspect ratios
    "aspectRatios": {
        "auto": "auto",
        "square": "1 / 1",
        "video": "16 / 9",
        "portrait": "3 / 4",
        "landscape": "4 / 3",
        "wide": "21 / 9",
    },
}


def get_token(path: str, default: Any = None) -> Any:
    """
    Get a design token by dot-notation path.

    Examples:
        get_token("spacing.md") -> "16px"
        get_token("colors.gray.500") -> "#6b7280"
        get_token("typography.fontSize.2xl") -> "24px"
    """
    parts = path.split(".")
    value = DESIGN_TOKENS

    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default

    return value


def get_spacing(size: str) -> str:
    """Get spacing token value"""
    return get_token(f"spacing.{size}", "16px")


def get_font_size(size: str) -> str:
    """Get font size token value"""
    return get_token(f"typography.fontSize.{size}", "16px")


def get_color(name: str) -> str:
    """Get color token value"""
    return get_token(f"colors.{name}", "inherit")


def get_shadow(size: str) -> str:
    """Get shadow token value"""
    return get_token(f"shadows.{size}", "none")


def get_radius(size: str) -> str:
    """Get border radius token value"""
    return get_token(f"borderRadius.{size}", "0px")


# Component-specific token compositions
COMPONENT_TOKENS = {
    "button": {
        "primary": {
            "padding": f"{get_spacing('3')} {get_spacing('6')}",
            "fontSize": get_font_size("base"),
            "fontWeight": "600",
            "borderRadius": get_radius("lg"),
            "transition": get_token("transitions.normal"),
        },
        "secondary": {
            "padding": f"{get_spacing('3')} {get_spacing('6')}",
            "fontSize": get_font_size("base"),
            "fontWeight": "500",
            "borderRadius": get_radius("lg"),
            "border": f"{get_token('borderWidth.1')} solid",
        },
        "ghost": {
            "padding": f"{get_spacing('2')} {get_spacing('4')}",
            "fontSize": get_font_size("sm"),
            "fontWeight": "500",
            "borderRadius": get_radius("md"),
        },
    },
    "card": {
        "default": {
            "padding": get_spacing("6"),
            "borderRadius": get_radius("xl"),
            "boxShadow": get_shadow("md"),
        },
        "elevated": {
            "padding": get_spacing("8"),
            "borderRadius": get_radius("2xl"),
            "boxShadow": get_shadow("xl"),
        },
        "flat": {
            "padding": get_spacing("6"),
            "borderRadius": get_radius("lg"),
            "border": f"{get_token('borderWidth.1')} solid var(--border-color)",
        },
    },
    "input": {
        "default": {
            "padding": f"{get_spacing('3')} {get_spacing('4')}",
            "fontSize": get_font_size("base"),
            "borderRadius": get_radius("lg"),
            "border": f"{get_token('borderWidth.1')} solid var(--border-color)",
        },
    },
    "section": {
        "default": {
            "padding": f"{get_spacing('section')} {get_spacing('6')}",
        },
        "compact": {
            "padding": f"{get_spacing('12')} {get_spacing('6')}",
        },
        "spacious": {
            "padding": f"{get_spacing('section-lg')} {get_spacing('6')}",
        },
    },
}


def get_component_tokens(component: str, variant: str = "default") -> dict:
    """Get token composition for a component variant"""
    return COMPONENT_TOKENS.get(component, {}).get(variant, {})


__all__ = [
    "DESIGN_TOKENS",
    "COMPONENT_TOKENS",
    "get_token",
    "get_spacing",
    "get_font_size",
    "get_color",
    "get_shadow",
    "get_radius",
    "get_component_tokens",
]
