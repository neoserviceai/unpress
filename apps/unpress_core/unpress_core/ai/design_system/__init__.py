# Design System Module
# Design tokens, styles, and themes for consistent UI generation

from unpress_core.ai.design_system.tokens import DESIGN_TOKENS, get_token
from unpress_core.ai.design_system.styles import BASE_STYLES, get_component_styles
from unpress_core.ai.design_system.themes import (
    THEMES,
    get_theme,
    list_themes,
    get_theme_prompt,
    get_theme_characteristics,
    get_theme_anti_patterns,
    apply_theme_to_block,
    get_theme_styles_for_section,
)

__all__ = [
    # Tokens
    "DESIGN_TOKENS",
    "get_token",
    # Styles
    "BASE_STYLES",
    "get_component_styles",
    # Themes
    "THEMES",
    "get_theme",
    "list_themes",
    "get_theme_prompt",
    "get_theme_characteristics",
    "get_theme_anti_patterns",
    "apply_theme_to_block",
    "get_theme_styles_for_section",
]
