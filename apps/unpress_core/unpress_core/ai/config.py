"""
AI Configuration Module

Resolution order (first non-empty wins):

1. site_config.json (frappe.conf) — the operator layer. A managed host
   pins its values here; anything set in site_config always wins.
2. Builder Settings (the Studio UI) — the self-host layer. The custom
   fields unpress_ai_* plus the upstream ai_api_key Password field, all
   editable from the builder Settings > AI tab. No desk, no SSH needed.
3. Hardcoded DEFAULTS below.
"""

from dataclasses import dataclass
from typing import Literal, Optional

import frappe


ProviderType = Literal["openai", "ollama"]
ThemeType = Literal["modern", "neobrutalist", "glassmorphism", "minimal", "corporate", "creative"]
SiteType = Literal["single_page", "multi_page", "multi_page_auth", "ecommerce", "blog", "portfolio"]


# Think level → per-model value. Kimi expects bool, GPT-OSS expects string,
# everything else defaults to bool.
THINK_LEVEL_MAP = {
    # K3 ships with reasoning ALWAYS ON (no instruct variant) — never send
    # think=False, whatever the configured level.
    "kimi-k3": {"low": True, "medium": True, "high": True},
    "kimi-k2.5": {"low": False, "medium": True, "high": True},
    "kimi-k2": {"low": False, "medium": True, "high": True},
    "glm": {"low": True, "medium": True, "high": True},
    "gpt-oss": {"low": "low", "medium": "medium", "high": "high"},
    "default": {"low": False, "medium": True, "high": True},
}


# Production defaults — decision validated on 2026-07-18 after the
# A/B on the dev16 bench (see Unpress/16-Design-Intelligence-Et-K3):
# - brief on kimi-k3: the quality step comes from the K3 brief + design
#   candidates; one call per site, so the 5× output pricing is negligible there.
# - pages on kimi-k2.7-code: ~90% of K3 page quality at ~1/7 the cost and
#   2.5× the speed (K3 pages: 47 min/91.8k tokens vs k2.7: 19 min/64k).
# Note: an instance whose site_config pins openai_model overrides this
# default — the operator has to push the new value there too.
DEFAULTS = {
    "provider": "openai",
    "model": "kimi-k3",
    "page_model": "kimi-k2.7-code",
    "base_url": "https://api.moonshot.ai/v1",
    "api_key": None,
    "temperature": 0.6,
    "max_tokens": 16384,
    # 1200s: kimi-k2.6 with thinking can exceed 15 min on dense pages
    "request_timeout": 1200,
    "connect_timeout": 30,
    "default_theme": "modern",
    "default_site_type": "multi_page",
    "output_language": "French",
    "brief_think_level": "high",
    "page_think_level": "high",
    "reasoning_effort": None,
}


# Per-provider recommended models.
RECOMMENDED_MODELS = {
    "openai": {
        # K3 leads Frontend Code Arena and has native vision + 1M context;
        # kept out of "balanced"/"fast" for cost (5× K2.x on output tokens).
        "best_quality": "kimi-k3",
        "balanced": "kimi-k2.6",
        "fast": "kimi-k2.6",
        "creative": "kimi-k3",
    },
    "ollama": {
        "best_quality": "kimi-k2.6:cloud",
        "balanced": "kimi-k2.6:cloud",
        "fast": "qwen2.5:7b",
        "creative": "kimi-k2.6:cloud",
        "code": "deepseek-coder:6.7b",
    },
}


