"""
ComfyUI image client — self-hosted image generation + editing (Olares One).

Server-side only: the admin key (same as the LLM, i.e. nora_api_key) must never
reach the browser. Async queue: POST /prompt → poll /history/{id} → GET /view.

Workflows mirror docs/comfyui-builder-api.md (Olares repo):
  A. generate_image      — FLUX.2 klein text→image (heroes, banners, lifestyle)
  B. remove_background    — BiRefNet product cutout → transparent PNG
  C. upscale              — Real-ESRGAN ×4

Model FLUX.2 [klein] Apache-2.0 · BiRefNet MIT · Real-ESRGAN BSD (commercial-safe).
"""

import copy
import io
import json
import time

import frappe
import requests

from unpress_core.ai.logging import ai_log


POLL_SECONDS = 180  # 1024² generation ~30s; allow for a shared-GPU queue


def _settings():
    """ComfyUI endpoint for THIS site. No default URL on purpose: this app is
    open source, so it must never point at someone else's private GPU. Set
    comfyui_url (+ comfyui_api_key if the server is protected) per site."""
    conf = frappe.conf
    url = (conf.get("comfyui_url") or "").rstrip("/")
    key = conf.get("comfyui_api_key") or conf.get("nora_api_key")
    return url, key


def is_configured() -> bool:
    """True only when ComfyUI was DELIBERATELY chosen for this site.

    Key presence alone is not enough: nora_api_key is the shared LLM admin key,
    so every AI-enabled site used to look "ComfyUI-ready" and got routed here.
    When the shared GPU is busy the graph dies with an out-of-memory error that
    the worker swallows per-image — sites silently kept their placeholders
    (observed on a managed fleet). ComfyUI now requires an explicit opt-in
    (comfyui_url or comfyui_api_key); everything else takes the Ollama/Flux
    path, which loads and unloads the model per request.
    """
    url, key = _settings()
    return bool(url and key)


def health() -> tuple[bool, str]:
    """Live check: server reachable AND the GPU has room for the graph."""
    base, key = _settings()
    if not base:
        return False, "No comfyui_url configured"
    if not key:
        return False, "No ComfyUI key configured"
    try:
        resp = requests.get(f"{base}/system_stats", headers=_headers(), timeout=15)
    except Exception as e:
        return False, f"Unreachable: {e}"
    if resp.status_code in (401, 403):
        return False, f"Key rejected (HTTP {resp.status_code})"
    if not resp.ok:
        return False, f"HTTP {resp.status_code}"
    try:
        devices = resp.json().get("devices") or []
        if devices:
            free = devices[0].get("vram_free") or 0
            # FLUX.2 klein 4b + qwen text encoder need ~12 GB of headroom
            if free and free < 12 * 1024**3:
                return False, f"GPU busy ({round(free / 1024**3, 1)} GB free, needs ~12 GB)"
    except Exception:
        pass
    return True, "ComfyUI ready"


# ---------------------------------------------------------------------------
# Workflow templates (edit a copy per call — never mutate these)
# ---------------------------------------------------------------------------

_WF_GENERATE = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b.safetensors", "weight_dtype": "fp8_e4m3fn"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b_fp4_flux2.safetensors", "type": "flux2"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
    "5": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["4", 0], "guidance": 3.0}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
    "7": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
    "8": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "seed": 42, "steps": 6, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
    "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "gen"}},
}

_WF_REMOVE_BG = {
    "1": {"class_type": "LoadImage", "inputs": {"image": ""}},
    "20": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}},
    "21": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["20", 0], "image": ["1", 0]}},
    "22": {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["1", 0], "alpha": ["21", 0]}},
    "23": {"class_type": "SaveImage", "inputs": {"images": ["22", 0], "filename_prefix": "cutout"}},
}

_WF_UPSCALE = {
    "1": {"class_type": "LoadImage", "inputs": {"image": ""}},
    "30": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "RealESRGAN_x4plus.pth"}},
    "31": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["30", 0], "image": ["1", 0]}},
    "32": {"class_type": "SaveImage", "inputs": {"images": ["31", 0], "filename_prefix": "upscaled"}},
}


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def _headers():
    _, key = _settings()
    return {"Authorization": f"Bearer {key}"}


