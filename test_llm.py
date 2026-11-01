import json
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

import pytest

from core.llm import (
    GeminiChatClient,
    LLMConfig,
    LLMConfigurationError,
    create_chat_client,
)


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self._payload


class _ReadTimeoutResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        raise TimeoutError("response read timed out")


class _FailingErrorBody:
    def read(self):
        raise ConnectionError("error response read failed")

    def close(self):
        return None


def test_llm_config_defaults_to_local_ollama():
    config = LLMConfig.from_env({})

    assert config.provider == "local"
    assert config.model_name == "qwen2.5-coder:7b"
    assert create_chat_client(config) is None


def test_llm_config_rejects_unknown_provider():
    with pytest.raises(LLMConfigurationError, match="LLM_PROVIDER"):
        LLMConfig.from_env({"LLM_PROVIDER": "unknown"})


def test_gemini_client_maps_messages_and_response_to_translator_contract():
    client = GeminiChatClient("test-key", timeout_seconds=7)
    response_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": '{"sql":"SELECT 1"}'}],
                }
            }
        ]
    }

    with patch("core.llm.urlopen", return_value=_Response(response_payload)) as request:
        result = client(
            model="gemini-test",
            messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Question"},
                {"role": "assistant", "content": '{"sql":"SELECT 0"}'},
            ],
        )

    sent_request = request.call_args.args[0]
    sent_payload = json.loads(sent_request.data.decode("utf-8"))
    assert sent_request.full_url.endswith("/gemini-test:generateContent")
    assert sent_request.get_header("X-goog-api-key") == "test-key"
    assert sent_payload["systemInstruction"] == {
        "parts": [{"text": "System prompt"}]
    }
    assert sent_payload["contents"] == [
        {"role": "user", "parts": [{"text": "Question"}]},
        {"role": "model", "parts": [{"text": '{"sql":"SELECT 0"}'}]},
    ]
    assert result == {"message": {"content": '{"sql":"SELECT 1"}'}}
    assert request.call_args.kwargs["timeout"] == 7


def test_gemini_client_retries_transient_503_with_backoff():
    client = GeminiChatClient("test-key", max_retries=1)
    transient_error = HTTPError(
        "https://example.test",
        503,
        "Unavailable",
        {},
        BytesIO(b'{"error":{"message":"busy"}}'),
    )
    response = _Response(
        {
            "candidates": [
                {"content": {"parts": [{"text": '{"sql":"SELECT 1"}'}]}}
            ]
        }
    )

    with patch(
        "core.llm.urlopen",
        side_effect=[transient_error, response],
    ) as request:
        with patch("core.llm.random.uniform", return_value=0):
            with patch("core.llm.time.sleep") as sleep:
                result = client(
                    model="gemini-test",
                    messages=[{"role": "user", "content": "Question"}],
                )

    assert result == {"message": {"content": '{"sql":"SELECT 1"}'}}
    assert request.call_count == 2
    sleep.assert_called_once_with(1)


def test_gemini_client_retries_timeout_during_response_read():
    client = GeminiChatClient("test-key", max_retries=1)
    response = _Response(
        {
            "candidates": [
                {"content": {"parts": [{"text": '{"sql":"SELECT 1"}'}]}}
            ]
        }
    )

    with patch(
        "core.llm.urlopen",
        side_effect=[_ReadTimeoutResponse(), response],
    ) as request:
        with patch("core.llm.random.uniform", return_value=0):
            with patch("core.llm.time.sleep") as sleep:
                result = client(
                    model="gemini-test",
                    messages=[{"role": "user", "content": "Question"}],
                )

    assert result == {"message": {"content": '{"sql":"SELECT 1"}'}}
    assert request.call_count == 2
    sleep.assert_called_once_with(1)


def test_gemini_client_retries_when_transient_error_body_read_fails():
    client = GeminiChatClient("test-key", max_retries=1)
    transient_error = HTTPError(
        "https://example.test",
        503,
        "Unavailable",
        {},
        _FailingErrorBody(),
    )
    response = _Response(
        {
            "candidates": [
                {"content": {"parts": [{"text": '{"sql":"SELECT 1"}'}]}}
            ]
        }
    )

    with patch(
        "core.llm.urlopen",
        side_effect=[transient_error, response],
    ) as request:
        with patch("core.llm.random.uniform", return_value=0):
            with patch("core.llm.time.sleep") as sleep:
                result = client(
                    model="gemini-test",
                    messages=[{"role": "user", "content": "Question"}],
                )

    assert result == {"message": {"content": '{"sql":"SELECT 1"}'}}
    assert request.call_count == 2
    sleep.assert_called_once_with(1)


def test_translator_can_use_a_non_ollama_client():
    from core.translator import Translator

    client = lambda **_kwargs: {
        "message": {"content": '{"sql":"SELECT 1"}'}
    }
    translator = Translator(
        system_prompt="prompt",
        model_name="gemini-test",
        chat_client=client,
    )

    assert translator.translate_to_sql("Quantos registros?")["sql"] == "SELECT 1"
