"""The two-stage Live pipeline: diagnose the scenario, then write the report.

Each stage asks the model for structured output and validates the answer. A failed answer
gets one repair call, then a typed error. Transport errors are retried by the SDK only, so
they pass through here unchanged.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from troubleshooter import config
from troubleshooter.domain.models import HUMAN_FIELDS, Diagnosis, Report, Scenario
from troubleshooter.domain.triage import needs_report
from troubleshooter.llm.base import LLMClient
from troubleshooter.llm.errors import InvalidOutputError, LLMError, LLMErrorKind

logger = logging.getLogger(__name__)

Answer = TypeVar("Answer", bound=BaseModel)

# Untrusted text is wrapped in these tags. A tag inside the text itself, in any case or
# spacing and with or without attributes, is replaced, so the text can't close its block
# early or open a new one.
DELIMITERS = ("scenario", "diagnosis", "previous_answer", "validation_errors")
_TAG = re.compile(r"<\s*/?\s*(?:" + "|".join(DELIMITERS) + r")\b[^>]*>", re.IGNORECASE)
TAG_REPLACEMENT = "[tag removed]"


@dataclass(frozen=True)
class Prompt:
    """One versioned prompt file's text, with the ID and version that are logged."""

    id: str
    version: str
    text: str


@dataclass(frozen=True)
class Prompts:
    """The prompts the pipeline sends. Loaded from the Markdown prompt files."""

    diagnose: Prompt
    generate: Prompt
    repair: Prompt


def wrap(tag: str, text: str, attributes: dict[str, str] | None = None) -> str:
    """Return `text` inside `<tag>` delimiters, with any delimiter tags in it replaced.

    Attribute values must be trusted codes, such as a project type, never visitor text.
    """
    attrs = "".join(f' {name}="{value}"' for name, value in (attributes or {}).items())
    return f"<{tag}{attrs}>\n{_TAG.sub(TAG_REPLACEMENT, text)}\n</{tag}>"


class LLMEngine:
    """Runs both stages on one model. Implements `AnalysisEngine`."""

    def __init__(self, client: LLMClient, prompts: Prompts) -> None:
        """Use `client` for every call. The engine never creates a client itself."""
        self._client = client
        self._prompts = prompts

    def diagnose(self, scenario: Scenario) -> Diagnosis:
        """Classify the scenario and list its warning signs.

        Raises:
            LLMError: the call failed, or the answer was invalid after one repair.
        """
        return self._ask(
            self._prompts.diagnose, _scenario_block(scenario), Diagnosis, config.DIAGNOSE_MAX_TOKENS
        )

    def generate(self, scenario: Scenario, diagnosis: Diagnosis) -> Report:
        """Write the full report for a troubled project.

        Raises:
            ValueError: the diagnosis says the project doesn't need a report.
            LLMError: the call failed, or the answer was invalid after one repair.
        """
        if not needs_report(diagnosis):
            raise ValueError("Only a troubled project gets a full report")
        user = "\n\n".join(
            [_scenario_block(scenario), wrap("diagnosis", diagnosis.model_dump_json(indent=2))]
        )
        return self._ask(self._prompts.generate, user, Report, config.GENERATE_MAX_TOKENS)

    def _ask(self, prompt: Prompt, user: str, model: type[Answer], max_tokens: int) -> Answer:
        schema = model.model_json_schema()
        answer, problems = self._attempt(prompt.text, user, schema, max_tokens, model)
        if answer is not None:
            _log(prompt, "valid")
            return answer
        repaired, _ = self._attempt(
            "\n\n".join([prompt.text, self._prompts.repair.text]),
            "\n\n".join([user, *problems]),
            schema,
            max_tokens,
            model,
        )
        if repaired is not None:
            _log(prompt, "repaired")
            return repaired
        _log(prompt, "invalid")
        raise LLMError(LLMErrorKind.INVALID_ANSWER)

    def _attempt(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int,
        model: type[Answer],
    ) -> tuple[Answer | None, list[str]]:
        """Return the validated answer, or None and the blocks a repair call needs."""
        try:
            raw = self._client.complete_structured(system, user, schema, max_tokens)
        except InvalidOutputError:
            # No JSON object to show; the repair prompt covers this case.
            return None, []
        previous = wrap("previous_answer", json.dumps(raw, ensure_ascii=False, indent=2))
        markers = sorted(_human_field_paths(raw))
        if markers:
            errors = [f"{path}: Extra inputs are not permitted" for path in markers]
            return None, [previous, wrap("validation_errors", "\n".join(errors))]
        try:
            return model.model_validate(raw), []
        except ValidationError as error:
            return None, [previous, wrap("validation_errors", _describe(error))]


def _scenario_block(scenario: Scenario) -> str:
    return wrap("scenario", scenario.text, {"project_type": scenario.project_type.value})


def _human_field_paths(value: Any, path: str = "") -> list[str]:
    """Every path in a JSON answer where a field only humans may set appears."""
    if isinstance(value, dict):
        found = [f"{path}{key}" for key in value if key in HUMAN_FIELDS]
        return found + [
            p for key, sub in value.items() for p in _human_field_paths(sub, f"{path}{key}.")
        ]
    if isinstance(value, list):
        return [p for i, sub in enumerate(value) for p in _human_field_paths(sub, f"{path}{i}.")]
    return []


def _describe(error: ValidationError) -> str:
    """Each problem's field path and message, without the values, which may be long."""
    lines = [
        f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
        for issue in error.errors(include_url=False, include_input=False)
    ]
    return "\n".join(lines[: config.REPAIR_MAX_ERRORS])


def _log(prompt: Prompt, outcome: str) -> None:
    # Metadata only: never the scenario or the answer.
    logger.info("stage prompt=%s version=%s outcome=%s", prompt.id, prompt.version, outcome)
