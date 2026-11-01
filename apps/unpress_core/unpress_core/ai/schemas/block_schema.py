"""
Frappe Builder Block Schema
The core schema for AI-generated blocks - simple and focused.
"""

from __future__ import annotations
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator
import uuid


# Supported HTML elements in Frappe Builder
ElementType = Literal[
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
    # Other
    "hr", "br", "figure", "figcaption",
]


class FrappeStyles(BaseModel):
    """
    CSS styles in camelCase format for Frappe Builder.
    All properties are optional to allow flexible styling.
    """
    # Display & Layout
    display: Optional[str] = None
    flexDirection: Optional[str] = None
    flexWrap: Optional[str] = None
    alignItems: Optional[str] = None
    justifyContent: Optional[str] = None
    gap: Optional[str] = None
    gridTemplateColumns: Optional[str] = None
    gridTemplateRows: Optional[str] = None
    position: Optional[str] = None
    top: Optional[str] = None
    right: Optional[str] = None
    bottom: Optional[str] = None
    left: Optional[str] = None
    zIndex: Optional[str] = None

    # Sizing
    width: Optional[str] = None
    minWidth: Optional[str] = None
    maxWidth: Optional[str] = None
    height: Optional[str] = None
    minHeight: Optional[str] = None
    maxHeight: Optional[str] = None

    # Spacing
    padding: Optional[str] = None
    paddingTop: Optional[str] = None
    paddingRight: Optional[str] = None
    paddingBottom: Optional[str] = None
    paddingLeft: Optional[str] = None
    margin: Optional[str] = None
    marginTop: Optional[str] = None
    marginRight: Optional[str] = None
    marginBottom: Optional[str] = None
    marginLeft: Optional[str] = None

    # Colors & Background
    color: Optional[str] = None
    backgroundColor: Optional[str] = None
    backgroundImage: Optional[str] = None
    backgroundSize: Optional[str] = None
    backgroundPosition: Optional[str] = None
    backgroundRepeat: Optional[str] = None
    background: Optional[str] = None
    opacity: Optional[str] = None

    # Typography
    fontSize: Optional[str] = None
    fontWeight: Optional[str] = None
    fontFamily: Optional[str] = None
    fontStyle: Optional[str] = None
    lineHeight: Optional[str] = None
    letterSpacing: Optional[str] = None
    textAlign: Optional[str] = None
    textDecoration: Optional[str] = None
    textTransform: Optional[str] = None

    # Borders
    border: Optional[str] = None
    borderTop: Optional[str] = None
    borderRight: Optional[str] = None
    borderBottom: Optional[str] = None
    borderLeft: Optional[str] = None
    borderRadius: Optional[str] = None
    borderColor: Optional[str] = None
    borderWidth: Optional[str] = None
    borderStyle: Optional[str] = None

    # Effects
    boxShadow: Optional[str] = None
    textShadow: Optional[str] = None
    transform: Optional[str] = None
    transition: Optional[str] = None
    overflow: Optional[str] = None
    overflowX: Optional[str] = None
    overflowY: Optional[str] = None

    # Flex item properties
    flex: Optional[str] = None
    flexGrow: Optional[str] = None
    flexShrink: Optional[str] = None
    flexBasis: Optional[str] = None
    alignSelf: Optional[str] = None
    order: Optional[str] = None

    # Cursor & Interaction
    cursor: Optional[str] = None
    pointerEvents: Optional[str] = None
    userSelect: Optional[str] = None

    # Other
    objectFit: Optional[str] = None
    objectPosition: Optional[str] = None
    aspectRatio: Optional[str] = None
    filter: Optional[str] = None
    backdropFilter: Optional[str] = None
    clipPath: Optional[str] = None
    listStyle: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional CSS properties

    def to_dict(self) -> dict:
        """Convert to dict, excluding None values"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class FrappeBlock(BaseModel):
    """
    Frappe Builder Block schema.
    This is the core structure that the AI generates.
    """
    blockId: str = Field(
        default_factory=lambda: f"block-{uuid.uuid4().hex[:8]}",
        description="Unique identifier for the block"
    )
    element: str = Field(
        default="div",
        description="HTML element type"
    )
    innerHTML: Optional[str] = Field(
        default=None,
        description="Text content of the block"
    )
    baseStyles: Optional[dict] = Field(
        default=None,
        description="Desktop styles in camelCase CSS"
    )
    mobileStyles: Optional[dict] = Field(
        default=None,
        description="Mobile styles (<576px)"
    )
    tabletStyles: Optional[dict] = Field(
        default=None,
        description="Tablet styles (576px-1024px)"
    )
    rawStyles: Optional[dict] = Field(
        default=None,
        description="Raw CSS variables"
    )
    attributes: Optional[dict[str, Any]] = Field(
        default=None,
        description="HTML attributes (href, src, alt, etc.)"
    )
    classes: Optional[list[str]] = Field(
        default=None,
        description="CSS classes to apply"
    )
    children: Optional[list["FrappeBlock"]] = Field(
        default=None,
        description="Nested child blocks"
    )
    visibilityCondition: Optional[str] = Field(
        default=None,
        description="Jinja2 condition for conditional rendering"
    )

    @field_validator("blockId", mode="before")
    @classmethod
    def ensure_block_id(cls, v):
        """Ensure blockId is always set"""
        if not v:
            return f"block-{uuid.uuid4().hex[:8]}"
        return v

    def to_dict(self) -> dict:
        """Convert to Frappe Builder compatible dict"""
        result = {
            "blockId": self.blockId,
            "element": self.element,
        }

        if self.innerHTML:
            result["innerHTML"] = self.innerHTML
        if self.baseStyles:
            result["baseStyles"] = self.baseStyles
        if self.mobileStyles:
            result["mobileStyles"] = self.mobileStyles
        if self.tabletStyles:
            result["tabletStyles"] = self.tabletStyles
        if self.rawStyles:
            result["rawStyles"] = self.rawStyles
        if self.attributes:
            result["attributes"] = self.attributes
        if self.classes:
            result["classes"] = self.classes
        if self.children:
            result["children"] = [
                child.to_dict() if isinstance(child, FrappeBlock) else child
                for child in self.children
            ]
        if self.visibilityCondition:
            result["visibilityCondition"] = self.visibilityCondition

        return result

    class Config:
        extra = "ignore"


# Rebuild model to resolve forward references
FrappeBlock.model_rebuild()


__all__ = [
    "ElementType",
    "FrappeStyles",
    "FrappeBlock",
]
