"""Local Ollama-compatible inference adapter."""

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMError(RuntimeError):
    """Base class for local inference failures."""


class LLMUnavailable(LLMError):
    """The local model endpoint cannot be reached or timed out."""


class LLMResponseError(LLMError):
    """The local model returned an invalid or unusable response."""


class OllamaClient:
    """Minimal Ollama `/api/generate` client using only Python's standard library."""

    def __init__(
        self, base_url: str, model: str, timeout_seconds: float = 30.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_json(self, prompt: str) -> Mapping[str, object]:
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "format": "json", "stream": False}
        ).encode()
        request = Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, URLError, HTTPError, OSError) as exc:
            raise LLMUnavailable(f"Local LLM is unavailable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMResponseError("Local LLM returned invalid HTTP JSON.") from exc
        generated = body.get("response") if isinstance(body, dict) else None
        if not isinstance(generated, str):
            raise LLMResponseError(
                "Local LLM response did not contain a text response."
            )
        try:
            parsed = json.loads(generated)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                "Local LLM returned malformed candidate JSON."
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError("Local LLM JSON must be an object.")
        return parsed
