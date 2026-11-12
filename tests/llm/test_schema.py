from typing import Any

from troubleshooter.llm.schema import portable_schema


def test_limits_move_into_a_new_description() -> None:
    schema = {"type": "integer", "minimum": 1, "maximum": 5}

    assert portable_schema(schema) == {
        "type": "integer",
        "description": "Limits: minimum 1, maximum 5.",
    }


def test_limits_are_added_after_an_existing_description() -> None:
    schema = {"type": "string", "description": "Who owns it.", "minLength": 1}

    assert portable_schema(schema)["description"] == "Who owns it. Limits: minLength 1."


def test_min_items_of_0_or_1_is_kept() -> None:
    for min_items in (0, 1):
        assert portable_schema({"type": "array", "minItems": min_items}) == {
            "type": "array",
            "minItems": min_items,
        }


def test_min_items_above_1_and_max_items_move() -> None:
    schema = {"type": "array", "minItems": 2, "maxItems": 4}

    assert portable_schema(schema) == {
        "type": "array",
        "description": "Limits: minItems 2, maxItems 4.",
    }


def test_nested_properties_items_and_defs_are_converted() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "string", "maxLength": 9}}},
        "$defs": {"Score": {"type": "integer", "maximum": 100}},
    }

    converted = portable_schema(schema)

    assert converted["properties"]["tags"]["items"] == {
        "type": "string",
        "description": "Limits: maxLength 9.",
    }
    assert converted["$defs"]["Score"] == {"type": "integer", "description": "Limits: maximum 100."}


def test_field_named_like_a_keyword_is_kept() -> None:
    schema = {"type": "object", "properties": {"maximum": {"type": "integer"}}}

    assert portable_schema(schema) == schema


def test_input_schema_is_not_changed() -> None:
    schema = {"type": "integer", "minimum": 1}

    portable_schema(schema)

    assert schema == {"type": "integer", "minimum": 1}
