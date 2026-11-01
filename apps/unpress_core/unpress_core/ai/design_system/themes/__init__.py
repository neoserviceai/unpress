"""
Design Themes
Creative visual themes for AI-generated pages.
Each theme provides colors, styles, and creative guidance.
"""

from unpress_core.ai.design_system.themes.modern import MODERN_THEME
from unpress_core.ai.design_system.themes.neobrutalist import NEOBRUTALIST_THEME
from unpress_core.ai.design_system.themes.glassmorphism import GLASSMORPHISM_THEME
from unpress_core.ai.design_system.themes.minimal import MINIMAL_THEME
from unpress_core.ai.design_system.themes.corporate import CORPORATE_THEME
from unpress_core.ai.design_system.themes.creative import CREATIVE_THEME


THEMES = {
    "modern": MODERN_THEME,
    "neobrutalist": NEOBRUTALIST_THEME,
    "glassmorphism": GLASSMORPHISM_THEME,
    "minimal": MINIMAL_THEME,
    "corporate": CORPORATE_THEME,
    "creative": CREATIVE_THEME,
}


def get_theme(theme_name: str) -> dict:
    """
    Get theme configuration by name.

    Args:
        theme_name: Name of the theme

    Returns:
        Theme configuration dict with colors, styles, characteristics
    """
    return THEMES.get(theme_name, MODERN_THEME)


def list_themes() -> list[str]:
    """Get list of available theme names"""
    return list(THEMES.keys())


def get_theme_prompt(theme_name: str) -> str:
    """
    Get the creative guidance prompt for a theme.

    Args:
        theme_name: Name of the theme

    Returns:
        str: Creative guidance prompt for the theme
    """
    theme = get_theme(theme_name)
    return theme.get("prompt", "")


def get_theme_characteristics(theme_name: str) -> list[str]:
    """Get the visual characteristics of a theme"""
    theme = get_theme(theme_name)
    return theme.get("characteristics", [])


def get_theme_anti_patterns(theme_name: str) -> list[str]:
    """Get the anti-patterns to avoid for a theme"""
    theme = get_theme(theme_name)
    return theme.get("anti_patterns", [])


def apply_theme_to_block(block: dict, theme_name: str, deep: bool = True) -> dict:
    """
    Apply theme CSS variables to a block.

    This function injects theme colors as CSS variables in the block's styles,
    allowing the block to adapt to different themes.

    Args:
        block: Block dictionary to enhance
        theme_name: Name of the theme to apply
        deep: If True, apply to all children recursively

    Returns:
        dict: Block with theme variables applied
    """
    import copy

    theme = get_theme(theme_name)
    colors = theme.get("colors", {})

    # Build CSS variable overrides
    css_vars = {
        "--primary-color": colors.get("primary", "#2563eb"),
        "--secondary-color": colors.get("secondary", "#64748b"),
        "--surface-color": colors.get("surface", "#ffffff"),
        "--text-color": colors.get("text", "#1f2937"),
        "--muted-color": colors.get("muted", "#6b7280"),
        "--border-color": colors.get("border", "#e5e7eb"),
        "--accent-color": colors.get("accent", "#f59e0b"),
    }

    # RGB versions for rgba() usage
    primary = colors.get("primary", "#2563eb")
    if primary.startswith("#"):
        r = int(primary[1:3], 16)
        g = int(primary[3:5], 16)
        b = int(primary[5:7], 16)
        css_vars["--primary-rgb"] = f"{r}, {g}, {b}"

    result = copy.deepcopy(block)

    # Apply to root block (typically the page container)
    if "baseStyles" not in result:
        result["baseStyles"] = {}

    # Only apply CSS vars to root/section level blocks
    is_section = result.get("element") in ("section", "header", "footer", "main")
    if is_section or result.get("blockId", "").endswith("-section"):
        for var_name, var_value in css_vars.items():
            # Store in rawStyles for CSS variable injection
            if "rawStyles" not in result:
                result["rawStyles"] = {}
            result["rawStyles"][var_name] = var_value

    # Recursively apply to children if requested
    if deep and "children" in result and isinstance(result["children"], list):
        result["children"] = [
            apply_theme_to_block(child, theme_name, deep=True)
            for child in result["children"]
        ]

    return result


def get_theme_styles_for_section(theme_name: str, section_type: str) -> dict:
    """
    Get theme-specific styles for a section type.

    Args:
        theme_name: Theme name
        section_type: Type of section (hero, features, etc.)

    Returns:
        dict: Section-specific style overrides for the theme
    """
    theme = get_theme(theme_name)
    styles = theme.get("styles", {})
    return styles.get(section_type, {})


__all__ = [
    "THEMES",
    "get_theme",
    "list_themes",
    "get_theme_prompt",
    "get_theme_characteristics",
    "get_theme_anti_patterns",
    "apply_theme_to_block",
    "get_theme_styles_for_section",
    "MODERN_THEME",
    "NEOBRUTALIST_THEME",
    "GLASSMORPHISM_THEME",
    "MINIMAL_THEME",
    "CORPORATE_THEME",
    "CREATIVE_THEME",
]
