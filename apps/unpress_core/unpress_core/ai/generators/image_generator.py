"""
Image Generator
Generates images using Ollama's OpenAI-compatible API with Flux models.
"""

import base64
import hashlib
import os
from typing import Optional
from dataclasses import dataclass

import frappe
from frappe.utils import get_files_path


@dataclass
class GeneratedImage:
    """Result of image generation"""
    file_url: str
    file_doc_name: str
    prompt: str
    width: int
    height: int


class ImageGenerator:
    """
    Generate images using Ollama's image generation models (Flux).

    Uses the OpenAI-compatible API endpoint /v1/images/generations.
    """

    DEFAULT_MODEL = "x/flux2-klein:latest"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_QUALITY = "standard"
    # a 1MP Flux render measured ~31s on the shared endpoint; leave room for
    # a cold model load
    TIMEOUT = 300

    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        api_key: str = None,
        size: str = None,
        quality: str = None,
    ):
        """
        Initialize the image generator.

        Args:
            model: Ollama image model (default: x/flux2-klein:latest)
            base_url: Ollama server URL
            api_key: API key for remote servers
            size: Image size (e.g., "1024x1024", "512x512")
            quality: Image quality ("standard" or "hd")
        """
        settings = self._get_settings()

        self.model = model or settings.get("model") or self.DEFAULT_MODEL
        self.base_url = base_url or settings.get("base_url") or "http://localhost:11434"
        self.api_key = api_key or settings.get("api_key") or "ollama"
        self.size = size or settings.get("size") or self.DEFAULT_SIZE
        self.quality = quality or self.DEFAULT_QUALITY

        # Parse size
        self.width, self.height = self._parse_size(self.size)

    def _get_settings(self) -> dict:
        """Resolved image settings (site_config > Studio Settings > defaults)."""
        from unpress_core.ai.config import get_image_settings

        return get_image_settings()

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string to width, height tuple"""
        try:
            w, h = size.lower().split("x")
            return int(w), int(h)
        except Exception:
            return 1024, 1024

    def generate(
        self,
        prompt: str,
        size: str = None,
        negative_prompt: str = None,
        seed: int = None,
        steps: int = None,
    ) -> GeneratedImage:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the image to generate
            size: Image size (e.g., "1024x1024")
            negative_prompt: What to avoid in the image
            seed: Random seed for reproducibility
            steps: Number of generation steps

        Returns:
            GeneratedImage with file URL and metadata
        """
        import requests

        # Apply default negative prompt to prevent text/logos in generated images
        if not negative_prompt:
            negative_prompt = "text, words, letters, logos, watermarks, typography, UI elements, signatures"

        # Build the full prompt with negative prompt
        full_prompt = f"{prompt}. Avoid: {negative_prompt}"

        # Parse size
        if size:
            width, height = self._parse_size(size)
        else:
            width, height = self.width, self.height

        # Plain HTTP against the OpenAI-compatible /v1/images/generations
        # endpoint — the `openai` SDK is NOT a dependency of this app, so
        # importing it made this whole path an ImportError away from dead.
        url = f"{self.base_url.rstrip('/')}/v1/images/generations"
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "ollama":
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key

        params = {
            "model": self.model,
            "prompt": full_prompt,
            "size": f"{width}x{height}",
            "response_format": "b64_json",
            "n": 1,
        }

        frappe.logger().info(f"Generating image with Flux: {prompt[:50]}...")

        try:
            response = requests.post(url, headers=headers, json=params, timeout=self.TIMEOUT)
            if not response.ok:
                raise ValueError(f"HTTP {response.status_code} from {url}: {response.text[:200]}")
            payload = response.json()
            items = payload.get("data") or []
            if not items or not items[0].get("b64_json"):
                raise ValueError("No image data in response")

            image_data = base64.b64decode(items[0]["b64_json"])

            # Hash the FULL prompt plus a nonce: hashing only the visible
            # prompt made two slots with the same description overwrite each
            # other's file.
            prompt_hash = hashlib.md5(full_prompt.encode()).hexdigest()[:12]
            filename = f"ai_generated_{prompt_hash}_{frappe.generate_hash(length=6)}.png"

            # Save as Frappe File
            file_doc = self._save_image(image_data, filename, prompt)

            return GeneratedImage(
                file_url=file_doc.file_url,
                file_doc_name=file_doc.name,
                prompt=prompt,
                width=width,
                height=height,
            )

        except Exception as e:
            frappe.log_error("Image generation failed", str(e))
            raise

    def _save_image(self, image_data: bytes, filename: str, prompt: str) -> "frappe.Document":
        """Save image data as a Frappe File document"""
        # Create file in public files
        file_path = get_files_path(filename, is_private=False)

        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write image data
        with open(file_path, "wb") as f:
            f.write(image_data)

        # Create File document
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "file_url": f"/files/{filename}",
            "is_private": 0,
            "folder": "Home/Attachments",
        })

        # Add description with prompt
        file_doc.description = f"AI Generated: {prompt[:200]}"

        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return file_doc

    def generate_async(
        self,
        prompt: str,
        callback_doctype: str = None,
        callback_name: str = None,
        callback_field: str = None,
        **kwargs
    ) -> str:
        """
        Queue image generation as a background job.

        Args:
            prompt: Text description of the image
            callback_doctype: DocType to update when done
            callback_name: Document name to update
            callback_field: Field to store the image URL
            **kwargs: Additional args passed to generate()

        Returns:
            str: Job ID for tracking
        """
        job = frappe.enqueue(
            "unpress_core.ai.generators.image_generator.generate_image_job",
            queue="long",
            timeout=300,
            prompt=prompt,
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            size=kwargs.get("size", self.size),
            callback_doctype=callback_doctype,
            callback_name=callback_name,
            callback_field=callback_field,
            **kwargs
        )

        return job.id


def generate_image_job(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    size: str = "1024x1024",
    callback_doctype: str = None,
    callback_name: str = None,
    callback_field: str = None,
    **kwargs
):
    """
    Background job for image generation.

    This function is called by Frappe's job queue.
    """
    generator = ImageGenerator(
        model=model,
        base_url=base_url,
        api_key=api_key,
        size=size,
    )

    try:
        result = generator.generate(prompt, **kwargs)

        # Update callback document if provided
        if callback_doctype and callback_name and callback_field:
            doc = frappe.get_doc(callback_doctype, callback_name)
            doc.set(callback_field, result.file_url)
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            frappe.publish_realtime(
                "image_generated",
                {
                    "doctype": callback_doctype,
                    "name": callback_name,
                    "field": callback_field,
                    "file_url": result.file_url,
                },
                doctype=callback_doctype,
                docname=callback_name,
            )

        return result.file_url

    except Exception as e:
        frappe.log_error("Image generation job failed", str(e))

        if callback_doctype and callback_name:
            frappe.publish_realtime(
                "image_generation_failed",
                {
                    "doctype": callback_doctype,
                    "name": callback_name,
                    "error": str(e),
                },
                doctype=callback_doctype,
                docname=callback_name,
            )

        raise


__all__ = [
    "ImageGenerator",
    "GeneratedImage",
    "generate_image_job",
]
