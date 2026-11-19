from typing import Any

from troubleshooter import config
from troubleshooter.llm.base import LLMClient, Provider


class FakeClient:
    """Returns a fixed answer. Typing it as `LLMClient` below makes mypy check the protocol."""

    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def complete_structured(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((system, user, schema))
        return self.answer


def test_provider_codes_are_stable() -> None:
    assert [provider.value for provider in Provider] == ["anthropic", "openai"]


def test_every_provider_has_models_in_config_and_no_more() -> None:
    assert set(config.MODELS) == {provider.value for provider in Provider}


def test_a_fake_client_meets_the_protocol() -> None:
    fake = FakeClient({"ok": True})
    client: LLMClient = fake

    answer = client.complete_structured("system", "user", {"type": "object"})

    assert answer == {"ok": True}
    assert fake.calls == [("system", "user", {"type": "object"})]