@dataclass
class AIConfig:
    """Runtime AI configuration, resolved from site_config.json."""

    provider: ProviderType = DEFAULTS["provider"]
    model: Optional[str] = DEFAULTS["model"]
    # Model used for page generation (code). Falls back to `model` when unset.
    page_model: Optional[str] = DEFAULTS["page_model"]
    api_key: Optional[str] = DEFAULTS["api_key"]
    base_url: Optional[str] = DEFAULTS["base_url"]

    temperature: float = DEFAULTS["temperature"]
    max_tokens: int = DEFAULTS["max_tokens"]
    max_retries: int = 3

    default_theme: ThemeType = DEFAULTS["default_theme"]
    default_site_type: SiteType = DEFAULTS["default_site_type"]
    output_language: str = DEFAULTS["output_language"]

    request_timeout: int = DEFAULTS["request_timeout"]
    connect_timeout: int = DEFAULTS["connect_timeout"]

    brief_think_level: str = DEFAULTS["brief_think_level"]
    page_think_level: str = DEFAULTS["page_think_level"]

    # Codex exposes this as model_reasoning_effort; empty means the provider
    # picks. Kept on the config rather than in the provider so the Studio and
    # site_config reach it the same way as the model.
    reasoning_effort: Optional[str] = None

    def get_think_value(self, level: str) -> bool | str:
        """Convert a think level to the value expected by the current model."""
        if not self.model:
            return THINK_LEVEL_MAP["default"].get(level, True)

        model_lower = self.model.lower()
        value = THINK_LEVEL_MAP["default"].get(level, True)
        for model_key, mapping in THINK_LEVEL_MAP.items():
            if model_key != "default" and model_key in model_lower:
                value = mapping.get(level, True)
                break
        # Moonshot *-code models (e.g. kimi-k2.7-code) REQUIRE thinking — a
        # request with thinking disabled returns a 400. Never send think=False
        # for them, whatever the configured think level resolves to.
        if value is False and "code" in model_lower:
            return True
        return value


def _studio_value(field: str) -> Optional[str]:
    """One field from the Builder Settings single (the Studio UI settings).

    Returns None when builder is not installed yet, the table is missing
    (pre-migrate), or the field is empty — resolution then falls through
    to the code defaults.
    """
    try:
        value = getattr(frappe.get_cached_doc("Builder Settings"), field, None)
        return value or None
    except Exception:
        return None


def _studio_api_key() -> Optional[str]:
    """The upstream Builder Settings ai_api_key (Password field, encrypted)."""
    try:
        from frappe.utils.password import get_decrypted_password

        return (
            get_decrypted_password(
                "Builder Settings", "Builder Settings", "ai_api_key", raise_exception=False
            )
            or None
        )
    except Exception:
        return None


def get_ai_settings() -> AIConfig:
    """
    Resolve AI settings: site_config.json > Builder Settings (Studio UI) > DEFAULTS.

    Keys read from frappe.conf (always win when set):
        ai_provider        (default: "openai")
        openai_model       aliases: ollama_model
        openai_page_model  aliases: ollama_page_model
        openai_base_url    aliases: ollama_base_url, ollama_url
        openai_api_key     aliases: ollama_api_key
        ai_temperature
        ai_max_tokens
        ai_request_timeout
        ai_default_theme
        ai_default_site_type
        ai_output_language

    Builder Settings fields (Settings > AI in the Studio):
        unpress_ai_provider, unpress_ai_brief_model, unpress_ai_page_model,
        unpress_ai_base_url, unpress_ai_output_language, ai_api_key
    """
    conf = frappe.conf

    provider = (
        conf.get("ai_provider")
        or conf.get("ollama_provider")
        or _studio_value("unpress_ai_provider")
        or DEFAULTS["provider"]
    )
    # DEFAULTS["model"] is a Moonshot model name. Handing it to a provider that
    # has never heard of it turns a working setup into a 400 — a ChatGPT plan
    # answers "The 'kimi-k3' model is not supported when using Codex with a
    # ChatGPT account". A subscription picks its own model, so when nobody has
    # named one explicitly, name none.
    model_default = None if provider == "codex" else DEFAULTS["model"]
    page_model_default = None if provider == "codex" else DEFAULTS["page_model"]
    model = (
        conf.get("openai_model")
        or conf.get("ollama_model")
        or conf.get("codex_model")
        or _studio_value("unpress_ai_brief_model")
        or model_default
    )
    page_model = (
        conf.get("openai_page_model")
        or conf.get("ollama_page_model")
        or conf.get("codex_model")
        or _studio_value("unpress_ai_page_model")
        or page_model_default
    )
    base_url = (
        conf.get("openai_base_url")
        or conf.get("ollama_base_url")
        or conf.get("ollama_url")
        or _studio_value("unpress_ai_base_url")
        or DEFAULTS["base_url"]
    )
    api_key = (
        conf.get("openai_api_key")
        or conf.get("ollama_api_key")
        or _studio_api_key()
        or DEFAULTS["api_key"]
    )

    reasoning_effort = (
        conf.get("codex_reasoning_effort")
        or conf.get("ai_reasoning_effort")
        or _studio_value("unpress_ai_reasoning_effort")
        or DEFAULTS["reasoning_effort"]
    )

    return AIConfig(
        provider=provider,
        model=model,
        page_model=page_model,
        reasoning_effort=reasoning_effort or None,
        base_url=base_url,
        api_key=api_key,
        temperature=float(conf.get("ai_temperature") or DEFAULTS["temperature"]),
        max_tokens=int(conf.get("ai_max_tokens") or DEFAULTS["max_tokens"]),
        request_timeout=int(conf.get("ai_request_timeout") or DEFAULTS["request_timeout"]),
        default_theme=conf.get("ai_default_theme") or DEFAULTS["default_theme"],
        default_site_type=conf.get("ai_default_site_type") or DEFAULTS["default_site_type"],
        output_language=(
            conf.get("ai_output_language")
            or _studio_value("unpress_ai_output_language")
            or DEFAULTS["output_language"]
        ),
    )


