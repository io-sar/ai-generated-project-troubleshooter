"""Reads the author's API key for local scripts. The deployed app never uses this.

The key lives in the gitignored local secrets file. It is never printed or saved.
"""

import tomllib
from pathlib import Path

SECRETS = Path(__file__).parents[1] / ".streamlit" / "secrets.toml"
KEY_NAME = "ANTHROPIC_API_KEY"


def read_key(path: Path = SECRETS) -> str:
    """Return the Anthropic key from the local secrets file, or stop with a clear message."""
    try:
        with path.open("rb") as file:
            key = tomllib.load(file).get(KEY_NAME, "")
    except FileNotFoundError:
        raise SystemExit("The local secrets file is missing") from None
    if not isinstance(key, str) or not key.strip():
        raise SystemExit(f"{KEY_NAME} is missing from the local secrets file")
    return key


def contains_key(text: str, keys: list[str]) -> bool:
    """Return True if any of the keys appears in `text`."""
    return any(key and key in text for key in keys)
