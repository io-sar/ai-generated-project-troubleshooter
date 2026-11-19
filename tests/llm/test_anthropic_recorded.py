"""Replays real Claude responses, recorded by scripts/record_llm_fixtures.py on 2026-11-19.

These check the adapter against the provider's actual format, which the built responses in
test_anthropic_client.py can only imitate. Never edit the fixture files by hand.
"""

import json
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from troubleshooter.domain.models import Diagnosis, Report
from troubleshooter.llm.anthropic_client import AnthropicClient
from troubleshooter.llm.errors import LLMError, LLMErrorKind

FIXTURES = Path(__file__).parent / "fixtures" / "anthropic"
SCHEMAS: dict[str, type[BaseModel]] = {
    "diagnosis-success": Diagnosis,
    "report-success-claude-haiku-5-5": Report,
}
FAILURES = {
    "report-truncated": LLMErrorKind.TRUNCATED,
    "invalid-key": LLMErrorKind.INVALID_KEY,
    "unknown-model": LLMErrorKind.MODEL_UNAVAILABLE,
}


def load(case: str) -> dict[str, Any]:
    fixture: dict[str, Any] = json.loads((FIXTURES / f"{case}.json").read_text(encoding="utf-8"))
    return fixture


def replay(case: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Send one call through the real SDK and adapter, answered by the recorded response."""
    fixture = load(case)
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(fixture["status"], json=fixture["body"])
    )
    sdk = anthropic.Anthropic(
        api_key="sk-ant-replay", max_retries=0, http_client=httpx2.Client(transport=transport)
    )
    client = AnthropicClient(sdk, fixture["model"], "medium")
    return client.complete_structured("system", "user", schema.model_json_schema(), 16_000)


def test_every_fixture_is_covered() -> None:
    recorded = {path.stem for path in FIXTURES.glob("*.json")}

    assert recorded == set(SCHEMAS) | set(FAILURES)


@pytest.mark.parametrize(("case", "schema"), SCHEMAS.items())
def test_recorded_answer_validates_against_its_model(case: str, schema: type[BaseModel]) -> None:
    answer = replay(case, schema)

    schema.model_validate(answer)


def test_recorded_answers_include_a_thinking_block_the_adapter_skips() -> None:
    blocks = [block["type"] for block in load("report-success-claude-haiku-5-5")["body"]["content"]]

    assert blocks == ["thinking", "text"]


@pytest.mark.parametrize(("case", "kind"), FAILURES.items())
def test_recorded_failure_maps_to_its_kind(case: str, kind: LLMErrorKind) -> None:
    with pytest.raises(LLMError) as caught:
        replay(case, Diagnosis)

    assert caught.value.kind is kind


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda path: path.stem)
def test_fixtures_hold_no_key(path: Path) -> None:
    assert "sk-ant-" not in path.read_text(encoding="utf-8")
