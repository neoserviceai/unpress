"""
AI Module Utilities
Shared utilities and constants for the AI generation module.
"""

import re
import uuid
from typing import Any


# =============================================================================
# CSS PROPERTY MAPPINGS
# =============================================================================

# Kebab-case to camelCase CSS property mappings
KEBAB_TO_CAMEL = {
    # Flexbox
    "flex-direction": "flexDirection",
    "flex-wrap": "flexWrap",
    "align-items": "alignItems",
    "justify-content": "justifyContent",
    "align-content": "alignContent",
    "align-self": "alignSelf",
    "flex-grow": "flexGrow",
    "flex-shrink": "flexShrink",
    "flex-basis": "flexBasis",
    # Grid
    "grid-template-columns": "gridTemplateColumns",
    "grid-template-rows": "gridTemplateRows",
    "grid-column": "gridColumn",
    "grid-row": "gridRow",
    "column-gap": "columnGap",
    "row-gap": "rowGap",
    # Sizing
    "min-width": "minWidth",
    "max-width": "maxWidth",
    "min-height": "minHeight",
    "max-height": "maxHeight",
    # Spacing
    "padding-top": "paddingTop",
    "padding-right": "paddingRight",
    "padding-bottom": "paddingBottom",
    "padding-left": "paddingLeft",
    "margin-top": "marginTop",
    "margin-right": "marginRight",
    "margin-bottom": "marginBottom",
    "margin-left": "marginLeft",
    # Background
    "background-color": "backgroundColor",
    "background-image": "backgroundImage",
    "background-size": "backgroundSize",
    "background-position": "backgroundPosition",
    "background-repeat": "backgroundRepeat",
    # Typography
    "font-size": "fontSize",
    "font-weight": "fontWeight",
    "font-family": "fontFamily",
    "font-style": "fontStyle",
    "line-height": "lineHeight",
    "letter-spacing": "letterSpacing",
    "text-align": "textAlign",
    "text-decoration": "textDecoration",
    "text-transform": "textTransform",
    "white-space": "whiteSpace",
    "word-break": "wordBreak",
    # Borders
    "border-radius": "borderRadius",
    "border-color": "borderColor",
    "border-width": "borderWidth",
    "border-style": "borderStyle",
    "border-top": "borderTop",
    "border-right": "borderRight",
    "border-bottom": "borderBottom",
    "border-left": "borderLeft",
    # Effects
    "box-shadow": "boxShadow",
    "text-shadow": "textShadow",
    "backdrop-filter": "backdropFilter",
    # Other
    "z-index": "zIndex",
    "object-fit": "objectFit",
    "object-position": "objectPosition",
    "pointer-events": "pointerEvents",
    "user-select": "userSelect",
    "aspect-ratio": "aspectRatio",
    "overflow-x": "overflowX",
    "overflow-y": "overflowY",
}

# Valid HTML elements for Frappe Builder
VALID_ELEMENTS = {
    # Structural
    "div", "section", "article", "aside", "main", "header", "footer", "nav",
    # Text
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "label", "blockquote",
    # Links & Buttons
    "a", "button",
    # Media
    "img", "video", "iframe",
    # Lists
    "ul", "ol", "li",
    # Forms
    "form", "input", "textarea", "select", "option",
    # Table
    "table", "thead", "tbody", "tr", "td", "th",
    # Other
    "hr", "br", "figure", "figcaption",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def kebab_to_camel(kebab_str: str) -> str:
    """
    Convert kebab-case to camelCase.

    Args:
        kebab_str: String in kebab-case format

    Returns:
        String in camelCase format
    """
    # First check the mapping
    if kebab_str in KEBAB_TO_CAMEL:
        return KEBAB_TO_CAMEL[kebab_str]

    # Otherwise convert manually
    components = kebab_str.split("-")
    return components[0] + "".join(x.title() for x in components[1:])


def generate_block_id(prefix: str = "block") -> str:
    """
    Generate a unique block ID.

    Args:
        prefix: Prefix for the block ID

    Returns:
        Unique block ID string
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def ensure_unique_ids(block: dict, seen_ids: set = None) -> dict:
    """
    Ensure all block IDs in a tree are unique.

    Args:
        block: Block dictionary
        seen_ids: Set of already seen IDs

    Returns:
        Block with unique IDs
    """
    if seen_ids is None:
        seen_ids = set()

    import copy
    result = copy.deepcopy(block)

    block_id = result.get("blockId")
    if not block_id or block_id in seen_ids:
        element = result.get("element", "block")
        result["blockId"] = generate_block_id(element)

    seen_ids.add(result["blockId"])

    if "children" in result and isinstance(result["children"], list):
        result["children"] = [
            ensure_unique_ids(child, seen_ids)
            for child in result["children"]
        ]

    return result


def convert_styles_to_camel(styles: dict) -> dict:
    """
    Convert all kebab-case properties in a styles dict to camelCase.

    Args:
        styles: Dictionary of CSS styles

    Returns:
        Dictionary with camelCase property names
    """
    if not isinstance(styles, dict):
        return {}

    result = {}
    for key, value in styles.items():
        if "-" in key:
            key = kebab_to_camel(key)
        if value is not None:
            result[key] = str(value) if not isinstance(value, str) else value

    return result


def validate_element(element: str) -> bool:
    """
    Check if an element is valid for Frappe Builder.

    Args:
        element: HTML element name

    Returns:
        True if valid, False otherwise
    """
    return element in VALID_ELEMENTS


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Dictionary to merge on top

    Returns:
        Merged dictionary
    """
    import copy
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


__all__ = [
    "KEBAB_TO_CAMEL",
    "VALID_ELEMENTS",
    "kebab_to_camel",
    "generate_block_id",
    "ensure_unique_ids",
    "convert_styles_to_camel",
    "validate_element",
    "deep_merge",
]
