"""
Design Analyzer for Inspiration Module

Analyzes images (screenshots or uploaded) to extract:
- Dominant colors
- Color palette suggestions
- Basic layout patterns
"""

import io
from typing import Optional

import frappe


class DesignAnalyzer:
    """
    Analyzes design images to extract colors and patterns.

    Uses PIL for image processing and sklearn for color clustering.
    """

    def __init__(self):
        """Initialize the analyzer."""
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if required dependencies are available."""
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            raise ImportError(
                "PIL and numpy are required for design analysis. "
                "Install with: pip install pillow numpy"
            )

    def extract_dominant_colors(
        self,
        image_source: bytes | str,
        n_colors: int = 5,
        resize_to: int = 150,
    ) -> list[dict]:
        """
        Extract dominant colors from an image.

        Args:
            image_source: Image bytes or file path
            n_colors: Number of colors to extract
            resize_to: Resize image to this size for speed

        Returns:
            List of color dicts with hex, rgb, and percentage
        """
        from PIL import Image
        import numpy as np

        # Load image
        if isinstance(image_source, bytes):
            img = Image.open(io.BytesIO(image_source))
        else:
            img = Image.open(image_source)

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize for speed
        img = img.resize((resize_to, resize_to))

        # Convert to numpy array
        pixels = np.array(img).reshape(-1, 3)

        # Try to use sklearn for better clustering
        try:
            from sklearn.cluster import KMeans

            kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
            kmeans.fit(pixels)

            # Get colors and their frequencies
            colors = kmeans.cluster_centers_.astype(int)
            labels = kmeans.labels_
            counts = np.bincount(labels)
            percentages = counts / len(labels) * 100

            # Sort by frequency
            sorted_indices = np.argsort(percentages)[::-1]

            result = []
            for idx in sorted_indices:
                r, g, b = colors[idx]
                result.append({
                    "hex": f"#{int(r):02x}{int(g):02x}{int(b):02x}",
                    "rgb": [int(r), int(g), int(b)],
                    "percentage": float(round(percentages[idx], 1)),
                })

            return result

        except ImportError:
            # Fallback: simple histogram-based extraction
            return self._extract_colors_simple(pixels, n_colors)

    def _extract_colors_simple(self, pixels, n_colors: int) -> list[dict]:
        """
        Simple color extraction without sklearn.

        Uses histogram binning for color quantization.
        """
        import numpy as np
        from collections import Counter

        # Quantize colors to reduce variety
        quantized = (pixels // 32) * 32

        # Count color occurrences
        color_tuples = [tuple(c) for c in quantized]
        counter = Counter(color_tuples)

        total = len(color_tuples)
        result = []

        for color, count in counter.most_common(n_colors):
            r, g, b = color
            result.append({
                "hex": f"#{r:02x}{g:02x}{b:02x}",
                "rgb": [int(r), int(g), int(b)],
                "percentage": round(count / total * 100, 1),
            })

        return result

    def analyze_image(
        self,
        image_source: bytes | str,
        extract_colors: bool = True,
        n_colors: int = 5,
    ) -> dict:
        """
        Perform full analysis on an image.

        Args:
            image_source: Image bytes or file path
            extract_colors: Whether to extract dominant colors
            n_colors: Number of colors to extract

        Returns:
            Analysis result dict
        """
        from PIL import Image

        # Load image
        if isinstance(image_source, bytes):
            img = Image.open(io.BytesIO(image_source))
        else:
            img = Image.open(image_source)

        result = {
            "width": img.width,
            "height": img.height,
            "aspect_ratio": round(img.width / img.height, 2),
            "format": img.format,
        }

        if extract_colors:
            result["dominant_colors"] = self.extract_dominant_colors(
                image_source, n_colors=n_colors
            )

        # Determine if image is light or dark
        if result.get("dominant_colors"):
            avg_brightness = self._calculate_brightness(result["dominant_colors"])
            result["is_dark_theme"] = bool(avg_brightness < 128)
            result["brightness"] = int(round(avg_brightness))

        return result

    def _calculate_brightness(self, colors: list[dict]) -> float:
        """
        Calculate weighted average brightness from colors.

        Args:
            colors: List of color dicts with rgb and percentage

        Returns:
            Average brightness (0-255)
        """
        total_brightness = 0
        total_weight = 0

        for color in colors:
            r, g, b = color["rgb"]
            # Perceived brightness formula
            brightness = (r * 0.299 + g * 0.587 + b * 0.114)
            weight = color["percentage"]
            total_brightness += brightness * weight
            total_weight += weight

        return total_brightness / total_weight if total_weight > 0 else 128

    def analyze_from_file_url(self, file_url: str) -> dict:
        """
        Analyze an image from a Frappe file URL.

        Args:
            file_url: Frappe file URL (e.g., /files/image.png)

        Returns:
            Analysis result dict
        """
        # Get file path
        if file_url.startswith("/files/"):
            file_path = frappe.get_site_path("public", file_url.lstrip("/"))
        elif file_url.startswith("/private/"):
            file_path = frappe.get_site_path(file_url.lstrip("/"))
        else:
            raise ValueError(f"Invalid file URL: {file_url}")

        return self.analyze_image(file_path)


def analyze_inspiration_image(image_source: bytes | str, n_colors: int = 5) -> dict:
    """
    Convenience function to analyze an inspiration image.

    Args:
        image_source: Image bytes or file path
        n_colors: Number of colors to extract

    Returns:
        Analysis result dict
    """
    analyzer = DesignAnalyzer()
    return analyzer.analyze_image(image_source, n_colors=n_colors)
