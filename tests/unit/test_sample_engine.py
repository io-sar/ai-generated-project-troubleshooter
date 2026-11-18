import json
import socket
from pathlib import Path
from typing import Any

import pytest
import yaml

from troubleshooter.domain.codes import ReportSource
from troubleshooter.engines.base import AnalysisEngine
from troubleshooter.engines.sample_engine import (
    SampleEngine,
    SampleFormatError,
    SampleNotFoundError,
    list_sample_ids,
    load_sample,
)

from .report_data import diagnosis_data, report_data


def meta_data(badge: str = "placeholder") -> dict[str, Any]:
    return {
        "title": "Vendor dependency slipping",
        "badge": badge,
        "scenario": {
            "project_type": "software_delivery",
            "text": "The vendor API is late again.",
            "key_points": ["Vendor slip"],
        },
    }


def write_sample(root: Path, sample_id: str = "vendor", **overrides: Any) -> Path:
    """Write a valid sample folder; an override replaces one file's content."""
    final = report_data()
    final["stakeholder_updates"]["executive"] = "Edited by the author."
    files: dict[str, str] = {
        "scenario.yaml": yaml.safe_dump(meta_data()),
        "diagnosis.json": json.dumps(diagnosis_data()),
        "draft.json": json.dumps(report_data()),
        "final.json": json.dumps(final),
        "changes.md": "I shortened the executive update.",
    }
    files.update({name.replace("_", "."): text for name, text in overrides.items()})
    folder = root / sample_id
    folder.mkdir(parents=True)
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_loads_a_valid_sample(tmp_path: Path) -> None:
    write_sample(tmp_path)

    sample = load_sample(tmp_path, "vendor")

    assert sample.id == "vendor"
    assert sample.badge is ReportSource.PLACEHOLDER
    assert sample.scenario.key_points == ["Vendor slip"]
    assert sample.final.stakeholder_updates.executive == "Edited by the author."
    assert sample.changes == "I shortened the executive update."


def test_engine_returns_the_stored_diagnosis_and_ai_draft(tmp_path: Path) -> None:
    write_sample(tmp_path)
    sample = load_sample(tmp_path, "vendor")
    engine: AnalysisEngine = SampleEngine(sample)

    diagnosis = engine.diagnose(sample.scenario)

    assert diagnosis == sample.diagnosis
    assert engine.generate(sample.scenario, diagnosis) == sample.draft
    assert sample.draft != sample.final


def test_loading_makes_no_network_calls(tmp_path: Path, no_network: None) -> None:
    write_sample(tmp_path)

    assert load_sample(tmp_path, "vendor").id == "vendor"


def test_lists_sample_folders_sorted_and_ignores_others(tmp_path: Path) -> None:
    write_sample(tmp_path, "vendor")
    write_sample(tmp_path, "go_live")
    (tmp_path / "notes").mkdir()
    (tmp_path / "README.md").write_text("not a sample", encoding="utf-8")

    assert list_sample_ids(tmp_path) == ["go_live", "vendor"]


def test_empty_folder_has_no_samples(tmp_path: Path) -> None:
    assert list_sample_ids(tmp_path) == []


def test_unknown_id_is_not_found(tmp_path: Path) -> None:
    write_sample(tmp_path)

    with pytest.raises(SampleNotFoundError, match="nope"):
        load_sample(tmp_path, "nope")


@pytest.mark.parametrize("sample_id", ["../vendor", "other/../../vendor", "", "..", "/etc"])
def test_path_like_ids_are_not_found(tmp_path: Path, sample_id: str) -> None:
    # A valid sample sits just outside the root, so a traversal would find something.
    write_sample(tmp_path, "vendor")
    write_sample(tmp_path / "inner", "other")

    with pytest.raises(SampleNotFoundError):
        load_sample(tmp_path / "inner", sample_id)


@pytest.mark.parametrize("missing", ["diagnosis.json", "draft.json", "final.json", "changes.md"])
def test_missing_file_names_the_file(tmp_path: Path, missing: str) -> None:
    folder = write_sample(tmp_path)
    (folder / missing).unlink()

    with pytest.raises(SampleFormatError, match=missing.replace(".", r"\.")):
        load_sample(tmp_path, "vendor")


def test_invalid_yaml_is_a_format_error(tmp_path: Path) -> None:
    write_sample(tmp_path, scenario_yaml="title: [unclosed")

    with pytest.raises(SampleFormatError, match=r"scenario\.yaml"):
        load_sample(tmp_path, "vendor")


def test_invalid_json_is_a_format_error(tmp_path: Path) -> None:
    write_sample(tmp_path, draft_json="{not json")

    with pytest.raises(SampleFormatError, match=r"draft\.json"):
        load_sample(tmp_path, "vendor")


def test_report_breaking_the_schema_is_a_format_error(tmp_path: Path) -> None:
    draft = report_data()
    draft["risks"][0]["likelihood"] = 9
    write_sample(tmp_path, draft_json=json.dumps(draft))

    with pytest.raises(SampleFormatError, match="schema"):
        load_sample(tmp_path, "vendor")


def test_yaml_that_is_not_a_mapping_is_a_format_error(tmp_path: Path) -> None:
    write_sample(tmp_path, scenario_yaml="- just a list")

    with pytest.raises(SampleFormatError, match="schema"):
        load_sample(tmp_path, "vendor")


def test_unknown_badge_is_a_format_error(tmp_path: Path) -> None:
    write_sample(tmp_path, scenario_yaml=yaml.safe_dump(meta_data(badge="verified")))

    with pytest.raises(SampleFormatError):
        load_sample(tmp_path, "vendor")


def test_a_sample_cannot_claim_to_be_live(tmp_path: Path) -> None:
    write_sample(tmp_path, scenario_yaml=yaml.safe_dump(meta_data(badge="live")))

    with pytest.raises(SampleFormatError):
        load_sample(tmp_path, "vendor")


def test_empty_note_is_a_format_error(tmp_path: Path) -> None:
    write_sample(tmp_path, changes_md="   ")

    with pytest.raises(SampleFormatError):
        load_sample(tmp_path, "vendor")


def test_recorded_badge_loads(tmp_path: Path) -> None:
    write_sample(tmp_path, scenario_yaml=yaml.safe_dump(meta_data(badge="recorded")))

    assert load_sample(tmp_path, "vendor").badge is ReportSource.RECORDED