# site_config keys that silently win over anything chosen in the Studio UI.
# Kept next to get_ai_settings so the two never drift.
PINNING_KEYS = {
    "provider": ("ai_provider", "ollama_provider"),
    "base_url": ("openai_base_url", "ollama_base_url", "ollama_url"),
    "api_key": ("openai_api_key", "ollama_api_key"),
    "model": ("openai_model", "ollama_model"),
    "output_language": ("ai_output_language",),
}


# "Managed" is DECLARED, never inferred.
#
# It first tried to guess — endpoint + credential pinned in site_config meant
# managed — and that was wrong: a self-hoster who puts their own key in
# site_config (a perfectly normal thing to do) got locked out of their own
# settings. Hosting is a commercial fact about the install, not a shape its
# configuration happens to have.
#
#     bench --site <site> set-config ai_managed 1
#
# Only a provider that actually runs the models for its customers sets it.
MANAGED_KEY = "ai_managed"


def _available_providers() -> list[dict]:
    """The provider choices this particular install can honour.

    Computed here rather than hardcoded in the UI so that one component serves
    every edition: Codex only shows up where the CLI is actually usable, and a
    fork that adds a provider adds it once, server-side.
    """
    providers = [
        {"value": "moonshot", "label": "Moonshot AI"},
        {"value": "openrouter", "label": "OpenRouter"},
        {"value": "openai", "label": "OpenAI"},
        {"value": "ollama", "label": "Ollama"},
        {"value": "custom", "label": "Custom"},
    ]
    try:
        from unpress_core.ai.providers.codex_provider import CodexProvider

        if CodexProvider.enabled_here() and CodexProvider.binary():
            # a personal ChatGPT plan: only where it was deliberately enabled
            providers.insert(1, {"value": "codex", "label": "ChatGPT subscription"})
    except Exception:
        pass
    return providers


