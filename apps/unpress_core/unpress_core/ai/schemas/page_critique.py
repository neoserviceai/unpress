"""
Schema for the visual verification loop.

A vision model looks at a SCREENSHOT of a generated page and reports concrete,
visible problems so the generator can fix them — the "the LLM sees what it made"
loop. Kept deliberately small so smaller vision models can fill it reliably.
"""

from typing import Literal

from pydantic import BaseModel, Field


class PageIssue(BaseModel):
    """One concrete, visible problem on the rendered page."""

    area: str = Field(
        default="",
        description="Where on the page: hero, header, gallery, a section, footer, CTA…",
    )
    severity: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="high = looks broken/unprofessional or wrong content; low = polish.",
    )
    problem: str = Field(
        default="",
        description="What is visibly wrong, specific to what is seen in the screenshot.",
    )
    fix: str = Field(
        default="",
        description="One concrete corrective action.",
    )

    class Config:
        extra = "ignore"


class PageCritique(BaseModel):
    """A first-glance design review of a rendered page screenshot."""

    overall: str = Field(
        default="",
        description="One-sentence overall impression of the page as seen.",
    )
    looks_professional: bool = Field(
        default=True,
        description="Would this pass as a professional site at first glance?",
    )
    issues: list[PageIssue] = Field(
        default_factory=list,
        description="Concrete visible problems, most important first. Empty if it looks good.",
    )

    class Config:
        extra = "ignore"


__all__ = ["PageCritique", "PageIssue"]
