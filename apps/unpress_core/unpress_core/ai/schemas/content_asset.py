"""
Schemas for client content understanding.

The generation pipeline accepts arbitrary client material (photos, documents)
dropped in the chat. A vision/LLM pass classifies each item into these
structured shapes so the generator can place real photos in the right slots
and use real copy in the right sections — instead of placeholders.
"""

from typing import Literal

from pydantic import BaseModel, Field


# Page sections a piece of content can belong to. Free-form `suggested_section`
# is kept as a plain string in the DocType, but the model is nudged toward
# this vocabulary for consistency with the page generator.
SECTION_VOCAB = (
    "home", "about", "services", "service-detail", "gallery",
    "team", "testimonials", "contact", "pricing", "faq", "generic"
)


class ImageUnderstanding(BaseModel):
    """Vision categorization of a single client photo."""

    description: str = Field(
        default="",
        description=(
            "Concrete description of what the photo actually shows (subject, "
            "setting, what's happening). This doubles as the image alt text / "
            "generation prompt context, so be specific and factual."
        ),
    )
    suggested_section: str = Field(
        default="generic",
        description=(
            "Which page section this photo best serves: one of home, about, "
            "services, service-detail, gallery, team, testimonials, contact, "
            "pricing, faq, generic."
        ),
    )
    suggested_slots: list[str] = Field(
        default_factory=list,
        description=(
            "Image slots this photo suits, ordered best-first: any of "
            "hero, background, gallery, service, team, logo, detail. A wide "
            "establishing shot suits hero/background; a portrait suits team; "
            "a tight subject shot suits service/gallery."
        ),
    )
    orientation: Literal["landscape", "portrait", "square"] = Field(
        default="landscape",
        description="Dominant orientation of the image.",
    )
    quality: Literal["high", "medium", "low"] = Field(
        default="medium",
        description=(
            "Usability for a professional website: high = sharp, well-lit, "
            "well-composed; low = blurry, dark, tiny, watermarked or a "
            "screenshot. Low-quality images should be avoided for hero slots."
        ),
    )
    contains_text: bool = Field(
        default=False,
        description="True if the image is mostly text/screenshot/scan (not a photo).",
    )
    is_logo: bool = Field(
        default=False,
        description="True if this looks like a brand logo rather than content.",
    )
    dominant_colors: list[str] = Field(
        default_factory=list,
        description="Up to 3 dominant colors as #rrggbb hex, most prominent first.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-8 short keywords describing the subject (for matching).",
    )

    class Config:
        extra = "ignore"


class DocumentUnderstanding(BaseModel):
    """LLM classification of a client document's extracted text."""

    summary: str = Field(
        default="",
        description="1-2 sentence summary of what this document contains.",
    )
    suggested_section: str = Field(
        default="generic",
        description=(
            "Which page section this content feeds: one of home, about, "
            "services, service-detail, gallery, team, testimonials, contact, "
            "pricing, faq, generic."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-8 short keywords (topics, service names, entities).",
    )

    class Config:
        extra = "ignore"


__all__ = ["ImageUnderstanding", "DocumentUnderstanding", "SECTION_VOCAB"]
