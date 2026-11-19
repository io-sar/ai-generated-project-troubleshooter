import pytest

from troubleshooter import config
from troubleshooter.llm.anthropic_client import AnthropicClient
from troubleshooter.llm.base import Provider
from troubleshooter.llm.factory import create_client

KEY = "sk-ant-test-0000"


@pytest.mark.parametrize("model", config.MODELS["anthropic"].all)
def test_builds_an_anthropic_client_for_each_offered_model(model: str) -> None:
    client = create_client(Provider.ANTHROPIC, KEY, model)

    assert isinstance(client, AnthropicClient)


def test_sdk_uses_the_configured_timeout_and_retries() -> None:
    client = create_client(Provider.ANTHROPIC, KEY, config.MODELS["anthropic"].default)

    assert isinstance(client, AnthropicClient)
    sdk = client._sdk
    assert sdk.timeout == config.LLM_TIMEOUT_SECONDS
    assert sdk.max_retries == config.LLM_MAX_RETRIES
    assert sdk.api_key == KEY


@pytest.mark.parametrize("key", ["", "   "])
def test_empty_key_is_rejected(key: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        create_client(Provider.ANTHROPIC, key, config.MODELS["anthropic"].default)


@pytest.mark.parametrize("model", ["gpt-6-luna", "claude-not-in-the-list", ""])
def test_model_not_offered_is_rejected(model: str) -> None:
    with pytest.raises(ValueError, match="not offered"):
        create_client(Provider.ANTHROPIC, KEY, model)
