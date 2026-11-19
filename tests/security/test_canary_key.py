"""A fake key must never appear in logs, errors, tracebacks or object reprs (SPEC section 10).

Each case goes through the real factory and adapter. Only the network is replaced, by a
mock transport, so the key travels the same path a visitor's key does.

Covered so far: the factory and the Anthropic adapter. The OpenAI adapter (#51), the engine
(#53) and session dumps (M6) join this file when they exist.
"""

import logging
import pickle
import traceback
from collections.abc import Callable, Iterator
from typing import Any

import anthropic
import httpx2
import pytest

from troubleshooter import config
from troubleshooter.llm import factory
from troubleshooter.llm.base import Provider
from troubleshooter.llm.errors import InvalidOutputError, LLMError
from troubleshooter.llm.logs import SDK_LOGGERS, quiet_sdk_loggers

CANARY_KEY = "sk-ant-canary-9f2c41d07b"
# Scenario text is never logged either, by the project or by the SDKs.
CANARY_SCENARIO = "scenario-canary-51e8"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}

Handler = Callable[[httpx2.Request], httpx2.Response]


def message(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_built",
        "type": "message",
        "role": "assistant",
        "model": config.MODELS["anthropic"].default,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def api_error(error_type: str, error_code: str | None = None) -> dict[str, Any]:
    # Providers sometimes quote part of the key back; this one quotes all of it.
    error: dict[str, Any] = {"type": error_type, "message": f"Key {CANARY_KEY} was refused"}
    if error_code:
        error["details"] = {"error_code": error_code}
    return {"type": "error", "error": error}


def respond(status: int, body: dict[str, Any]) -> Handler:
    return lambda request: httpx2.Response(status, json=body)


def fail_with(error: Exception) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise error

    return handler


CASES: dict[str, Handler] = {
    "success": respond(200, message('{"ok": true}')),
    "refusal": respond(200, message("", "refusal")),
    "truncated": respond(200, message('{"o', "max_tokens")),
    "invalid output": respond(200, message("not json")),
    "invalid key": respond(401, api_error("authentication_error")),
    "no credit": respond(402, api_error("billing_error")),
    "spend limit": respond(429, api_error("rate_limit_error", "enforced_spend_limit_reached")),
    "rate limited": respond(429, api_error("rate_limit_error")),
    "model unavailable": respond(404, api_error("not_found_error")),
    "request rejected": respond(400, api_error("invalid_request_error")),
    "provider error": respond(500, api_error("api_error")),
    "timeout": fail_with(httpx2.ReadTimeout(f"timed out for {CANARY_KEY}")),
    "connection lost": fail_with(httpx2.ConnectError(f"refused for {CANARY_KEY}")),
}


@pytest.fixture
def quiet_sdks() -> Iterator[None]:
    """Quiet the SDK loggers as the app and scripts do, then restore their levels."""
    loggers = [logging.getLogger(name) for name in SDK_LOGGERS]
    levels = [logger.level for logger in loggers]
    quiet_sdk_loggers()
    yield
    for logger, level in zip(loggers, levels, strict=True):
        logger.setLevel(level)


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> list[Handler]:
    """Replace the network under the real factory. Append a handler to choose the reply."""
    handlers: list[Handler] = []
    real_sdk = anthropic.Anthropic

    def sdk_with_mock_network(**kwargs: Any) -> anthropic.Anthropic:
        transport = httpx2.MockTransport(lambda request: handlers[-1](request))
        return real_sdk(**kwargs, http_client=httpx2.Client(transport=transport))

    # The factory looks the class up on the module at call time, so this reaches it.
    monkeypatch.setattr(anthropic, "Anthropic", sdk_with_mock_network)
    return handlers


def run(case: str, network: list[Handler]) -> BaseException | None:
    """Make one call through the factory. Return the error it raised, if any."""
    network.append(CASES[case])
    client = factory.create_client(
        Provider.ANTHROPIC, CANARY_KEY, config.MODELS["anthropic"].default
    )
    try:
        client.complete_structured("system", f"<scenario>{CANARY_SCENARIO}</scenario>", SCHEMA, 100)
    except (LLMError, InvalidOutputError) as error:
        return error
    return None


@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.usefixtures("quiet_sdks")
def test_key_and_scenario_never_reach_the_logs(
    case: str, network: list[Handler], caplog: pytest.LogCaptureFixture
) -> None:
    # The whole app at DEBUG: the most anyone could switch on.
    caplog.set_level(logging.DEBUG)

    run(case, network)

    assert caplog.records
    for canary in (CANARY_KEY, CANARY_SCENARIO):
        assert canary not in caplog.text
        assert all(canary not in str(record.args) for record in caplog.records)


def test_sdk_debug_logs_would_leak_without_quieting(
    network: list[Handler], caplog: pytest.LogCaptureFixture
) -> None:
    # Proves the test above can fail: the SDK logs the request body at DEBUG.
    caplog.set_level(logging.DEBUG)

    run("success", network)

    assert CANARY_SCENARIO in caplog.text


@pytest.mark.parametrize("case", [case for case in CASES if case != "success"])
def test_key_never_reaches_the_error(case: str, network: list[Handler]) -> None:
    error = run(case, network)

    assert error is not None
    shown = [
        str(error),
        repr(error),
        "".join(traceback.format_exception(error)),
        repr(pickle.loads(pickle.dumps(error))),  # noqa: S301 - our own object
    ]
    assert all(CANARY_KEY not in text for text in shown)


def test_key_never_reaches_the_client_repr(network: list[Handler]) -> None:
    client = factory.create_client(
        Provider.ANTHROPIC, CANARY_KEY, config.MODELS["anthropic"].default
    )

    assert CANARY_KEY not in repr(client)
    assert CANARY_KEY not in str(client)
    assert CANARY_KEY not in repr(vars(client))


def test_factory_errors_never_echo_the_key() -> None:
    with pytest.raises(ValueError) as caught:
        factory.create_client(Provider.ANTHROPIC, CANARY_KEY, "not-an-offered-model")

    assert CANARY_KEY not in "".join(traceback.format_exception(caught.value))
