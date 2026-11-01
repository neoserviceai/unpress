"""
Website Screenshotter for Inspiration Module

Captures full-page screenshots of websites using Playwright.
"""

import asyncio
import io
from typing import Optional

import frappe


class WebsiteScreenshotter:
    """
    Captures screenshots of websites for design inspiration.

    Uses Playwright to render pages headlessly and capture full-page screenshots.
    """

    def __init__(self, viewport_width: int = 1440, viewport_height: int = 900):
        """
        Initialize the screenshotter.

        Args:
            viewport_width: Default viewport width (desktop)
            viewport_height: Default viewport height
        """
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

    async def capture_async(
        self,
        url: str,
        full_page: bool = True,
        timeout: int = 30000,
    ) -> dict:
        """
        Capture a screenshot of the given URL asynchronously.

        Args:
            url: URL to capture
            full_page: Whether to capture the full page or just viewport
            timeout: Navigation timeout in milliseconds

        Returns:
            dict with screenshot bytes, title, and metadata
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required for website screenshots. "
                "Install with: pip install playwright && playwright install chromium"
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": self.viewport_width, "height": self.viewport_height}
                )

                # Navigate to URL
                await page.goto(url, timeout=timeout, wait_until="networkidle")

                # Wait a bit for any animations to settle
                await page.wait_for_timeout(1000)

                # Capture screenshot
                screenshot_bytes = await page.screenshot(
                    full_page=full_page,
                    type="png"
                )

                # Get page metadata
                title = await page.title()

                # Get page dimensions
                dimensions = await page.evaluate("""
                    () => ({
                        width: document.documentElement.scrollWidth,
                        height: document.documentElement.scrollHeight
                    })
                """)

                return {
                    "screenshot": screenshot_bytes,
                    "title": title,
                    "url": url,
                    "width": dimensions.get("width", self.viewport_width),
                    "height": dimensions.get("height", self.viewport_height),
                    "viewport_width": self.viewport_width,
                    "success": True,
                }

            finally:
                await browser.close()

    def capture(
        self,
        url: str,
        full_page: bool = True,
        timeout: int = 30000,
    ) -> dict:
        """
        Capture a screenshot synchronously (wrapper around async method).

        Args:
            url: URL to capture
            full_page: Whether to capture the full page or just viewport
            timeout: Navigation timeout in milliseconds

        Returns:
            dict with screenshot bytes, title, and metadata
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.capture_async(url, full_page, timeout)
        )

    def capture_and_save(
        self,
        url: str,
        doc_name: Optional[str] = None,
        full_page: bool = True,
    ) -> dict:
        """
        Capture screenshot and save to Frappe File.

        Args:
            url: URL to capture
            doc_name: Optional document name to link file to
            full_page: Whether to capture the full page

        Returns:
            dict with file_url, file_doc, and capture metadata
        """
        result = self.capture(url, full_page=full_page)

        if not result.get("success"):
            return result

        # Generate filename from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace(".", "_")
        filename = f"inspiration_{domain}_{frappe.generate_hash(length=6)}.png"

        # Save to Frappe File
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": result["screenshot"],
            "is_private": 0,
        })
        file_doc.save(ignore_permissions=True)

        return {
            "file_url": file_doc.file_url,
            "file_doc_name": file_doc.name,
            "title": result.get("title"),
            "url": url,
            "width": result.get("width"),
            "height": result.get("height"),
            "success": True,
        }


def capture_website_screenshot(url: str, full_page: bool = True) -> dict:
    """
    Convenience function to capture a website screenshot.

    Args:
        url: URL to capture
        full_page: Whether to capture full page

    Returns:
        dict with capture result
    """
    screenshotter = WebsiteScreenshotter()
    return screenshotter.capture_and_save(url, full_page=full_page)
