"""Builds a model client for a provider and key.

Every call builds a new client. A client holds a visitor's key, so it must never be cached
or shared between sessions.
"""

import anthropic

from troubleshooter import config
from troubleshooter.llm.anthropic_client import AnthropicClient
from troubleshooter.llm.base import LLMClient, Provider


def create_client(provider: Provider, api_key: str, model: str) -> LLMClient:
    """Return a new client for `model`, using the visitor's or the author's key.

    Args:
        provider: Which provider the key and model belong to.
        api_key: The key. Passing it explicitly stops the SDK from reading keys from
            environment variables.
        model: A model ID offered for `provider` in `config.MODELS`.

    Raises:
        ValueError: The key is empty, or the model isn't offered for the provider.
    """
    if not api_key.strip():
        raise ValueError("The API key is empty")
    if model not in config.MODELS[provider.value].all:
        raise ValueError(f"Model {model} is not offered for {provider.value}")
    match provider:
        case Provider.ANTHROPIC:
            sdk = anthropic.Anthropic(
                api_key=api_key,
                timeout=config.LLM_TIMEOUT_SECONDS,
                max_retries=config.LLM_MAX_RETRIES,
            )
            return AnthropicClient(sdk, model, config.LLM_EFFORT)
