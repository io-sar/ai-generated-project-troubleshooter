"""Makes a JSON Schema portable across Claude and OpenAI structured output.

Claude rejects numeric and string-length limits and any `minItems` above 1, and OpenAI strict
mode doesn't list `minLength`. Sending them would fail the request, so they are moved into the
field's description, where the model still reads them. Pydantic enforces every limit again
when the response comes back, so nothing is lost.
"""

from typing import Any

# Keywords one of the providers rejects. `minItems` of 0 or 1 is fine for both.
MOVED_KEYWORDS = ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems")
PORTABLE_MIN_ITEMS = 1

# Keywords whose value maps names to subschemas, so the names are never keywords themselves.
NAMED_SUBSCHEMAS = ("properties", "$defs")


def portable_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `schema` with unsupported limits moved into descriptions."""
    converted = {
        key: (
            {name: portable_schema(sub) for name, sub in value.items()}
            if key in NAMED_SUBSCHEMAS
            else _convert_value(value)
        )
        for key, value in schema.items()
    }
    moved = [f"{key} {converted.pop(key)}" for key in MOVED_KEYWORDS if _must_move(converted, key)]
    if moved:
        limits = f"Limits: {', '.join(moved)}."
        description = converted.get("description")
        converted["description"] = f"{description} {limits}" if description else limits
    return converted


def _convert_value(value: Any) -> Any:
    """Converts subschemas found in a keyword's value, such as `items` or `anyOf`."""
    if isinstance(value, dict):
        return portable_schema(value)
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    return value


def _must_move(node: dict[str, Any], key: str) -> bool:
    if key not in node:
        return False
    return not (key == "minItems" and node[key] <= PORTABLE_MIN_ITEMS)
