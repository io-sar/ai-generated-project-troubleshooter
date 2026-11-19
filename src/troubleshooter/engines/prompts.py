"""Loads the versioned Markdown prompt files for the LLM pipeline.

Each file is `<id>.<version>.md` and starts with a YAML header between `---` lines, giving
its ID, version, the models it was written for and its eval cases. Only the body after the
header is sent to the model.

Numbers that are business rules, such as the health bands and the escalation thresholds,
are written in the files as `{{name}}` placeholders and filled from `domain` here, so a
prompt can never disagree with the rules the app applies.
"""

import hashlib
import re
from dataclasses import fields
from pathlib import Path

import yaml

from troubleshooter import config
from troubleshooter.domain import scoring
from troubleshooter.domain.codes import EscalationLevel
from troubleshooter.domain.models import RATING_MAX, RATING_MIN, SCORE_MAX, SCORE_MIN
from troubleshooter.engines.llm_engine import Prompt, Prompts

_HEADER = re.compile(r"\A---\n(?P<header>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class PromptFileError(ValueError):
    """A prompt file is missing, has no valid header, or uses an unknown placeholder."""


def load_prompts(
    root: Path = config.PROMPTS_DIR, versions: dict[str, str] = config.PROMPT_VERSIONS
) -> Prompts:
    """Load the prompt for each pipeline stage, at the versions set in `config.py`.

    Raises:
        PromptFileError: a file is missing or malformed.
    """
    names = [field.name for field in fields(Prompts)]
    return Prompts(**{name: load_prompt(root, name, versions[name]) for name in names})


def load_prompt(root: Path, prompt_id: str, version: str) -> Prompt:
    """Load one prompt file by ID and version, with its placeholders filled.

    Raises:
        PromptFileError: the file is missing, its header doesn't match its name, or it
            uses an unknown placeholder.
    """
    path = root / f"{prompt_id}.{version}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PromptFileError(f"No prompt file {path.name}") from None
    match = _HEADER.match(text)
    if match is None:
        raise PromptFileError(f"{path.name} has no header between --- lines")
    header = yaml.safe_load(match["header"])
    if not isinstance(header, dict) or (header.get("id"), header.get("version")) != (
        prompt_id,
        version,
    ):
        raise PromptFileError(f"{path.name}: the header's id and version don't match its name")
    return Prompt(prompt_id, version, _fill(match["body"].strip(), path.name))


def prompt_fingerprint(root: Path, prompt_id: str, version: str) -> str:
    """Return the SHA-256 of a prompt file's text, as hex.

    Line endings are normalised first, so a Windows checkout and CI agree.

    Raises:
        PromptFileError: the file is missing.
    """
    path = root / f"{prompt_id}.{version}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PromptFileError(f"No prompt file {path.name}") from None
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def rule_values() -> dict[str, int]:
    """The numbers prompts may name, taken from the domain rules."""
    lowest = {level: score for score, level in scoring.ESCALATION_MIN_SCORES}
    return {
        "score_min": SCORE_MIN,
        "score_max": SCORE_MAX,
        "good_min": scoring.GOOD_MIN_SCORE,
        "problematic_min": scoring.PROBLEMATIC_MIN_SCORE,
        "problematic_max": scoring.GOOD_MIN_SCORE - 1,
        "rating_min": RATING_MIN,
        "rating_max": RATING_MAX,
        "team_min": lowest[EscalationLevel.TEAM],
        "team_max": lowest[EscalationLevel.PM] - 1,
        "pm_min": lowest[EscalationLevel.PM],
        "pm_max": lowest[EscalationLevel.SPONSOR] - 1,
        "sponsor_min": lowest[EscalationLevel.SPONSOR],
        "sponsor_max": lowest[EscalationLevel.STEERING] - 1,
        "steering_min": lowest[EscalationLevel.STEERING],
        "steering_max": RATING_MAX * RATING_MAX,
    }


def _fill(body: str, name: str) -> str:
    values = rule_values()

    def value(match: re.Match[str]) -> str:
        key = match[1]
        if key not in values:
            raise PromptFileError(f"{name} uses an unknown placeholder {{{{{key}}}}}")
        return str(values[key])

    return _PLACEHOLDER.sub(value, body)
