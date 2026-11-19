"""Anthropic adapter tests. Responses go through the real SDK over a mock transport.

The responses here are built in the documented API shape, so every case is covered,
including those that can't be triggered on demand (refusals, rate limits, outages).
"""

import json
import logging
import traceback
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import pytest

from troubleshooter.llm.anthropic_client import AnthropicClient, error_kind
from troubleshooter.llm.errors import InvalidOutputError, LLMError, LLMErrorKind

KEY = "sk-ant-test-0000"
MODEL = "claude-haiku-5-5"
SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5}},
    "required": ["score"],
    "additionalProperties": False,
}
# Planted in prompts and provider messages: it must never reach logs or errors.
CANARY = "canary-7f3a"

Handler = Callable[[httpx2.Request], httpx2.Response]


def make_client(handler: Handler, key: str = KEY) -> AnthropicClient:
    sdk = anthropic.Anthropic(
        api_key=key,
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicClient(sdk, MODEL, "medium")


def message(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_built",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 120, "output_tokens": 40},
    }


def reply(status: int, body: dict[str, Any]) -> Handler:
    return lambda request: httpx2.Response(status, json=body)


def api_error(
    error_type: str, error_code: str | None = None, message: str = f"Provider says {CANARY}"
) -> dict[str, Any]:
    error: dict[str, Any] = {"type": error_type, "message": message}
    if error_code:
        error["details"] = {"error_code": error_code}
    return {"type": "error", "error": error, "request_id": "req_built"}


def call(client: AnthropicClient) -> dict[str, Any]:
    return client.complete_structured("system " + CANARY, "user " + CANARY, SCHEMA, 500)


def test_returns_the_parsed_answer() -> None:
    client = make_client(reply(200, message('{"score": 4}')))

    assert call(client) == {"score": 4}


def test_sends_the_model_limits_and_a_portable_schema() -> None:
    sent: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json=message('{"score": 4}'))

    call(make_client(handler))

    body = json.loads(sent[0].content)
    assert sent[0].headers["authorization"] == f"Bearer {KEY}"
    assert body["model"] == MODEL
    assert body["max_tokens"] == 500
    assert body["system"] == "system " + CANARY
    assert body["messages"] == [{"role": "user", "content": "user " + CANARY}]
    assert body["output_config"]["effort"] == "medium"
    score = body["output_config"]["format"]["schema"]["properties"]["score"]
    assert "minimum" not in score
    assert "minimum 1" in score["description"]
    # Forced tool use and sampling parameters are rejected by current models.
    assert {"tool_choice", "tools", "temperature", "thinking"}.isdisjoint(body)


def test_joins_text_blocks_and_skips_thinking_blocks() -> None:
    body = message('{"score":')
    body["content"] = [
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": '{"score":'},
        {"type": "text", "text": " 2}"},
    ]

    assert call(make_client(reply(200, body))) == {"score": 2}


@pytest.mark.parametrize(
    ("stop_reason", "kind"),
    [("refusal", LLMErrorKind.REFUSAL), ("max_tokens", LLMErrorKind.TRUNCATED)],
)
def test_unfinished_answer_raises_its_kind(stop_reason: str, kind: LLMErrorKind) -> None:
    client = make_client(reply(200, message('{"sco', stop_reason)))

    with pytest.raises(LLMError) as caught:
        call(client)

    assert caught.value.kind is kind


@pytest.mark.parametrize("text", ["not json " + CANARY, "[1, 2]", ""])
def test_answer_that_is_not_a_json_object_is_invalid_output(text: str) -> None:
    client = make_client(reply(200, message(text)))

    with pytest.raises(InvalidOutputError) as caught:
        call(client)

    assert CANARY not in str(caught.value)


