import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class LLMConfigurationError(ValueError):
    """Raised when the selected language-model provider is not configured."""


def _non_negative_integer(
    environ: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    value = environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise LLMConfigurationError(f"{name} must be an integer.") from exc
    if parsed < 0:
        raise LLMConfigurationError(f"{name} must not be negative.")
    return parsed


@dataclass(frozen=True)
class LLMConfig:
    """Runtime configuration used by the API LLM integration."""

    provider: str = "local"
    ollama_model: str = "qwen2.5-coder:7b"
    gemini_model: str = "gemini-flash-latest"
    gemini_api_key: Optional[str] = field(default=None, repr=False)
    request_timeout_seconds: int = 120
    gemini_max_retries: int = 2

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
        gemini_max_retries = _non_negative_integer(
            environ,
            "GEMINI_MAX_RETRIES",
            2,
        )

        return cls(
            provider=provider,
            ollama_model=ollama_model,
            gemini_model=gemini_model,
            gemini_api_key=gemini_api_key,
            gemini_max_retries=gemini_max_retries,
        )


class GeminiChatClient:
    """Small REST client that adapts Gemini responses to the Ollama shape."""

    _retryable_statuses = frozenset({408, 429, 500, 502, 503, 504})
    _endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent"
    )

    def __init__(
        self,
        api_key: str,
        timeout_seconds: int = 120,
        max_retries: int = 2,
    ):
        if not api_key.strip():
            raise LLMConfigurationError("GEMINI_API_KEY must not be empty.")
        if max_retries < 0:
            raise LLMConfigurationError("GEMINI_MAX_RETRIES must not be negative.")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

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

        request_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        body = ""
        for attempt in range(self._max_retries + 1):
            request = Request(
                self._endpoint.format(model=quote(model, safe="")),
                data=request_data,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": self._api_key,
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                break
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace").strip()
                if (
                    exc.code not in self._retryable_statuses
                    or attempt >= self._max_retries
                ):
                    raise RuntimeError(
                        f"Gemini request failed with HTTP "
                        f"{exc.code}: {detail or exc.reason}"
                    ) from exc
                self._wait_before_retry(attempt, exc.code)
            except (URLError, TimeoutError, ConnectionError) as exc:
                if attempt >= self._max_retries:
                    reason = getattr(exc, "reason", str(exc))
                    raise RuntimeError(
                        f"Gemini request failed: {reason}"
                    ) from exc
                self._wait_before_retry(attempt, "network")

        if not body:
            raise RuntimeError("Gemini returned an empty response.")

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

    @staticmethod
    def _wait_before_retry(attempt: int, failure: object) -> None:
        delay = (2**attempt) + random.uniform(0, 0.25)
        logger.warning(
            "Gemini request temporarily unavailable failure=%s attempt=%s "
            "retry_in_seconds=%.2f",
            failure,
            attempt + 1,
            delay,
        )
        time.sleep(delay)


def create_chat_client(config: LLMConfig):
    """Create the configured cloud client, or keep the native Ollama path."""

    if config.provider == "google":
        return GeminiChatClient(
            config.gemini_api_key or "",
            timeout_seconds=config.request_timeout_seconds,
            max_retries=config.gemini_max_retries,
        )
    return None
