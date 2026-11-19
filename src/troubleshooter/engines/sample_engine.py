"""Stored demo runs: loading sample folders, and an engine that replays them.

A sample folder holds ``scenario.yaml`` (title, badge and scenario), ``diagnosis.json``,
``draft.json``, ``final.json`` and ``changes.md``, plus ``run.json`` when it was recorded
from a model. Loading reads local files only.

A folder is "in review" until the author adds ``final.json`` and ``changes.md``: it has
been recorded but not reviewed, so it isn't offered as a sample yet. A project that got no
full report, such as a healthy one, has no ``draft.json`` or ``final.json``, so it needs
only ``changes.md``.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from troubleshooter import config
from troubleshooter.domain.models import Diagnosis, Report, RunInfo, Sample, Scenario
from troubleshooter.domain.triage import needs_report
from troubleshooter.engines.prompts import PromptFileError, prompt_fingerprint

_META_FILE = "scenario.yaml"
DRAFT_FILE = "draft.json"
FINAL_FILE = "final.json"
CHANGES_FILE = "changes.md"
RUN_FILE = "run.json"


class SampleNotFoundError(LookupError):
    """No sample has the requested ID."""


class SampleFormatError(ValueError):
    """A sample's files are missing or don't match the schema."""


class SampleEngine:
    """Replays a stored run. Implements `AnalysisEngine`.

    Like the Live engine, it returns the AI's draft. The author's final version and
    note are read from the `Sample` itself.
    """

    def __init__(self, sample: Sample) -> None:
        """Wrap a loaded sample."""
        self._sample = sample

    def diagnose(self, scenario: Scenario) -> Diagnosis:
        """Return the stored diagnosis. The scenario is the sample's own."""
        return self._sample.diagnosis

    def generate(self, scenario: Scenario, diagnosis: Diagnosis) -> Report:
        """Return the stored AI draft.

        Raises:
            LookupError: the sample has no draft, because its project needed no report.
        """
        if self._sample.draft is None:
            raise LookupError(f"Sample {self._sample.id!r} has no report")
        return self._sample.draft


def list_sample_ids(root: Path) -> list[str]:
    """Return the IDs of the sample folders under ``root``, sorted.

    Args:
        root: The folder that holds one sub-folder per sample.

    Returns:
        Folder names that contain a ``scenario.yaml`` and the author's review files.
        Samples still in review and anything else are left out.
    """
    return [folder.name for folder in _sample_folders(root) if _reviewed(folder)]


def list_samples_in_review(root: Path) -> list[str]:
    """Return the IDs of recorded samples the author hasn't reviewed yet, sorted."""
    return [folder.name for folder in _sample_folders(root) if not _reviewed(folder)]


def _sample_folders(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.glob(f"*/{_META_FILE}"))


def _reviewed(folder: Path) -> bool:
    # A recorded draft needs the author's final version; no draft means no report to correct.
    has_final_if_needed = (folder / FINAL_FILE).is_file() or not (folder / DRAFT_FILE).exists()
    return (folder / CHANGES_FILE).is_file() and has_final_if_needed


def load_sample(root: Path, sample_id: str) -> Sample:
    """Load and validate one sample.

    Args:
        root: The folder that holds one sub-folder per sample.
        sample_id: The sample's ID, possibly from a URL, so it is only matched against
            the listed IDs and never used to build a path directly.

    Returns:
        The validated sample.

    Raises:
        SampleNotFoundError: If no sample has this ID, or it is still in review.
        SampleFormatError: If a file is missing, unreadable or fails validation, or the
            sample has a report when its diagnosis needs none, or the other way round.
    """
    if sample_id not in list_sample_ids(root):
        raise SampleNotFoundError(f"No sample with ID {sample_id!r}")
    folder = root / sample_id
    meta = _read(folder / _META_FILE, yaml.safe_load)
    data = {
        **(meta if isinstance(meta, dict) else {}),
        "id": sample_id,
        "diagnosis": _read(folder / "diagnosis.json", json.loads),
        "changes": _read(folder / CHANGES_FILE, str),
    }
    if (folder / FINAL_FILE).is_file():
        data["draft"] = _read(folder / DRAFT_FILE, json.loads)
        data["final"] = _read(folder / FINAL_FILE, json.loads)
    if (folder / RUN_FILE).is_file():
        data["run"] = _read(folder / RUN_FILE, json.loads)
    try:
        sample = Sample.model_validate(data)
    except ValidationError as error:
        raise SampleFormatError(f"Sample {sample_id!r} doesn't match the schema") from error
    if (sample.final is not None) != needs_report(sample.diagnosis):
        raise SampleFormatError(
            f"Sample {sample_id!r} must have a report exactly when its project is troubled"
        )
    return sample


def recording_problems(run: RunInfo, prompts_root: Path = config.PROMPTS_DIR) -> list[str]:
    """Return what no longer matches the code a sample was recorded with.

    A recorded sample stays traceable only while its prompt files are unchanged and its
    model is still offered. A changed prompt needs a new version file, not an edit.

    Args:
        run: How the sample was recorded.
        prompts_root: The folder that holds the prompt files.

    Returns:
        One message per problem; empty when the recording still matches.
    """
    problems = []
    choice = config.MODELS.get(run.provider)
    if choice is None or run.model not in choice.all:
        problems.append(f"model {run.model} is no longer offered for {run.provider}")
    for prompt_id, version in sorted(run.prompt_versions.items()):
        name = f"{prompt_id}.{version}.md"
        try:
            fingerprint = prompt_fingerprint(prompts_root, prompt_id, version)
        except PromptFileError:
            problems.append(f"{name} is missing; recorded samples still use it")
            continue
        if fingerprint != run.prompt_fingerprints.get(prompt_id):
            problems.append(
                f"{name} changed after this sample was recorded; "
                "restore it and add a new version instead"
            )
    return problems


def _read(path: Path, parse: Callable[[str], Any]) -> Any:
    try:
        return parse(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as error:
        raise SampleFormatError(f"Can't read {path.parent.name}/{path.name}") from error
