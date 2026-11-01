"""
Base Styles
Pre-defined style compositions for common UI elements.
"""

from typing import Optional
from unpress_core.ai.design_system.tokens import get_token, get_component_tokens


# Base styles for layout elements
BASE_STYLES = {
    # Container styles
    "container": {
        "width": "100%",
        "maxWidth": "1280px",
        "marginLeft": "auto",
        "marginRight": "auto",
        "paddingLeft": "24px",
        "paddingRight": "24px",
    },
    "container_narrow": {
        "width": "100%",
        "maxWidth": "768px",
        "marginLeft": "auto",
        "marginRight": "auto",
        "paddingLeft": "24px",
        "paddingRight": "24px",
    },
    "container_wide": {
        "width": "100%",
        "maxWidth": "1536px",
        "marginLeft": "auto",
        "marginRight": "auto",
        "paddingLeft": "24px",
        "paddingRight": "24px",
    },

    # Flex utilities
    "flex_center": {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
    },
    "flex_between": {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "space-between",
    },
    "flex_col": {
        "display": "flex",
        "flexDirection": "column",
    },
    "flex_col_center": {
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
    },

    # Grid utilities
    "grid_2": {
        "display": "grid",
        "gridTemplateColumns": "repeat(2, 1fr)",
        "gap": "24px",
    },
    "grid_3": {
        "display": "grid",
        "gridTemplateColumns": "repeat(3, 1fr)",
        "gap": "24px",
    },
    "grid_4": {
        "display": "grid",
        "gridTemplateColumns": "repeat(4, 1fr)",
        "gap": "24px",
    },
    "grid_auto": {
        "display": "grid",
        "gridTemplateColumns": "repeat(auto-fit, minmax(280px, 1fr))",
        "gap": "24px",
    },

    # Section styles
    "section": {
        "padding": "80px 24px",
    },
    "section_hero": {
        "minHeight": "90vh",
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "justifyContent": "center",
        "padding": "80px 24px",
    },
    "section_alt": {
        "padding": "80px 24px",
        "backgroundColor": "var(--surface-color)",
    },

    # Typography
    "heading_1": {
        "fontSize": "48px",
        "fontWeight": "700",
        "lineHeight": "1.2",
        "letterSpacing": "-0.025em",
        "color": "var(--text-color)",
    },
    "heading_2": {
        "fontSize": "36px",
        "fontWeight": "600",
        "lineHeight": "1.3",
        "letterSpacing": "-0.02em",
        "color": "var(--text-color)",
    },
    "heading_3": {
        "fontSize": "24px",
        "fontWeight": "600",
        "lineHeight": "1.4",
        "color": "var(--text-color)",
    },
    "body": {
        "fontSize": "16px",
        "fontWeight": "400",
        "lineHeight": "1.6",
        "color": "var(--text-color)",
    },
    "body_large": {
        "fontSize": "18px",
        "fontWeight": "400",
        "lineHeight": "1.7",
        "color": "var(--muted-color)",
    },
    "caption": {
        "fontSize": "14px",
        "fontWeight": "400",
        "lineHeight": "1.5",
        "color": "var(--muted-color)",
    },
    "overline": {
        "fontSize": "12px",
        "fontWeight": "600",
        "textTransform": "uppercase",
        "letterSpacing": "0.1em",
        "color": "var(--primary-color)",
    },
}


# Mobile styles (< 576px)
MOBILE_STYLES = {
    "container": {
        "paddingLeft": "16px",
        "paddingRight": "16px",
    },
    "section": {
        "padding": "48px 16px",
    },
    "section_hero": {
        "minHeight": "80vh",
        "padding": "48px 16px",
    },
    "heading_1": {
        "fontSize": "32px",
    },
    "heading_2": {
        "fontSize": "28px",
    },
    "heading_3": {
        "fontSize": "20px",
    },
    "grid_2": {
        "gridTemplateColumns": "1fr",
    },
    "grid_3": {
        "gridTemplateColumns": "1fr",
    },
    "grid_4": {
        "gridTemplateColumns": "repeat(2, 1fr)",
    },
}


