"""UI text catalogs and t(). Imports no other project package.

Fixed values are stored as codes and translated here for display only. Callers build
the key from the code, for example ``t(f"health_label.{label}")``.
"""

from functools import cache
from pathlib import Path
from typing import Any

import yaml

_CATALOG_PATH = Path(__file__).with_name("en.yaml")


def t(key: str, **params: Any) -> str:
    """Return the UI text for a key, with any ``{placeholders}`` filled in.

    Args:
        key: Dotted catalog key, such as ``"app.title"``.
        **params: Values for the placeholders in the text.

    Returns:
        The text in English.

    Raises:
        KeyError: If the key isn't in the catalog, or a placeholder has no value.
    """
    try:
        text = _catalog()[key]
    except KeyError:
        raise KeyError(f"Missing UI text key: {key!r}") from None
    return text.format(**params)


def keys() -> frozenset[str]:
    """Return every key in the catalog, for coverage checks."""
    return frozenset(_catalog())


@cache
def _catalog() -> dict[str, str]:
    # Static app text, the same for every visitor, so caching it is safe.
    with _CATALOG_PATH.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return _flatten(data)


def _flatten(node: dict[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for name, value in node.items():
        key = f"{prefix}{name}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{key}."))
        else:
            flat[key] = str(value)
    return flat
