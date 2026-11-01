import json
import os
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv


class LLMConfigurationError(ValueError):
    """Raised when the selected language-model provider is not configured."""


@dataclass(frozen=True)
class LLMConfig:
    """Runtime configuration used by the API LLM integration."""

    provider: str = "local"
    ollama_model: str = "qwen2.5-coder:7b"
    gemini_model: str = "gemini-flash-latest"
    gemini_api_key: Optional[str] = field(default=None, repr=False)
    request_timeout_seconds: int = 120

    @property
    def model_name(self) -> str:
        return (
            self.gemini_model
            if self.provider == "google"
            else self.ollama_model
        )

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
    ) -> "LLMConfig":
        if environ is None:
            load_dotenv()
            environ = os.environ

        provider = environ.get("LLM_PROVIDER", "local").strip().lower()
        if provider not in {"local", "google"}:
            raise LLMConfigurationError(
                "LLM_PROVIDER must be either 'local' or 'google'."
            )

        ollama_model = environ.get("OLLAMA_MODEL", cls.ollama_model).strip()
        gemini_model = environ.get("GEMINI_MODEL", cls.gemini_model).strip()
        if not ollama_model:
            raise LLMConfigurationError("OLLAMA_MODEL must be configured.")
        if not gemini_model:
            raise LLMConfigurationError("GEMINI_MODEL must be configured.")

        gemini_api_key = environ.get("GEMINI_API_KEY", "").strip() or None
        if provider == "google" and not gemini_api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY must be configured when LLM_PROVIDER is 'google'."
            )

        return cls(
            provider=provider,
            ollama_model=ollama_model,
            gemini_model=gemini_model,
            gemini_api_key=gemini_api_key,
        )


class GeminiChatClient:
    """Small REST client that adapts Gemini responses to the Ollama shape."""

    _endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent"
    )

    def __init__(self, api_key: str, timeout_seconds: int = 120):
        if not api_key.strip():
            raise LLMConfigurationError("GEMINI_API_KEY must not be empty.")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def __call__(
        self,
        *,
        model: str,
        messages: Sequence[Mapping[str, str]],
    ) -> dict:
        system_parts = [
            {"text": message["content"]}
            for message in messages
            if message.get("role") == "system"
        ]
        contents = [
            {
                "role": "model" if message.get("role") == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
            if message.get("role") != "system"
        ]
        payload = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        request = Request(
            self._endpoint.format(model=quote(model, safe="")),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": self._api_key,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Gemini request failed with HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Gemini request failed: {exc.reason}") from exc

        try:
            response_payload = json.loads(body)
            candidates = response_payload["candidates"]
            parts = candidates[0]["content"]["parts"]
            text = "".join(part["text"] for part in parts if "text" in part)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gemini returned an invalid response.") from exc

        if not text.strip():
            raise RuntimeError("Gemini returned an empty response.")
        return {"message": {"content": text}}


def create_chat_client(config: LLMConfig):
    """Create the configured cloud client, or keep the native Ollama path."""

    if config.provider == "google":
        return GeminiChatClient(
            config.gemini_api_key or "",
            timeout_seconds=config.request_timeout_seconds,
        )
    return None