# Component styles
COMPONENT_STYLES = {
    "button_primary": {
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "gap": "8px",
        "padding": "12px 24px",
        "fontSize": "16px",
        "fontWeight": "600",
        "borderRadius": "8px",
        "backgroundColor": "var(--primary-color)",
        "color": "#ffffff",
        "border": "none",
        "cursor": "pointer",
        "transition": "all 250ms ease",
    },
    "button_secondary": {
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "gap": "8px",
        "padding": "12px 24px",
        "fontSize": "16px",
        "fontWeight": "500",
        "borderRadius": "8px",
        "backgroundColor": "transparent",
        "color": "var(--text-color)",
        "border": "1px solid var(--border-color)",
        "cursor": "pointer",
        "transition": "all 250ms ease",
    },
    "button_ghost": {
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "gap": "8px",
        "padding": "8px 16px",
        "fontSize": "14px",
        "fontWeight": "500",
        "borderRadius": "6px",
        "backgroundColor": "transparent",
        "color": "var(--text-color)",
        "border": "none",
        "cursor": "pointer",
        "transition": "all 250ms ease",
    },
    "card": {
        "padding": "24px",
        "borderRadius": "12px",
        "backgroundColor": "var(--surface-color)",
        "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
    },
    "card_elevated": {
        "padding": "32px",
        "borderRadius": "16px",
        "backgroundColor": "var(--surface-color)",
        "boxShadow": "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
    },
    "card_flat": {
        "padding": "24px",
        "borderRadius": "12px",
        "backgroundColor": "var(--surface-color)",
        "border": "1px solid var(--border-color)",
    },
    "input": {
        "width": "100%",
        "padding": "12px 16px",
        "fontSize": "16px",
        "borderRadius": "8px",
        "border": "1px solid var(--border-color)",
        "backgroundColor": "var(--surface-color)",
        "color": "var(--text-color)",
        "transition": "border-color 250ms ease, box-shadow 250ms ease",
    },
    "badge": {
        "display": "inline-flex",
        "alignItems": "center",
        "padding": "4px 12px",
        "fontSize": "12px",
        "fontWeight": "500",
        "borderRadius": "9999px",
        "backgroundColor": "var(--primary-color)",
        "color": "#ffffff",
    },
    "avatar": {
        "width": "48px",
        "height": "48px",
        "borderRadius": "9999px",
        "objectFit": "cover",
    },
    "link": {
        "color": "var(--primary-color)",
        "textDecoration": "none",
        "transition": "color 250ms ease",
        "cursor": "pointer",
    },
    "divider": {
        "width": "100%",
        "height": "1px",
        "backgroundColor": "var(--border-color)",
        "border": "none",
    },
}


def get_base_style(name: str) -> dict:
    """Get a base style by name"""
    return BASE_STYLES.get(name, {})


def get_mobile_style(name: str) -> dict:
    """Get mobile overrides for a style"""
    return MOBILE_STYLES.get(name, {})


def get_component_styles(component: str) -> dict:
    """Get component styles"""
    return COMPONENT_STYLES.get(component, {})


def compose_styles(*style_names: str) -> dict:
    """Compose multiple base styles into one"""
    result = {}
    for name in style_names:
        result.update(get_base_style(name))
    return result


def get_responsive_styles(name: str) -> tuple[dict, dict]:
    """Get both base and mobile styles for a component"""
    return get_base_style(name), get_mobile_style(name)


# Section presets for AI generation
SECTION_PRESETS = {
    "hero_centered": {
        "element": "section",
        "baseStyles": {
            "minHeight": "90vh",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "padding": "80px 24px",
            "textAlign": "center",
        },
        "mobileStyles": {
            "minHeight": "80vh",
            "padding": "48px 16px",
        },
    },
    "hero_split": {
        "element": "section",
        "baseStyles": {
            "minHeight": "90vh",
            "display": "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap": "48px",
            "alignItems": "center",
            "padding": "80px 24px",
        },
        "mobileStyles": {
            "gridTemplateColumns": "1fr",
            "padding": "48px 16px",
            "minHeight": "auto",
        },
    },
    "features_grid": {
        "element": "section",
        "baseStyles": {
            "padding": "80px 24px",
        },
        "mobileStyles": {
            "padding": "48px 16px",
        },
        "innerGrid": {
            "display": "grid",
            "gridTemplateColumns": "repeat(3, 1fr)",
            "gap": "32px",
        },
        "innerGridMobile": {
            "gridTemplateColumns": "1fr",
        },
    },
    "testimonials": {
        "element": "section",
        "baseStyles": {
            "padding": "80px 24px",
            "backgroundColor": "var(--surface-color)",
        },
        "mobileStyles": {
            "padding": "48px 16px",
        },
    },
    "cta": {
        "element": "section",
        "baseStyles": {
            "padding": "80px 24px",
            "textAlign": "center",
            "backgroundColor": "var(--primary-color)",
            "color": "#ffffff",
        },
        "mobileStyles": {
            "padding": "48px 16px",
        },
    },
    "footer": {
        "element": "footer",
        "baseStyles": {
            "padding": "64px 24px 24px",
            "backgroundColor": "var(--surface-color)",
        },
        "mobileStyles": {
            "padding": "48px 16px 16px",
        },
    },
}


def get_section_preset(preset_name: str) -> dict:
    """Get a section preset configuration"""
    return SECTION_PRESETS.get(preset_name, {})


__all__ = [
    "BASE_STYLES",
    "MOBILE_STYLES",
    "COMPONENT_STYLES",
    "SECTION_PRESETS",
    "get_base_style",
    "get_mobile_style",
    "get_component_styles",
    "compose_styles",
    "get_responsive_styles",
    "get_section_preset",
]
