import json
import socket
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from troubleshooter.domain.codes import ReportSource
from troubleshooter.domain.models import RunInfo
from troubleshooter.engines.base import AnalysisEngine
from troubleshooter.engines.prompts import prompt_fingerprint
from troubleshooter.engines.sample_engine import (
    SampleEngine,
    SampleFormatError,
    SampleNotFoundError,
    list_sample_ids,
    list_samples_in_review,
    load_sample,
    recording_problems,
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
    assert sample.final is not None
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


@pytest.mark.parametrize("missing", ["diagnosis.json", "draft.json"])
def test_missing_recorded_file_names_the_file(tmp_path: Path, missing: str) -> None:
    folder = write_sample(tmp_path)
    (folder / missing).unlink()

    with pytest.raises(SampleFormatError, match=missing.replace(".", r"\.")):
        load_sample(tmp_path, "vendor")


@pytest.mark.parametrize("missing", [["final.json"], ["changes.md"], ["final.json", "changes.md"]])
def test_sample_without_the_author_review_is_in_review(tmp_path: Path, missing: list[str]) -> None:
    folder = write_sample(tmp_path, "recorded")
    write_sample(tmp_path, "vendor")
    for name in missing:
        (folder / name).unlink()

    assert list_sample_ids(tmp_path) == ["vendor"]
    assert list_samples_in_review(tmp_path) == ["recorded"]
    with pytest.raises(SampleNotFoundError):
        load_sample(tmp_path, "recorded")


def test_reviewed_sample_is_not_in_review(tmp_path: Path) -> None:
    write_sample(tmp_path)

    assert list_samples_in_review(tmp_path) == []


def test_review_file_that_is_a_folder_does_not_count(tmp_path: Path) -> None:
    folder = write_sample(tmp_path)
    (folder / "changes.md").unlink()
    (folder / "changes.md").mkdir()

    assert list_sample_ids(tmp_path) == []


def test_loads_how_a_recorded_sample_was_run(tmp_path: Path) -> None:
    run = {
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "prompt_versions": {"diagnose": "v1", "generate": "v1"},
        "prompt_fingerprints": {"diagnose": "a" * 64, "generate": "b" * 64},
        "recorded_on": "2026-11-19",
    }
    write_sample(tmp_path, run_json=json.dumps(run))

    sample = load_sample(tmp_path, "vendor")

    assert sample.run is not None
    assert (sample.run.model, sample.run.prompt_versions["generate"]) == ("claude-haiku-5-5", "v1")
    assert sample.run.recorded_on.isoformat() == "2026-11-19"


def test_sample_without_a_run_file_has_no_run(tmp_path: Path) -> None:
    write_sample(tmp_path)

    assert load_sample(tmp_path, "vendor").run is None


@pytest.mark.parametrize(
    "run_json", ["not json", json.dumps({"provider": "anthropic"}), json.dumps([1])]
)
def test_broken_run_file_is_a_format_error(tmp_path: Path, run_json: str) -> None:
    write_sample(tmp_path, run_json=run_json)

    with pytest.raises(SampleFormatError):
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


# Recordings that no longer match the code


def recorded_run(prompts_root: Path, model: str = "claude-haiku-5-5") -> RunInfo:
    """A run recorded against the prompt files now in `prompts_root`."""
    for prompt_id in ("diagnose", "generate"):
        (prompts_root / f"{prompt_id}.v1.md").write_text(f"{prompt_id} prompt\n", "utf-8")
    versions = {"diagnose": "v1", "generate": "v1"}
    return RunInfo(
        provider="anthropic",
        model=model,
        prompt_versions=versions,
        prompt_fingerprints={
            prompt_id: prompt_fingerprint(prompts_root, prompt_id, version)
            for prompt_id, version in versions.items()
        },
        recorded_on=date(2026, 11, 19),
    )


def test_unchanged_recording_has_no_problems(tmp_path: Path) -> None:
    assert recording_problems(recorded_run(tmp_path), tmp_path) == []


def test_changed_prompt_file_says_to_add_a_new_version(tmp_path: Path) -> None:
    run = recorded_run(tmp_path)
    (tmp_path / "generate.v1.md").write_text("generate prompt, edited\n", "utf-8")

    assert recording_problems(run, tmp_path) == [
        "generate.v1.md changed after this sample was recorded; "
        "restore it and add a new version instead"
    ]


def test_missing_prompt_version_is_a_problem(tmp_path: Path) -> None:
    run = recorded_run(tmp_path)
    (tmp_path / "diagnose.v1.md").unlink()

    assert recording_problems(run, tmp_path) == [
        "diagnose.v1.md is missing; recorded samples still use it"
    ]


def test_prompt_with_no_fingerprint_counts_as_changed(tmp_path: Path) -> None:
    run = recorded_run(tmp_path)
    run = run.model_copy(
        update={"prompt_fingerprints": {"diagnose": run.prompt_fingerprints["diagnose"]}}
    )

    assert recording_problems(run, tmp_path) == [
        "generate.v1.md changed after this sample was recorded; "
        "restore it and add a new version instead"
    ]


def test_model_no_longer_offered_is_a_problem(tmp_path: Path) -> None:
    run = recorded_run(tmp_path, model="claude-retired-1")

    assert recording_problems(run, tmp_path) == [
        "model claude-retired-1 is no longer offered for anthropic"
    ]


def test_unknown_provider_is_a_problem(tmp_path: Path) -> None:
    run = recorded_run(tmp_path).model_copy(update={"provider": "openai"})

    assert recording_problems(run, tmp_path) == [
        "model claude-haiku-5-5 is no longer offered for openai"
    ]


# Projects that get no full report


def write_healthy_sample(root: Path, sample_id: str = "steady") -> Path:
    """A reviewed sample for a healthy project: a diagnosis and a note, with no report."""
    folder = write_sample(root, sample_id, diagnosis_json=json.dumps(healthy_diagnosis()))
    (folder / "draft.json").unlink()
    (folder / "final.json").unlink()
    return folder


def healthy_diagnosis() -> dict[str, Any]:
    return diagnosis_data() | {"classification": "healthy", "things_to_watch": ["Vendor SLA"]}


def test_healthy_sample_loads_without_a_report(tmp_path: Path) -> None:
    write_healthy_sample(tmp_path)

    sample = load_sample(tmp_path, "steady")

    assert (sample.draft, sample.final) == (None, None)
    assert sample.diagnosis.things_to_watch == ["Vendor SLA"]
    assert list_sample_ids(tmp_path) == ["steady"]


def test_healthy_sample_needs_only_the_note_to_be_reviewed(tmp_path: Path) -> None:
    folder = write_healthy_sample(tmp_path)
    (folder / "changes.md").unlink()

    assert list_sample_ids(tmp_path) == []
    assert list_samples_in_review(tmp_path) == ["steady"]


def test_engine_has_no_draft_for_a_healthy_sample(tmp_path: Path) -> None:
    write_healthy_sample(tmp_path)
    sample = load_sample(tmp_path, "steady")

    with pytest.raises(LookupError, match="steady"):
        SampleEngine(sample).generate(sample.scenario, sample.diagnosis)


def test_healthy_sample_with_a_report_is_a_format_error(tmp_path: Path) -> None:
    write_sample(tmp_path, diagnosis_json=json.dumps(healthy_diagnosis()))

    with pytest.raises(SampleFormatError, match="exactly when its project is troubled"):
        load_sample(tmp_path, "vendor")


def test_troubled_sample_without_a_report_is_a_format_error(tmp_path: Path) -> None:
    folder = write_sample(tmp_path)
    (folder / "draft.json").unlink()
    (folder / "final.json").unlink()

    with pytest.raises(SampleFormatError, match="exactly when its project is troubled"):
        load_sample(tmp_path, "vendor")
