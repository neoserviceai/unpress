"""
Brief Enhancer for Inspiration Module

Integrates inspiration data into the AI design brief.
"""

from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
    from unpress_core.ai.schemas.design_brief import DesignBrief


def enhance_brief_with_inspirations(
    base_brief: "DesignBrief",
    inspirations: list[dict],
) -> "DesignBrief":
    """
    Enhance a design brief with insights from inspiration sources.

    Args:
        base_brief: The base DesignBrief to enhance
        inspirations: List of inspiration dicts with:
            - sentiment: "like" | "dislike" | "neutral"
            - analysis: dict with dominant_colors, brightness, etc.
            - url: source URL (optional)
            - description: user notes (optional)

    Returns:
        Enhanced DesignBrief
    """
    liked_colors = []
    disliked_colors = []
    liked_descriptions = []
    disliked_descriptions = []
    is_dark_preference = None

    for insp in inspirations:
        sentiment = insp.get("sentiment", "neutral")
        analysis = insp.get("analysis", {})

        # Extract colors
        colors = analysis.get("dominant_colors", [])
        color_hexes = [c.get("hex") for c in colors if c.get("hex")]

        if sentiment == "like":
            liked_colors.extend(color_hexes[:3])  # Top 3 colors
            if insp.get("description"):
                liked_descriptions.append(insp["description"])
            # Track dark/light preference
            if analysis.get("is_dark_theme") is not None:
                is_dark_preference = analysis["is_dark_theme"]

        elif sentiment == "dislike":
            disliked_colors.extend(color_hexes[:3])
            if insp.get("description"):
                disliked_descriptions.append(insp["description"])

    # Build inspiration context for the brief
    inspiration_parts = []

    if liked_colors:
        # Deduplicate and limit
        unique_liked = list(dict.fromkeys(liked_colors))[:5]
        inspiration_parts.append(
            f"Colors from liked inspirations: {', '.join(unique_liked)}"
        )

    if disliked_colors:
        unique_disliked = list(dict.fromkeys(disliked_colors))[:5]
        inspiration_parts.append(
            f"Colors to AVOID (from disliked inspirations): {', '.join(unique_disliked)}"
        )

    if liked_descriptions:
        inspiration_parts.append(
            f"Liked design characteristics: {'; '.join(liked_descriptions[:3])}"
        )

    if disliked_descriptions:
        inspiration_parts.append(
            f"Avoid these characteristics: {'; '.join(disliked_descriptions[:3])}"
        )

    if is_dark_preference is not None:
        theme_pref = "dark" if is_dark_preference else "light"
        inspiration_parts.append(
            f"User prefers {theme_pref} color schemes based on liked inspirations"
        )

    # Update brief with inspiration context
    if inspiration_parts:
        inspiration_context = "\n".join(inspiration_parts)

        # Add to existing brief context or create new
        if hasattr(base_brief, "inspiration_context"):
            base_brief.inspiration_context = inspiration_context
        else:
            # If brief doesn't have this field, we'll need to work around it
            # by appending to an existing field or storing separately
            pass

    return base_brief


def get_inspirations_for_site(site_name: str = None) -> list[dict]:
    """
    Get all inspirations for a site (or all recent inspirations).

    Args:
        site_name: Optional Builder Site name to filter by

    Returns:
        List of inspiration dicts with analysis data
    """
    filters = {"status": "captured"}
    if site_name:
        filters["parent_site"] = site_name

    inspirations = frappe.get_all(
        "Builder Site Inspiration",
        filters=filters,
        fields=["name", "url", "sentiment", "description", "analysis", "screenshot", "image"],
        order_by="creation desc",
        limit=20,
    )

    result = []
    for insp in inspirations:
        # Parse JSON analysis
        analysis = {}
        if insp.get("analysis"):
            try:
                import json
                analysis = json.loads(insp["analysis"])
            except (json.JSONDecodeError, TypeError):
                pass

        result.append({
            "name": insp.name,
            "url": insp.get("url"),
            "sentiment": insp.get("sentiment", "neutral"),
            "description": insp.get("description"),
            "analysis": analysis,
            "screenshot": insp.get("screenshot"),
            "image": insp.get("image"),
        })

    return result


def analyze_and_enhance_brief(
    base_brief: "DesignBrief",
    site_name: str = None,
) -> "DesignBrief":
    """
    Convenience function to get inspirations and enhance brief.

    Args:
        base_brief: Base DesignBrief to enhance
        site_name: Optional site name to filter inspirations

    Returns:
        Enhanced DesignBrief
    """
    inspirations = get_inspirations_for_site(site_name)
    if inspirations:
        return enhance_brief_with_inspirations(base_brief, inspirations)
    return base_brief