def _run_workflow(workflow: dict) -> bytes:
    """Queue a workflow and return the first output image's bytes."""
    base, key = _settings()
    if not base or not key:
        raise RuntimeError("ComfyUI not configured (set comfyui_url and comfyui_api_key)")

    pid = requests.post(
        f"{base}/prompt",
        headers={**_headers(), "Content-Type": "application/json"},
        data=json.dumps({"prompt": workflow}),
        timeout=30,
    ).json().get("prompt_id")
    if not pid:
        raise RuntimeError("ComfyUI did not return a prompt_id")

    for _ in range(POLL_SECONDS):
        hist = requests.get(f"{base}/history/{pid}", headers=_headers(), timeout=30).json()
        if pid in hist:
            status = hist[pid].get("status", {})
            if status.get("status_str") != "success":
                # surface the node's own exception — "error" alone told us
                # nothing and hid a plain out-of-memory for months
                detail = ""
                for kind, payload in status.get("messages", []):
                    if kind == "execution_error":
                        detail = (payload.get("exception_message") or "").splitlines()[0]
                        node = payload.get("node_type") or payload.get("node_id")
                        detail = f"{node}: {detail}" if node else detail
                        break
                raise RuntimeError(
                    f"ComfyUI generation failed ({status.get('status_str')})"
                    + (f" — {detail}" if detail else "")
                )
            for node in hist[pid].get("outputs", {}).values():
                for im in node.get("images", []):
                    q = f"filename={im['filename']}&subfolder={im.get('subfolder', '')}&type={im.get('type', 'output')}"
                    resp = requests.get(f"{base}/view?{q}", headers=_headers(), timeout=60)
                    if resp.ok and resp.content:
                        return resp.content
            raise RuntimeError("ComfyUI finished with no output image")
        time.sleep(1)
    raise TimeoutError("ComfyUI generation timed out")


def _upload_input(content: bytes, filename: str = "input.png") -> str:
    base, _ = _settings()
    r = requests.post(
        f"{base}/upload/image",
        headers=_headers(),
        files={"image": (filename, io.BytesIO(content), "image/png")},
        timeout=60,
    )
    return r.json()["name"]


def _save_png(content: bytes, prefix: str = "ai_image") -> str:
    """Persist generated bytes as a public Frappe File; return its file_url."""
    fname = f"{prefix}_{frappe.generate_hash(length=8)}.png"
    fdoc = frappe.get_doc({
        "doctype": "File", "file_name": fname, "is_private": 0, "content": content,
    }).insert(ignore_permissions=True)
    return fdoc.file_url


def _file_bytes(file_url: str) -> bytes:
    from unpress_core.ai.providers.base import BaseProvider  # reuse the resolver
    # local /files path → read from disk; otherwise fetch
    import os
    path = file_url
    site_url = frappe.utils.get_url()
    if path.startswith(site_url):
        path = path[len(site_url):]
    if path.startswith("/files/") or path.startswith("/private/files/"):
        base = frappe.get_site_path("public" if path.startswith("/files/") else "")
        full = os.path.join(base, path.lstrip("/"))
        with open(full, "rb") as f:
            return f.read()
    return requests.get(file_url, timeout=60).content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _norm_size(width: int, height: int, max_dim: int = 1024):
    """Cap the longest side at max_dim (FLUX is optimal ~1MP) and round to /64."""
    w, h = int(width or 1024), int(height or 1024)
    scale = min(1.0, max_dim / max(w, h))
    w, h = int(w * scale), int(h * scale)
    rnd = lambda v: max(256, (v // 64) * 64)
    return rnd(w), rnd(h)


def generate_image(prompt: str, width: int = 1024, height: int = 1024, seed: int = None) -> str:
    """Workflow A — text→image. Returns the saved /files/ URL."""
    wf = copy.deepcopy(_WF_GENERATE)
    wf["4"]["inputs"]["text"] = prompt or "professional photography, clean composition, no text"
    w, h = _norm_size(width, height)
    wf["7"]["inputs"]["width"], wf["7"]["inputs"]["height"] = w, h
    # generate_hash returns hex, so cint() on it was always 0 -> every image
    # shared seed 42 and identical prompts produced byte-identical pictures
    wf["8"]["inputs"]["seed"] = int(seed) if seed is not None else int(frappe.generate_hash(length=8), 16) % (2**31)
    ai_log("info", "ComfyUI generate", w=w, h=h, prompt=(prompt or "")[:60])
    return _save_png(_run_workflow(wf), prefix="gen")


def remove_background(file_url: str) -> str:
    """Workflow B — product cutout (transparent PNG). Returns the saved /files/ URL."""
    name = _upload_input(_file_bytes(file_url), "product.png")
    wf = copy.deepcopy(_WF_REMOVE_BG)
    wf["1"]["inputs"]["image"] = name
    return _save_png(_run_workflow(wf), prefix="cutout")


def upscale(file_url: str) -> str:
    """Workflow C — Real-ESRGAN ×4. Returns the saved /files/ URL."""
    name = _upload_input(_file_bytes(file_url), "to_upscale.png")
    wf = copy.deepcopy(_WF_UPSCALE)
    wf["1"]["inputs"]["image"] = name
    return _save_png(_run_workflow(wf), prefix="upscaled")