@pytest.mark.parametrize(
    ("status", "error_type", "error_code", "kind"),
    [
        (401, "authentication_error", None, LLMErrorKind.INVALID_KEY),
        (402, "billing_error", None, LLMErrorKind.NO_CREDIT),
        (429, "rate_limit_error", "enforced_spend_limit_reached", LLMErrorKind.NO_CREDIT),
        (429, "rate_limit_error", "contract_spend_limit_reached", LLMErrorKind.NO_CREDIT),
        (429, "rate_limit_error", None, LLMErrorKind.RATE_LIMITED),
        (429, "rate_limit_error", "ramp_limit_exceeded", LLMErrorKind.RATE_LIMITED),
        (403, "permission_error", None, LLMErrorKind.MODEL_UNAVAILABLE),
        (404, "not_found_error", None, LLMErrorKind.MODEL_UNAVAILABLE),
        (408, "timeout_error", None, LLMErrorKind.TIMEOUT),
        (504, "timeout_error", None, LLMErrorKind.TIMEOUT),
        (500, "api_error", None, LLMErrorKind.PROVIDER_UNAVAILABLE),
        (503, "api_error", None, LLMErrorKind.PROVIDER_UNAVAILABLE),
        (529, "overloaded_error", None, LLMErrorKind.PROVIDER_UNAVAILABLE),
        (400, "invalid_request_error", None, LLMErrorKind.REQUEST_REJECTED),
        (413, "request_too_large", None, LLMErrorKind.REQUEST_REJECTED),
        (422, "invalid_request_error", None, LLMErrorKind.REQUEST_REJECTED),
    ],
)
def test_provider_error_maps_to_its_kind(
    status: int, error_type: str, error_code: str | None, kind: LLMErrorKind
) -> None:
    client = make_client(reply(status, api_error(error_type, error_code)))

    with pytest.raises(LLMError) as caught:
        call(client)

    assert caught.value.kind is kind


@pytest.mark.parametrize(
    "message",
    [
        # The texts the rate-limits docs give for a limit the key's owner set themselves.
        "You have reached your specified API usage limits. You will regain access on ...",
        "You have reached your specified workspace API usage limits. You will regain ...",
        "Your credit balance is too low to access the Anthropic API.",
    ],
)
def test_400_for_spend_limit_or_low_credit_means_no_credit(message: str) -> None:
    client = make_client(reply(400, api_error("invalid_request_error", message=message)))

    with pytest.raises(LLMError) as caught:
        call(client)

    assert caught.value.kind is LLMErrorKind.NO_CREDIT


def test_other_400s_stay_request_rejected() -> None:
    body = api_error("invalid_request_error", message="max_tokens: must be at least 1")
    client = make_client(reply(400, body))

    with pytest.raises(LLMError) as caught:
        call(client)

    assert caught.value.kind is LLMErrorKind.REQUEST_REJECTED


def test_401_for_a_key_from_another_provider_says_so() -> None:
    client = make_client(reply(401, api_error("authentication_error")), key="sk-proj-abc")

    with pytest.raises(LLMError) as caught:
        call(client)

    assert caught.value.kind is LLMErrorKind.WRONG_PROVIDER_KEY


@pytest.mark.parametrize(
    ("raised", "kind"),
    [
        (httpx2.ReadTimeout("read timed out"), LLMErrorKind.TIMEOUT),
        (httpx2.ConnectError("connection refused"), LLMErrorKind.PROVIDER_UNAVAILABLE),
    ],
)
def test_network_failure_maps_to_its_kind(raised: Exception, kind: LLMErrorKind) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise raised

    with pytest.raises(LLMError) as caught:
        call(make_client(handler))

    assert caught.value.kind is kind


def test_error_carries_no_provider_text_or_key() -> None:
    client = make_client(reply(401, api_error("authentication_error")))

    with pytest.raises(LLMError) as caught:
        call(client)

    printed = "".join(traceback.format_exception(caught.value))
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert CANARY not in printed
    assert KEY not in printed


def test_unknown_sdk_error_counts_as_provider_unavailable() -> None:
    assert error_kind(anthropic.AnthropicError("odd"), KEY) is LLMErrorKind.PROVIDER_UNAVAILABLE


def test_logs_metadata_only(caplog: pytest.LogCaptureFixture) -> None:
    client = make_client(reply(200, message('{"score": 4} ' + CANARY)))
    caplog.set_level(logging.INFO, logger="troubleshooter.llm.anthropic_client")

    with pytest.raises(InvalidOutputError):
        call(client)

    logged = caplog.text
    assert "provider=anthropic" in logged
    assert f"model={MODEL}" in logged
    assert "input_tokens=120 output_tokens=40" in logged
    assert "outcome=end_turn" in logged
    assert CANARY not in logged
    assert KEY not in logged


def test_logs_the_error_kind_when_a_call_fails(caplog: pytest.LogCaptureFixture) -> None:
    client = make_client(reply(429, api_error("rate_limit_error")))
    caplog.set_level(logging.INFO, logger="troubleshooter.llm.anthropic_client")

    with pytest.raises(LLMError):
        call(client)

    assert "outcome=rate_limited" in caplog.text
    assert CANARY not in caplog.text
