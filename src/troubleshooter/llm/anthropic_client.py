"""Claude through the Anthropic SDK, behind the `LLMClient` protocol."""

import json
import logging
import time
from typing import Any, Literal

import anthropic
from anthropic.types import Message, MessageParam, OutputConfigParam

from troubleshooter.llm.errors import InvalidOutputError, LLMError, LLMErrorKind
from troubleshooter.llm.schema import portable_schema

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"
# Every Anthropic API key starts with this. A 401 for a key without it most likely means
# the visitor pasted another provider's key.
KEY_PREFIX = "sk-ant-"
# A spend limit the key's owner set, or an empty balance, comes back as a plain 400 with no
# error code, so its documented message text is the only signal.
OUT_OF_CREDIT_MESSAGES = ("You have reached your specified", "credit balance is too low")

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class AnthropicClient:
    """Returns structured output from one Claude model. Implements `LLMClient`."""

    def __init__(self, sdk: anthropic.Anthropic, model: str, effort: Effort) -> None:
        """Wrap an SDK client.

        Args:
            sdk: The Anthropic SDK client, already holding the key, timeout and retries.
            model: The model ID, from `config.MODELS`.
            effort: How much the model reasons before answering, from `config.LLM_EFFORT`.
        """
        self._sdk = sdk
        self._model = model
        self._effort = effort

    def complete_structured(
        self, system: str, user: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        """Return Claude's answer as a JSON object. See `LLMClient.complete_structured`."""
        messages: list[MessageParam] = [{"role": "user", "content": user}]
        output_config: OutputConfigParam = {
            "effort": self._effort,
            "format": {"type": "json_schema", "schema": portable_schema(schema)},
        }
        started = time.monotonic()
        try:
            message = self._sdk.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_config=output_config,
            )
        except anthropic.AnthropicError as error:
            kind = error_kind(error, self._sdk.api_key)
            self._log(started, kind.value)
            raise LLMError(kind) from None
        self._log(started, message.stop_reason or "unknown", message)
        return _answer(message)

    def _log(self, started: float, outcome: str, message: Message | None = None) -> None:
        # Metadata only: never the key, the prompt or the answer.
        usage = message.usage if message else None
        logger.info(
            "model call provider=%s model=%s latency_ms=%d input_tokens=%s "
            "output_tokens=%s outcome=%s",
            PROVIDER,
            self._model,
            (time.monotonic() - started) * 1000,
            usage.input_tokens if usage else "-",
            usage.output_tokens if usage else "-",
            outcome,
        )


def _answer(message: Message) -> dict[str, Any]:
    """Return the JSON object in a finished message, or raise why there is none."""
    if message.stop_reason == "refusal":
        raise LLMError(LLMErrorKind.REFUSAL)
    if message.stop_reason == "max_tokens":
        raise LLMError(LLMErrorKind.TRUNCATED)
    text = "".join(block.text for block in message.content if block.type == "text")
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        raise InvalidOutputError("The answer is not valid JSON") from None
    if not isinstance(answer, dict):
        raise InvalidOutputError("The answer is not a JSON object")
    return answer


def _is_out_of_credit(error: anthropic.BadRequestError) -> bool:
    body = error.body if isinstance(error.body, dict) else {}
    details = body.get("error")
    message = details.get("message") if isinstance(details, dict) else None
    return isinstance(message, str) and any(text in message for text in OUT_OF_CREDIT_MESSAGES)


def error_kind(error: anthropic.AnthropicError, api_key: str | None) -> LLMErrorKind:
    """Map an SDK error to the reason shown to the visitor.

    Specific SDK classes subclass general ones (a spend-limit 429 is a `RateLimitError`),
    so the most specific checks come first.
    """
    match error:
        case anthropic.AuthenticationError() | anthropic.OrganizationOnHoldError():
            looks_wrong = api_key is not None and not api_key.startswith(KEY_PREFIX)
            return LLMErrorKind.WRONG_PROVIDER_KEY if looks_wrong else LLMErrorKind.INVALID_KEY
        case (
            anthropic.PaymentRequiredError()
            | anthropic.EnforcedSpendLimitReachedError()
            | anthropic.ContractSpendLimitReachedError()
        ):
            return LLMErrorKind.NO_CREDIT
        case anthropic.RateLimitError():
            return LLMErrorKind.RATE_LIMITED
        case anthropic.PermissionDeniedError() | anthropic.NotFoundError():
            return LLMErrorKind.MODEL_UNAVAILABLE
        case (
            anthropic.APITimeoutError()
            | anthropic.RequestTimeoutError()
            | anthropic.GatewayTimeoutError()
            | anthropic.DeadlineExceededError()
        ):
            return LLMErrorKind.TIMEOUT
        case anthropic.InternalServerError() | anthropic.APIConnectionError():
            return LLMErrorKind.PROVIDER_UNAVAILABLE
        case anthropic.BadRequestError() if _is_out_of_credit(error):
            return LLMErrorKind.NO_CREDIT
        case anthropic.APIStatusError():
            return LLMErrorKind.REQUEST_REJECTED
        case _:
            return LLMErrorKind.PROVIDER_UNAVAILABLE
