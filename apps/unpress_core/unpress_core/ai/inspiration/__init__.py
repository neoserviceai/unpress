"""
Inspiration Module for Builder AI

This module allows users to capture and analyze websites or upload images
for design inspiration. The captured content is analyzed to extract:
- Dominant colors
- Layout patterns
- Design elements

This information is then used to enhance the AI design brief.
"""

from unpress_core.ai.inspiration.screenshotter import WebsiteScreenshotter
from unpress_core.ai.inspiration.analyzer import DesignAnalyzer
from unpress_core.ai.inspiration.brief_enhancer import enhance_brief_with_inspirations

__all__ = [
    "WebsiteScreenshotter",
    "DesignAnalyzer",
    "enhance_brief_with_inspirations",
]
