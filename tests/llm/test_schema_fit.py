"""Checks that the schemas sent to the LLM fit both providers' structured output.

The rules below come from the providers' docs, checked on 2026-11-12:
- Claude: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- OpenAI: https://developers.openai.com/api/docs/guides/structured-outputs ("Supported schemas")
If a provider changes its rules, update them here and say so in the commit.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel

from troubleshooter.domain.models import Diagnosis, Report
from troubleshooter.llm.schema import portable_schema

# Stage 1 returns a Diagnosis and stage 2 a Report. Nothing else goes to the LLM as a schema.
LLM_OUTPUT_MODELS: list[type[BaseModel]] = [Diagnosis, Report]

# Keywords both providers accept. Anything else in a schema fails the test.
ALLOWED_KEYWORDS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "$ref",
    "$defs",
    "anyOf",
    "title",
    "description",
    "minItems",
}
CLAUDE_MAX_MIN_ITEMS = 1
CLAUDE_MAX_OPTIONAL_PARAMETERS = 24
CLAUDE_MAX_UNION_PARAMETERS = 16
OPENAI_MAX_PROPERTIES = 5000
OPENAI_MAX_NESTING = 10
OPENAI_MAX_ENUM_VALUES = 1000
OPENAI_MAX_NAME_CHARS = 120_000


def schemas(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every subschema in `node`, including `node` itself."""
    yield node
    for name in ("properties", "$defs"):
        for sub in node.get(name, {}).values():
            yield from schemas(sub)
    if "items" in node:
        yield from schemas(node["items"])
    for sub in node.get("anyOf", []):
        yield from schemas(sub)


def resolve(root: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        target: dict[str, Any] = root["$defs"][node["$ref"].removeprefix("#/$defs/")]
        return target
    return node


def depth(root: dict[str, Any], node: dict[str, Any], seen: frozenset[str] = frozenset()) -> int:
    """Levels of object nesting below `node`, following references. Fails on recursion."""
    ref = node.get("$ref")
    if ref is not None:
        assert ref not in seen, f"recursive schema through {ref}"
        seen = seen | {ref}
    node = resolve(root, node)
    children = list(node.get("properties", {}).values())
    children += [node["items"]] if "items" in node else []
    children += node.get("anyOf", [])
    below = max((depth(root, child, seen) for child in children), default=0)
    return below + (1 if node.get("type") == "object" else 0)


@pytest.fixture(params=LLM_OUTPUT_MODELS, ids=lambda model: model.__name__)
def schema(request: pytest.FixtureRequest) -> dict[str, Any]:
    model: type[BaseModel] = request.param
    return portable_schema(model.model_json_schema())


def test_root_is_an_object_without_any_of(schema: dict[str, Any]) -> None:
    assert schema["type"] == "object"
    assert "anyOf" not in schema


def test_only_supported_keywords_are_used(schema: dict[str, Any]) -> None:
    used = {keyword for node in schemas(schema) for keyword in node}

    assert used <= ALLOWED_KEYWORDS, f"unsupported: {used - ALLOWED_KEYWORDS}"


def test_every_object_is_closed_and_requires_all_its_fields(schema: dict[str, Any]) -> None:
    for node in schemas(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


def test_min_items_is_at_most_1(schema: dict[str, Any]) -> None:
    for node in schemas(schema):
        assert node.get("minItems", 0) <= CLAUDE_MAX_MIN_ITEMS


def test_references_are_local_and_not_recursive(schema: dict[str, Any]) -> None:
    for node in schemas(schema):
        if "$ref" in node:
            assert node["$ref"].startswith("#/$defs/")

    assert depth(schema, schema) <= OPENAI_MAX_NESTING


def test_size_is_within_both_providers_limits(schema: dict[str, Any]) -> None:
    nodes = list(schemas(schema))
    properties = [name for node in nodes for name in node.get("properties", {})]
    enum_values = [str(value) for node in nodes for value in node.get("enum", [])]
    names = properties + list(schema.get("$defs", {})) + enum_values
    optional = [
        name
        for node in nodes
        for name in node.get("properties", {})
        if name not in node.get("required", [])
    ]
    unions = [node for node in nodes if "anyOf" in node or isinstance(node.get("type"), list)]

    assert len(properties) <= OPENAI_MAX_PROPERTIES
    assert len(enum_values) <= OPENAI_MAX_ENUM_VALUES
    assert sum(len(name) for name in names) <= OPENAI_MAX_NAME_CHARS
    assert len(optional) <= CLAUDE_MAX_OPTIONAL_PARAMETERS
    assert len(unions) <= CLAUDE_MAX_UNION_PARAMETERS


def test_moved_limits_still_reach_the_model() -> None:
    risk = portable_schema(Report.model_json_schema())["$defs"]["Risk"]

    assert "minimum 1, maximum 5" in risk["properties"]["likelihood"]["description"]


def test_raw_schema_would_not_fit() -> None:
    # Guards the converter's purpose: without it, Claude rejects the schema.
    raw = Report.model_json_schema()
    used = {keyword for node in schemas(raw) for keyword in node}

    assert {"minimum", "maximum", "minLength", "maxItems"} <= used
