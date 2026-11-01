# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import Optional

import frappe
from frappe.model.document import Document


class BuilderSiteInspiration(Document):
    """
    Builder Site Inspiration DocType

    Allows users to capture websites or upload images for design inspiration.
    Automatically analyzes images to extract dominant colors and patterns.
    """

    def before_save(self):
        """Trigger capture/analysis before save if needed."""
        # For uploaded images, analyze immediately
        if self.source_type == "Image" and self.image:
            if self.status == "pending" or not self.analysis:
                self.analyze_image()

    def after_insert(self):
        """Queue capture for URL sources after insert."""
        if self.source_type == "URL" and self.url and self.status == "pending":
            # Queue the capture as a background job
            frappe.enqueue(
                "unpress_core.unpress_core.doctype.builder_site_inspiration.builder_site_inspiration.capture_and_analyze",
                doc_name=self.name,
                queue="default",
                timeout=120,
            )
            frappe.db.set_value(
                self.doctype, self.name, "status", "capturing", update_modified=False
            )
            frappe.db.commit()

    def analyze_image(self):
        """Analyze the uploaded image to extract colors."""
        try:
            from unpress_core.ai.inspiration.analyzer import DesignAnalyzer

            analyzer = DesignAnalyzer()

            # Get the image source
            if self.source_type == "Image" and self.image:
                image_path = self.image
            elif self.screenshot:
                image_path = self.screenshot
            else:
                return

            # Analyze
            result = analyzer.analyze_from_file_url(image_path)

            # Store analysis
            self.analysis = json.dumps(result, indent=2)
            self.status = "captured"
            self.captured_at = frappe.utils.now()

        except Exception as e:
            frappe.log_error("Inspiration analysis failed", str(e))
            self.status = "failed"
            self.error_message = str(e)[:500]

    def capture_website(self):
        """Capture screenshot of the website URL."""
        if not self.url or self.source_type != "URL":
            return

        try:
            from unpress_core.ai.inspiration.screenshotter import WebsiteScreenshotter

            screenshotter = WebsiteScreenshotter()
            result = screenshotter.capture_and_save(self.url)

            if result.get("success"):
                self.screenshot = result["file_url"]
                self.status = "captured"
                self.captured_at = frappe.utils.now()

                # Now analyze the screenshot
                self.analyze_image()
            else:
                self.status = "failed"
                self.error_message = result.get("error", "Unknown error")

        except ImportError:
            # Playwright not available — use lightweight HTML-based extraction
            self._capture_website_lightweight()

        except Exception as e:
            frappe.log_error("Website capture failed", str(e))
            self.status = "failed"
            self.error_message = str(e)[:500]

    def _capture_website_lightweight(self):
        """Fallback: extract page metadata and colors via HTTP without Playwright."""
        import re
        import requests
        from collections import Counter
        from urllib.parse import urljoin

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(self.url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            html = resp.text

            analysis = {"source": "html_metadata", "url": self.url}

            # Extract title
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if title_match:
                analysis["title"] = title_match.group(1).strip()[:200]

            # Extract meta description
            desc_match = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE
            )
            if not desc_match:
                desc_match = re.search(
                    r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE
                )
            if desc_match:
                analysis["description"] = desc_match.group(1).strip()[:500]

            # Extract theme-color meta tag
            theme_match = re.search(
                r'<meta[^>]*name=["\']theme-color["\'][^>]*content=["\'](#[0-9a-fA-F]{3,8})["\']',
                html, re.IGNORECASE
            )
            if not theme_match:
                theme_match = re.search(
                    r'<meta[^>]*content=["\'](#[0-9a-fA-F]{3,8})["\'][^>]*name=["\']theme-color["\']',
                    html, re.IGNORECASE
                )

            # Extract og:image
            og_match = re.search(
                r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE
            )
            if not og_match:
                og_match = re.search(
                    r'<meta[^>]*content=["\'](.*?)["\'][^>]*property=["\']og:image["\']', html, re.IGNORECASE
                )

            # Extract hex colors from CSS/styles
            hex_colors = re.findall(r'#([0-9a-fA-F]{6})\b', html)
            color_counts = Counter(hex_colors)
            total = sum(color_counts.values()) or 1

            dominant_colors = []
            for hex_val, count in color_counts.most_common(15):
                r, g, b = int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)
                # Skip near-black and near-white
                brightness = r * 0.299 + g * 0.587 + b * 0.114
                if 15 < brightness < 240:
                    dominant_colors.append({
                        "hex": f"#{hex_val.lower()}",
                        "rgb": [r, g, b],
                        "percentage": round(count / total * 100, 1),
                        "source": "css"
                    })
                if len(dominant_colors) >= 5:
                    break

            # Insert theme-color at top if found
            if theme_match:
                theme_hex = theme_match.group(1)
                if len(theme_hex) == 4:  # Expand #RGB to #RRGGBB
                    theme_hex = f"#{theme_hex[1]*2}{theme_hex[2]*2}{theme_hex[3]*2}"
                analysis["theme_color"] = theme_hex
                r, g, b = int(theme_hex[1:3], 16), int(theme_hex[3:5], 16), int(theme_hex[5:7], 16)
                dominant_colors.insert(0, {
                    "hex": theme_hex.lower(),
                    "rgb": [r, g, b],
                    "percentage": 100.0,
                    "source": "theme-color"
                })

            # Try to download og:image and analyze for better colors
            if og_match:
                og_url = og_match.group(1)
                if not og_url.startswith("http"):
                    og_url = urljoin(self.url, og_url)
                analysis["og_image"] = og_url
                try:
                    og_colors = self._analyze_remote_image(og_url)
                    if og_colors:
                        dominant_colors = og_colors
                        analysis["color_source"] = "og_image"
                except Exception:
                    pass

            analysis["dominant_colors"] = dominant_colors[:5]

            # Determine dark/light theme
            if dominant_colors:
                total_weight = sum(c["percentage"] for c in dominant_colors)
                if total_weight > 0:
                    avg_brightness = sum(
                        (c["rgb"][0] * 0.299 + c["rgb"][1] * 0.587 + c["rgb"][2] * 0.114) * c["percentage"]
                        for c in dominant_colors
                    ) / total_weight
                    analysis["is_dark_theme"] = bool(avg_brightness < 128)
                    analysis["brightness"] = int(round(avg_brightness))

            self.analysis = json.dumps(analysis, indent=2)
            self.status = "captured"
            self.captured_at = frappe.utils.now()

        except Exception as e:
            frappe.log_error("Lightweight capture failed", str(e))
            self.status = "failed"
            self.error_message = f"HTML capture: {str(e)[:450]}"

    def _analyze_remote_image(self, image_url: str) -> Optional[list]:
        """Download a remote image and extract dominant colors."""
        import requests

        resp = requests.get(image_url, timeout=10, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return None

        content = resp.content
        if len(content) > 5 * 1024 * 1024:
            return None

        from unpress_core.ai.inspiration.analyzer import DesignAnalyzer
        analyzer = DesignAnalyzer()
        return analyzer.extract_dominant_colors(content, n_colors=5)

    def get_analysis_dict(self) -> dict:
        """Get the analysis data as a dict."""
        if not self.analysis:
            return {}
        try:
            return json.loads(self.analysis)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_dominant_colors(self) -> list[str]:
        """Get list of dominant color hex codes."""
        analysis = self.get_analysis_dict()
        colors = analysis.get("dominant_colors", [])
        return [c.get("hex") for c in colors if c.get("hex")]


def capture_and_analyze(doc_name: str):
    """
    Background job to capture website and analyze.

    Args:
        doc_name: Name of the Builder Site Inspiration document
    """
    doc = frappe.get_doc("Builder Site Inspiration", doc_name)

    try:
        doc.capture_website()
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error("Capture job failed", str(e))
        frappe.db.set_value(
            "Builder Site Inspiration",
            doc_name,
            {
                "status": "failed",
                "error_message": str(e)[:500],
            },
            update_modified=False,
        )
        frappe.db.commit()


@frappe.whitelist()
def capture_inspiration(
    url: str = None,
    image: str = None,
    sentiment: str = "like",
    description: str = None,
) -> dict:
    """
    API to capture a new inspiration source.

    Args:
        url: Website URL to capture (optional)
        image: Uploaded image file URL (optional)
        sentiment: User sentiment (like, dislike, neutral)
        description: User description/notes

    Returns:
        dict with doc name and status
    """
    if not url and not image:
        frappe.throw("Either url or image is required")

    source_type = "URL" if url else "Image"

    doc = frappe.get_doc({
        "doctype": "Builder Site Inspiration",
        "source_type": source_type,
        "url": url,
        "image": image,
        "sentiment": sentiment,
        "description": description,
        "status": "pending",
    })
    doc.insert(ignore_permissions=True)

    return {
        "name": doc.name,
        "status": doc.status,
        "message": "Capture started" if source_type == "URL" else "Image analyzed",
    }


@frappe.whitelist()
def get_inspirations(limit: int = 20, sentiment: str = None) -> list[dict]:
    """
    Get list of inspirations.

    Args:
        limit: Max number to return
        sentiment: Optional filter by sentiment

    Returns:
        List of inspiration summaries
    """
    filters = {"status": "captured"}
    if sentiment:
        filters["sentiment"] = sentiment

    inspirations = frappe.get_all(
        "Builder Site Inspiration",
        filters=filters,
        fields=[
            "name", "source_type", "url", "image", "screenshot", "thumbnail",
            "sentiment", "description", "status", "captured_at", "analysis"
        ],
        order_by="creation desc",
        limit=limit,
    )

    # Parse analysis and extract colors for preview
    for insp in inspirations:
        if insp.get("analysis"):
            try:
                analysis = json.loads(insp["analysis"])
                insp["dominant_colors"] = [
                    c.get("hex") for c in analysis.get("dominant_colors", [])[:5]
                ]
            except (json.JSONDecodeError, TypeError):
                insp["dominant_colors"] = []
        else:
            insp["dominant_colors"] = []

    return inspirations


@frappe.whitelist()
def analyze_inspirations_for_generation(inspiration_names: str = None) -> dict:
    """
    Analyze inspirations and return data for AI generation.

    Args:
        inspiration_names: JSON array of inspiration names (or None for all)

    Returns:
        Aggregated inspiration data for the design brief
    """
    filters = {"status": "captured"}

    if inspiration_names:
        names = json.loads(inspiration_names)
        filters["name"] = ["in", names]

    inspirations = frappe.get_all(
        "Builder Site Inspiration",
        filters=filters,
        fields=["sentiment", "description", "analysis"],
    )

    # Aggregate data
    liked_colors = []
    disliked_colors = []
    notes = {"like": [], "dislike": []}

    for insp in inspirations:
        sentiment = insp.get("sentiment", "neutral")

        if insp.get("analysis"):
            try:
                analysis = json.loads(insp["analysis"])
                colors = [c.get("hex") for c in analysis.get("dominant_colors", [])[:3]]

                if sentiment == "like":
                    liked_colors.extend(colors)
                elif sentiment == "dislike":
                    disliked_colors.extend(colors)
            except (json.JSONDecodeError, TypeError):
                pass

        if insp.get("description") and sentiment in notes:
            notes[sentiment].append(insp["description"])

    return {
        "liked_colors": list(dict.fromkeys(liked_colors))[:8],
        "disliked_colors": list(dict.fromkeys(disliked_colors))[:5],
        "liked_notes": notes["like"][:5],
        "disliked_notes": notes["dislike"][:3],
        "total_inspirations": len(inspirations),
    }
