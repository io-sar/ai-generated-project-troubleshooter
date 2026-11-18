"""Markdown escaping, shared by the app and the Markdown export so the rule lives once."""

import re

# Everything Streamlit's and common Markdown renderers treat as syntax, including
# Streamlit's :colour[] directives and $maths$.
_MARKDOWN_SYNTAX = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")


def escape_markdown(text: str) -> str:
    """Escape Markdown so text shows exactly as written, with no links, images or styling.

    Args:
        text: Text that may come from a model or a visitor.

    Returns:
        The text with every Markdown character backslash-escaped.
    """
    return _MARKDOWN_SYNTAX.sub(r"\\\1", text)