@frappe.whitelist()
def describe_resolution() -> dict:
    """What this install lets a user configure, and what is already decided.

    The AI tab renders whatever this returns — that is the whole point. A
    provider that runs the models for its customers declares `ai_managed`, so
    the tab shows a short statement instead of dead input fields. Everyone
    else gets the full form, with the provider list this install can honour.

    One component, one code path; the difference between editions is data.

    Returns NOTHING about the infrastructure when managed: which endpoint and
    which model a host runs is the host's business, not a detail to publish in
    a customer's settings screen.
    """
    frappe.only_for("System Manager")
    conf = frappe.conf
    managed = bool(frappe.utils.cint(conf.get(MANAGED_KEY)))
    if managed:
        return {"managed": True, "pinned": {}, "providers": [], "effective": {}}

    # Which fields site_config decides — the NAMES only. The values are the
    # operator's business and can name private infrastructure; echoing them
    # into a settings screen is how an internal hostname ends up on someone
    # else's monitor.
    pinned = [field for field, keys in PINNING_KEYS.items() if any(conf.get(k) for k in keys)]

    return {
        "managed": False,
        "pinned": pinned,
        "providers": _available_providers(),
    }


ASSISTANT_NAME = "Unpress AI"


def get_assistant_name() -> str:
    """How the assistant introduces itself.

    Overridable per site (`unpress_ai_name` in site_config) so a fork or a host
    application can put its own product name in front of the user without
    patching the prompts.
    """
    return frappe.conf.get("unpress_ai_name") or ASSISTANT_NAME


def get_image_settings() -> dict:
    """Image backend for this site: site_config > Builder Settings > defaults.

    Deliberately provider-agnostic and endpoint-less by default — this app is
    open source, so it must never ship someone's private GPU as a fallback.
    Any OpenAI-compatible /v1/images/generations host works (OpenAI itself, a
    local Ollama serving Flux, a gateway); ComfyUI has its own client.
    """
    conf = frappe.conf
    enabled = conf.get("image_generation_enabled")
    if enabled is None:
        enabled = _studio_value("unpress_ai_image_enabled")

    base_url = (
        conf.get("image_base_url")
        or conf.get("ollama_base_url")
        or conf.get("ollama_url")
        or _studio_value("unpress_ai_image_base_url")
    )
    api_key = conf.get("image_api_key") or conf.get("ollama_api_key")
    if not api_key:
        try:
            from frappe.utils.password import get_decrypted_password

            api_key = (
                get_decrypted_password(
                    "Builder Settings", "Builder Settings", "unpress_ai_image_api_key", raise_exception=False
                )
                or None
            )
        except Exception:
            api_key = None

    return {
        "enabled": bool(frappe.utils.cint(enabled)),
        # "codex" routes images through the local Codex CLI (ChatGPT plan);
        # anything else means the OpenAI-compatible endpoint below.
        "provider": conf.get("image_provider") or _studio_value("unpress_ai_image_provider") or "",
        "base_url": base_url,
        "api_key": api_key,
        "model": conf.get("image_model") or _studio_value("unpress_ai_image_model") or "gpt-image-1",
        "size": conf.get("image_size") or _studio_value("unpress_ai_image_size") or "1024x1024",
    }


def get_model_for_task(task: str, provider: str = None) -> str:
    """Return the recommended model name for a given task + provider."""
    if not provider:
        provider = get_ai_settings().provider
    models = RECOMMENDED_MODELS.get(provider, {})
    return models.get(task, models.get("balanced", ""))


def validate_provider_config(config: AIConfig) -> tuple[bool, str]:
    """Ensure the resolved config has enough info to call the provider."""
    if config.provider == "openai":
        if not config.api_key:
            return False, "No API key configured (Studio Settings > AI, or openai_api_key in site_config.json)"
        if not config.model:
            return False, "No model configured (Studio Settings > AI, or openai_model in site_config.json)"
        return True, ""

    if config.provider == "ollama":
        if not config.base_url:
            return False, "No Ollama URL configured (Studio Settings > AI, or ollama_base_url in site_config.json)"
        if not config.model:
            return False, "No model configured (Studio Settings > AI, or ollama_model in site_config.json)"
        return True, ""

    return False, f"Unknown provider: {config.provider}"


__all__ = [
    "AIConfig",
    "DEFAULTS",
    "RECOMMENDED_MODELS",
    "THINK_LEVEL_MAP",
    "ProviderType",
    "SiteType",
    "ThemeType",
    "get_ai_settings",
    "get_image_settings",
    "get_model_for_task",
    "validate_provider_config",
]
