"""Typed model-call failures, so no provider error text reaches the caller.

Adapters raise `LLMError` with `from None`. The provider's own exception can contain the
key or the request, so it is never attached as the cause.
"""

from enum import StrEnum


class LLMErrorKind(StrEnum):
    """Why a model call failed. The UI shows a translated message for each code."""

    INVALID_KEY = "invalid_key"
    WRONG_PROVIDER_KEY = "wrong_provider_key"
    NO_CREDIT = "no_credit"
    RATE_LIMITED = "rate_limited"
    MODEL_UNAVAILABLE = "model_unavailable"
    TIMEOUT = "timeout"
    REFUSAL = "refusal"
    TRUNCATED = "truncated"
    # A provider outage or a lost connection, after the SDK's own retries.
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class LLMError(Exception):
    """A model call failed for the reason in `kind`.

    The message is the code alone, so logs and tracebacks never carry provider text.
    """

    def __init__(self, kind: LLMErrorKind) -> None:
        """Record why the call failed."""
        # The kind itself is the only argument, so a copied or unpickled error rebuilds
        # with the same kind. As a StrEnum it prints as the bare code.
        super().__init__(kind)
        self.kind = kind
