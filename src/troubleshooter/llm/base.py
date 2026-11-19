"""The interface every engine uses to call a model, whatever the provider."""

from enum import StrEnum
from typing import Any, Protocol


class Provider(StrEnum):
    """The model providers the app supports. The codes are the keys of `config.MODELS`."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LLMClient(Protocol):
    """One provider's model, ready to return structured output.

    Engines receive a client and never create one, so tests can pass a fake.
    """

    def complete_structured(
        self, system: str, user: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        """Return the model's answer as a JSON object shaped by `schema`.

        Args:
            system: The system prompt.
            user: The user message, with any untrusted text already wrapped in delimiters.
            schema: The JSON Schema of the expected answer, as Pydantic generates it. The
                client adapts it to what its provider supports.
            max_tokens: The most tokens the model may produce, set per stage in `config.py`.

        Returns:
            The parsed JSON object. The caller validates it against its Pydantic model.

        Raises:
            LLMError: The call failed. Its `kind` says why.
            InvalidOutputError: The answer wasn't a JSON object. The caller treats it like
                output that fails validation.
        """
        ...
