"""Stored demo runs: loading sample folders, and an engine that replays them.

A sample folder holds ``scenario.yaml`` (title, badge and scenario), ``diagnosis.json``,
``draft.json``, ``final.json`` and ``changes.md``, plus ``run.json`` when it was recorded
from a model. Loading reads local files only.

A folder is "in review" until the author adds ``final.json`` and ``changes.md``: it has
been recorded but not reviewed, so it isn't offered as a sample yet.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from troubleshooter.domain.models import Diagnosis, Report, Sample, Scenario

_META_FILE = "scenario.yaml"
# The author's files. Until both exist, a recorded sample is in review.
REVIEW_FILES = ("final.json", "changes.md")
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
        """Return the stored AI draft."""
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
    return all((folder / name).is_file() for name in REVIEW_FILES)


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
        SampleFormatError: If a file is missing, unreadable or fails validation.
    """
    if sample_id not in list_sample_ids(root):
        raise SampleNotFoundError(f"No sample with ID {sample_id!r}")
    folder = root / sample_id
    meta = _read(folder / _META_FILE, yaml.safe_load)
    data = {
        **(meta if isinstance(meta, dict) else {}),
        "id": sample_id,
        "diagnosis": _read(folder / "diagnosis.json", json.loads),
        "draft": _read(folder / "draft.json", json.loads),
        "final": _read(folder / "final.json", json.loads),
        "changes": _read(folder / "changes.md", str),
    }
    if (folder / RUN_FILE).is_file():
        data["run"] = _read(folder / RUN_FILE, json.loads)
    try:
        return Sample.model_validate(data)
    except ValidationError as error:
        raise SampleFormatError(f"Sample {sample_id!r} doesn't match the schema") from error


def _read(path: Path, parse: Callable[[str], Any]) -> Any:
    try:
        return parse(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as error:
        raise SampleFormatError(f"Can't read {path.parent.name}/{path.name}") from error
