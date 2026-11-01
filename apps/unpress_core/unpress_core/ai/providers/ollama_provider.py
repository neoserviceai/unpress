"""
Ollama Provider
Implements AI generation using Ollama's API with structured output support.

Supports both the official Ollama SDK (recommended) and HTTP fallback.
Optimized for Kimi K2.5 with 256k context window.
"""

import json
from typing import TypeVar, Optional
from pydantic import BaseModel
import frappe

from unpress_core.ai.providers.base import (
    BaseProvider,
    GenerationError,
    ValidationError,
)
from unpress_core.ai.logging import ai_log

# Check if Ollama SDK is available
try:
    from ollama import Client
    OLLAMA_SDK_AVAILABLE = True
except ImportError:
    OLLAMA_SDK_AVAILABLE = False

T = TypeVar("T", bound=BaseModel)


class OllamaProvider(BaseProvider):
    """
    Ollama provider with support for:
    - Kimi K2.5 with 256k context (default)
    - Structured outputs via JSON schema (Ollama 0.5+)
    - Official Ollama SDK with HTTP fallback
    - Retry logic for transient failures

    Recommended models for JSON generation:
    - kimi-k2.5:cloud - Best for large structured output (256k context)
    - qwen2.5:7b - Good for structured output
    - qwen2.5:32b - Higher quality, slower
    - deepseek-coder:6.7b - Good for code/structure
    """

    DEFAULT_MODEL = "kimi-k2.5:cloud"
    DEFAULT_BASE_URL = "http://localhost:11434"

    # Optimized for Kimi K2.5 cloud - keep high limits for quality
    DEFAULT_NUM_CTX = 131072      # 128k context
    DEFAULT_MAX_TOKENS = 32768    # 32k output tokens (pages can be large)
    DEFAULT_TIMEOUT = 600         # 10 minutes for large generations

    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        api_key: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
        num_ctx: int = None,
        **kwargs
    ):
        conf = frappe.conf

        # Resolved settings (site_config > Builder Settings UI) apply only when
        # they actually point at ollama; a bare OllamaProvider built while the
        # configured provider is openai must not inherit openai's key/url.
        resolved = None
        try:
            from ..config import get_ai_settings

            resolved = get_ai_settings()
            if resolved.provider != "ollama":
                resolved = None
        except Exception:
            resolved = None

        super().__init__(
            model=model
            or conf.get("ollama_model")
            or (resolved.model if resolved else None)
            or self.DEFAULT_MODEL,
            base_url=(
                base_url
                or conf.get("ollama_base_url")
                or conf.get("ollama_url")
                or (resolved.base_url if resolved else None)
                or self.DEFAULT_BASE_URL
            ),
            api_key=api_key or conf.get("ollama_api_key") or (resolved.api_key if resolved else None),
            temperature=temperature if temperature is not None else 0.6,
            max_tokens=max_tokens or self.DEFAULT_MAX_TOKENS,
            timeout=timeout or int(conf.get("ollama_timeout") or self.DEFAULT_TIMEOUT),
            **kwargs,
        )
        self.num_ctx = num_ctx or int(conf.get("ollama_num_ctx") or self.DEFAULT_NUM_CTX)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def _use_sdk(self) -> bool:
        """
        Determine if we should use the SDK or HTTP fallback.

        The SDK doesn't support custom auth headers, so we must use HTTP
        when an API key is configured (e.g., for Cloudflare WAF protected servers).
        """
        return OLLAMA_SDK_AVAILABLE and not self.api_key

    def is_available(self) -> bool:
        """Check if Ollama server is running and model is available"""
        try:
            if self._use_sdk:
                client = Client(host=self.base_url)
                models = client.list().get("models", [])
            else:
                import requests
                headers = self._get_auth_headers()
                response = requests.get(
                    f"{self.base_url}/api/tags",
                    headers=headers,
                    timeout=5
                )
                if response.status_code != 200:
                    return False
                models = response.json().get("models", [])

            model_names = [m.get("name", "") for m in models]
            base_model = self.model.split(":")[0]
            return any(
                self.model in name or base_model in name
                for name in model_names
            )
        except Exception:
            return False

    def _get_auth_headers(self) -> dict:
        """Build authentication headers for API requests"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
            print(f"[OLLAMA] Using API key (length={len(self.api_key)}, starts={self.api_key[:8]}...)")
        else:
            print("[OLLAMA] No API key configured!")
        return headers

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        think: bool | str = False,
    ) -> str:
        """Generate text response

        Args:
            think: Reasoning mode - False to disable, True to enable, or "low"/"medium"/"high" for GPT-OSS
        """
        ai_log("info", "OllamaProvider.generate() called",
            model=self.model, base_url=self.base_url,
            use_sdk=self._use_sdk, num_ctx=self.num_ctx, think=think)

        messages = self._format_messages(prompt, system_prompt)

        if self._use_sdk:
            ai_log("debug", "Using Ollama SDK")
            return self._generate_with_sdk(messages, temperature, max_tokens)

        ai_log("debug", "Using HTTP API with streaming", think=think)
        return self._generate_with_http(messages, temperature, max_tokens, think=think)

    def _generate_with_sdk(
        self,
        messages: list,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Generate using official Ollama SDK"""
        try:
            ai_log("debug", "SDK client.chat() starting", model=self.model)
            client = Client(host=self.base_url)
            response = client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature or self.temperature,
                    "num_predict": max_tokens or self.max_tokens,
                    "num_ctx": self.num_ctx,
                },
            )
            content = response.message.content
            ai_log("info", "SDK response received", content_length=len(content))
            return content
        except Exception as e:
            ai_log("error", "SDK generation failed", error=str(e))
            raise GenerationError(f"Ollama generation failed: {e}")

    def _generate_with_http(
        self,
        messages: list,
        temperature: float = None,
        max_tokens: int = None,
        think: bool | str = False,
    ) -> str:
        """
        Generate using HTTP API with streaming to bypass Cloudflare timeout.

        Uses stream=True to keep the connection alive - Cloudflare won't
        timeout as long as data is flowing.

        Args:
            think: Reasoning mode - False to disable, True to enable, or "low"/"medium"/"high" for GPT-OSS
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,  # Stream to avoid Cloudflare 524 timeout
            "think": think,  # Enable/disable reasoning mode
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }

        ai_log("debug", "HTTP generate payload prepared",
            model=self.model, temperature=temperature or self.temperature,
            num_predict=max_tokens or self.max_tokens)

        try:
            result = self._make_streaming_request("/api/chat", payload)
            return result
        except Exception as e:
            ai_log("error", "HTTP generation failed", error=str(e))
            raise GenerationError(f"Ollama generation failed: {e}")

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str = None,
        temperature: float = None,
        max_retries: int = 3,
        think: bool | str = False,
    ) -> T:
        """
        Generate structured response using Ollama's JSON schema support.

        Includes retry logic with progressive temperature increase
        for better recovery from transient failures.

        Args:
            prompt: User prompt
            schema: Pydantic model class for output structure
            system_prompt: Optional system prompt
            temperature: Generation temperature (default: self.temperature)
            max_retries: Number of retry attempts (default: 3)
            think: Reasoning mode - False to disable, True to enable, or "low"/"medium"/"high" for GPT-OSS

        Returns:
            Instance of the schema class with generated content
        """
        schema_dict = schema.model_json_schema()
        enhanced_system = self._build_structured_system_prompt(
            system_prompt,
            schema_dict
        )

        messages = self._format_messages(prompt, enhanced_system)
        current_temp = temperature or self.temperature
        last_error = None

        for attempt in range(max_retries):
            try:
                if self._use_sdk:
                    content = self._structured_with_sdk(messages, schema_dict, current_temp)
                else:
                    content = self._structured_with_http(messages, schema_dict, current_temp, think=think)

                if not content:
                    raise GenerationError("Empty response from Ollama")

                return self._validate_response(content, schema)

            except ValidationError as e:
                last_error = e
                frappe.log_error(
                    "Ollama validation retry",
                    f"Attempt {attempt + 1}/{max_retries}: {e}"
                )
                # Increase temperature slightly for retry to get different output
                current_temp = min(current_temp + 0.1, 1.0)
                continue
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    frappe.log_error(
                        "Ollama generation retry",
                        f"Attempt {attempt + 1}/{max_retries}: {e}"
                    )
                    current_temp = min(current_temp + 0.1, 1.0)
                    continue
                break

        raise GenerationError(
            f"Ollama structured generation failed after {max_retries} attempts: {last_error}"
        )

    def _structured_with_sdk(
        self,
        messages: list,
        schema_dict: dict,
        temperature: float,
    ) -> str:
        """Generate structured response using Ollama SDK"""
        client = Client(host=self.base_url)
        response = client.chat(
            model=self.model,
            messages=messages,
            format=schema_dict,  # JSON schema for structured output
            options={
                "temperature": temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        )
        return response.message.content

    def _structured_with_http(
        self,
        messages: list,
        schema_dict: dict,
        temperature: float,
        think: bool | str = False,
    ) -> str:
        """
        Generate structured response using HTTP API with streaming.

        Uses streaming to bypass Cloudflare timeout while still
        enforcing JSON schema constraints.

        Args:
            think: Reasoning mode - False to disable, True to enable, or "low"/"medium"/"high" for GPT-OSS
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,  # Stream to avoid Cloudflare 524 timeout
            "format": schema_dict,  # Ollama 0.5+ JSON schema constraint
            "think": think,  # Enable/disable reasoning mode
            "options": {
                "temperature": temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }

        return self._make_streaming_request("/api/chat", payload)

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
    ) -> dict:
        """
        Generate JSON response without schema validation.
        Uses Ollama's basic JSON mode.
        """
        enhanced_system = system_prompt or ""
        enhanced_system += "\n\nYou MUST respond with valid JSON only. No explanations."

        messages = self._format_messages(prompt, enhanced_system)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",  # Basic JSON mode
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }

        try:
            response = self._make_request("/api/chat", payload)
            content = response.get("message", {}).get("content", "")
            return json.loads(self._extract_json_from_response(content))
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON from Ollama: {e}")
        except Exception as e:
            raise GenerationError(f"Ollama JSON generation failed: {e}")

    def _build_structured_system_prompt(
        self,
        base_prompt: str,
        schema_dict: dict
    ) -> str:
        """Build system prompt optimized for structured output"""
        simplified = self._simplify_schema_for_prompt(schema_dict)

        schema_instruction = f"""
You are a JSON generator. You MUST respond with valid JSON matching this structure:

{json.dumps(simplified, indent=2)}

CRITICAL RULES:
1. Output ONLY valid JSON - no explanations, no markdown, no code blocks
2. Use camelCase for CSS properties (backgroundColor, not background-color)
3. All strings must be properly escaped
4. Arrays must use proper JSON syntax
5. Include all required fields
6. Ensure the JSON is complete and not truncated
"""
        if base_prompt:
            return f"{base_prompt}\n\n{schema_instruction}"
        return schema_instruction

    def _simplify_schema_for_prompt(self, schema: dict) -> dict:
        """Simplify JSON schema for better LLM understanding"""
        keys_to_remove = ["$defs", "definitions", "description", "title", "default"]

        def clean(obj):
            if isinstance(obj, dict):
                return {
                    k: clean(v)
                    for k, v in obj.items()
                    if k not in keys_to_remove
                }
            elif isinstance(obj, list):
                return [clean(item) for item in obj]
            return obj

        return clean(schema)

    def _make_streaming_request(self, endpoint: str, payload: dict) -> str:
        """
        Make streaming HTTP request to Ollama API.

        Streams the response to bypass Cloudflare's 100s timeout.
        Assembles the full response from stream chunks.
        """
        import requests

        url = f"{self.base_url}{endpoint}"
        headers = self._get_auth_headers()

        ai_log("debug", "HTTP streaming request starting",
            url=url, model=payload.get("model"),
            num_ctx=payload.get("options", {}).get("num_ctx"),
            timeout=self.timeout)
        print(f"[OLLAMA] Streaming request to {url}, has_api_key={'X-API-Key' in headers}")

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            )

            ai_log("debug", "HTTP response received", status=response.status_code)
            print(f"[OLLAMA] Response status: {response.status_code}")

            if response.status_code != 200:
                error_text = response.text[:500]
                ai_log("error", "HTTP error response",
                    status=response.status_code, body=error_text[:200])
                print(f"[OLLAMA] Error response: {error_text[:200]}")
                raise GenerationError(
                    f"Ollama API error ({response.status_code}): {error_text}"
                )

            # Assemble content from stream chunks
            full_content = ""
            chunks_count = 0
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            full_content += chunk["message"]["content"]
                            chunks_count += 1
                        # Check if stream is done
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

            ai_log("info", "HTTP streaming completed",
                chunks_received=chunks_count, content_length=len(full_content))

            return full_content

        except requests.exceptions.ConnectionError as e:
            ai_log("error", "HTTP connection error", url=url, error=str(e))
            raise GenerationError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running (ollama serve)."
            )
        except requests.exceptions.Timeout:
            ai_log("error", "HTTP timeout", url=url, timeout=self.timeout)
            raise GenerationError(
                f"Ollama request timed out after {self.timeout}s. "
                "Try a smaller model or increase timeout."
            )
        except requests.exceptions.RequestException as e:
            ai_log("error", "HTTP request failed", url=url, error=str(e))
            raise GenerationError(f"Ollama request failed: {e}")

    def _make_request(self, endpoint: str, payload: dict) -> dict:
        """Make non-streaming HTTP request to Ollama API"""
        import requests

        url = f"{self.base_url}{endpoint}"
        headers = self._get_auth_headers()

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                raise GenerationError(
                    f"Ollama API error ({response.status_code}): {error_text}"
                )

            return response.json()

        except requests.exceptions.ConnectionError:
            raise GenerationError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running (ollama serve)."
            )
        except requests.exceptions.Timeout:
            raise GenerationError(
                f"Ollama request timed out after {self.timeout}s. "
                "Try a smaller model or increase timeout."
            )
        except requests.exceptions.RequestException as e:
            raise GenerationError(f"Ollama request failed: {e}")

    def pull_model(self, model: str = None) -> bool:
        """
        Pull/download a model from Ollama registry.

        Args:
            model: Model name to pull (defaults to configured model)

        Returns:
            bool: True if successful
        """
        model_to_pull = model or self.model

        if self._use_sdk:
            try:
                client = Client(host=self.base_url)
                client.pull(model_to_pull)
                return True
            except Exception as e:
                frappe.log_error("Ollama pull error", str(e))
                return False

        # HTTP fallback
        import requests
        headers = self._get_auth_headers()

        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_to_pull},
                headers=headers,
                timeout=600,  # Models can take a while to download
                stream=True,
            )

            if response.status_code != 200:
                return False

            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "error" in data:
                        frappe.log_error("Ollama pull error", data['error'])
                        return False

            return True

        except Exception as e:
            frappe.log_error("Ollama pull error", str(e))
            return False

    def list_models(self) -> list[dict]:
        """List available models on the Ollama server"""
        if self._use_sdk:
            try:
                client = Client(host=self.base_url)
                return client.list().get("models", [])
            except Exception:
                return []

        # HTTP fallback
        import requests
        headers = self._get_auth_headers()

        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("models", [])
            return []
        except Exception:
            return []

    def get_model_info(self, model: str = None) -> Optional[dict]:
        """Get information about a specific model"""
        model_name = model or self.model

        if self._use_sdk:
            try:
                client = Client(host=self.base_url)
                return client.show(model_name)
            except Exception:
                return None

        # HTTP fallback
        import requests
        headers = self._get_auth_headers()

        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None


# Recommended models for different tasks
OLLAMA_RECOMMENDED_MODELS = {
    "structured_output": {
        "best": "kimi-k2.5:cloud",
        "balanced": "qwen2.5:7b",
        "fast": "qwen2.5:3b",
        "description": "Kimi K2.5 excels at large structured output (256k context)"
    },
    "creative": {
        "best": "kimi-k2.5:cloud",
        "balanced": "llama3.2:8b",
        "description": "Kimi K2.5 offers great creativity with large context"
    },
    "code": {
        "best": "deepseek-coder:33b",
        "balanced": "deepseek-coder:6.7b",
        "fast": "deepseek-coder:1.3b",
        "description": "DeepSeek Coder for code/structure tasks"
    },
    "general": {
        "best": "kimi-k2.5:cloud",
        "balanced": "mistral:7b",
        "description": "Kimi K2.5 for general tasks with large context"
    },
}


__all__ = [
    "OllamaProvider",
    "OLLAMA_RECOMMENDED_MODELS",
    "OLLAMA_SDK_AVAILABLE",
]
