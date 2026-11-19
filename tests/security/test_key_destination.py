"""A visitor's key goes only to the provider's official API, never to an address from the host.

The Anthropic SDK reads an `ANTHROPIC_BASE_URL` environment variable when no address is
passed. If one were set on the host, every key would be sent there, so the factory pins
the address from `config.py`.
"""

from typing import Any

import anthropic
import httpx2
import pytest

from troubleshooter import config
from troubleshooter.llm import factory
from troubleshooter.llm.anthropic_client import AnthropicClient
from troubleshooter.llm.base import Provider

KEY = "sk-ant-destination-check"
ATTACKER = "https://keys.attacker.example"


def test_config_names_the_official_https_address() -> None:
    assert config.ANTHROPIC_BASE_URL == "https://api.anthropic.com"


def test_environment_variable_cannot_redirect_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", ATTACKER)

    client = factory.create_client(Provider.ANTHROPIC, KEY, config.MODELS["anthropic"].default)

    assert isinstance(client, AnthropicClient)
    assert str(client._sdk.base_url).rstrip("/") == config.ANTHROPIC_BASE_URL


def test_key_is_sent_only_to_the_official_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", ATTACKER)
    sent: list[httpx2.Request] = []
    real_sdk = anthropic.Anthropic

    def sdk_with_recording_network(**kwargs: Any) -> anthropic.Anthropic:
        def handler(request: httpx2.Request) -> httpx2.Response:
            sent.append(request)
            return httpx2.Response(401, json={"type": "error", "error": {"type": "x"}})

        return real_sdk(
            **kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
        )

    monkeypatch.setattr(anthropic, "Anthropic", sdk_with_recording_network)
    client = factory.create_client(Provider.ANTHROPIC, KEY, config.MODELS["anthropic"].default)

    with pytest.raises(Exception):  # noqa: B017 - only where the request went matters here
        client.complete_structured("system", "user", {"type": "object"}, 10)

    assert [(r.url.scheme, r.url.host) for r in sent] == [("https", "api.anthropic.com")]
