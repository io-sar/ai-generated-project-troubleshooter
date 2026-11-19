import pickle
import traceback

import pytest

from troubleshooter.llm.errors import LLMError, LLMErrorKind

# Codes are stored and translated in the UI, so they must not change.
EXPECTED_KINDS = [
    "invalid_key",
    "wrong_provider_key",
    "no_credit",
    "rate_limited",
    "model_unavailable",
    "timeout",
    "refusal",
    "truncated",
    "provider_unavailable",
]


def test_error_kinds_are_stable() -> None:
    assert [kind.value for kind in LLMErrorKind] == EXPECTED_KINDS


@pytest.mark.parametrize("kind", list(LLMErrorKind))
def test_error_carries_its_kind(kind: LLMErrorKind) -> None:
    error = LLMError(kind)

    assert error.kind is kind
    assert str(error) == kind.value
    assert repr(error) == f"LLMError({kind!r})"


def test_error_raised_from_none_drops_the_provider_exception() -> None:
    provider_text = "sk-canary-0000 rejected for request body ..."

    with pytest.raises(LLMError) as caught:
        try:
            raise RuntimeError(provider_text)
        except RuntimeError:
            raise LLMError(LLMErrorKind.INVALID_KEY) from None

    printed = "".join(traceback.format_exception(caught.value))
    assert caught.value.__cause__ is None
    assert provider_text not in printed


def test_error_is_an_exception_callers_can_catch_broadly() -> None:
    with pytest.raises(Exception, match="timeout"):
        raise LLMError(LLMErrorKind.TIMEOUT)


def test_error_survives_pickling_with_its_kind() -> None:
    # Streamlit and pytest may copy exceptions between processes or reruns.
    copy = pickle.loads(pickle.dumps(LLMError(LLMErrorKind.REFUSAL)))  # noqa: S301

    assert copy.kind is LLMErrorKind.REFUSAL
