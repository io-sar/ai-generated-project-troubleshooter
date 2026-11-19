"""The sample recording script, run with a scripted client. Real runs are local and paid."""

import json
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from troubleshooter import config
from troubleshooter.domain.codes import InputClassification, ProjectType
from troubleshooter.domain.models import Diagnosis, Report, RunInfo, Scenario
from troubleshooter.engines.llm_engine import LLMEngine
from troubleshooter.engines.prompts import prompt_fingerprint
from troubleshooter.engines.sample_engine import (
    list_sample_ids,
    list_samples_in_review,
    load_sample,
)
from troubleshooter.llm.base import Provider

from ..script_loading import load_script
from .test_llm_engine import DIAGNOSIS, PROMPTS, REPORT, ScriptedClient

KEY = "sk-ant-recording-key-0000"
SCENARIO = Scenario(project_type=ProjectType.SERVICE_MIGRATION, text="Cutover slipped twice.")
VERSIONS = {"diagnose": "v1", "generate": "v1", "repair": "v1"}
RUN = RunInfo(
    provider="anthropic",
    model="claude-haiku-5-5",
    prompt_versions=VERSIONS,
    prompt_fingerprints={
        prompt_id: prompt_fingerprint(config.PROMPTS_DIR, prompt_id, version)
        for prompt_id, version in VERSIONS.items()
    },
    recorded_on=date(2026, 11, 19),
)


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return load_script("record_sample")


def write_meta(folder: Path, badge: str = "recorded") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"title": "CRM migration", "badge": badge, "scenario": SCENARIO.model_dump(mode="json")}
    (folder / "scenario.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")


def files_for(script: ModuleType, classification: str = "troubled") -> dict[str, str]:
    diagnosis = Diagnosis.model_validate(DIAGNOSIS | {"classification": classification})
    report = Report.model_validate(REPORT) if classification == "troubled" else None
    files: dict[str, str] = script.sample_files(diagnosis, report, RUN)
    return files


# Running the pipeline


def test_troubled_project_gets_a_diagnosis_and_a_draft(script: ModuleType) -> None:
    client = ScriptedClient(DIAGNOSIS, REPORT)

    diagnosis, report = script.record(LLMEngine(client, PROMPTS), SCENARIO)

    assert diagnosis.classification is InputClassification.TROUBLED
    assert report == Report.model_validate(REPORT)
    assert len(client.calls) == 2


@pytest.mark.parametrize("classification", ["healthy", "too_thin", "off_topic"])
def test_project_needing_no_report_skips_stage_2(script: ModuleType, classification: str) -> None:
    client = ScriptedClient(DIAGNOSIS | {"classification": classification})

    _, report = script.record(LLMEngine(client, PROMPTS), SCENARIO)

    assert report is None
    assert len(client.calls) == 1


def test_run_info_records_every_prompt_version(script: ModuleType) -> None:
    run = script.run_info(Provider.ANTHROPIC, "claude-haiku-5-5", PROMPTS, date(2026, 11, 19))

    assert run == RUN


def test_run_info_fingerprints_the_files_it_was_given(script: ModuleType, tmp_path: Path) -> None:
    for prompt_id, version in VERSIONS.items():
        (tmp_path / f"{prompt_id}.{version}.md").write_text(f"{prompt_id} edited", "utf-8")

    run = script.run_info(
        Provider.ANTHROPIC, "claude-haiku-5-5", PROMPTS, RUN.recorded_on, tmp_path
    )

    assert run.prompt_versions == RUN.prompt_versions
    assert run.prompt_fingerprints != RUN.prompt_fingerprints
    assert len(set(run.prompt_fingerprints.values())) == len(VERSIONS)


# The recorded files


def test_files_round_trip_to_the_same_models(script: ModuleType) -> None:
    files = files_for(script)

    assert set(files) == {"diagnosis.json", "draft.json", "run.json"}
    assert Diagnosis.model_validate_json(files["diagnosis.json"]) == Diagnosis.model_validate(
        DIAGNOSIS
    )
    assert Report.model_validate_json(files["draft.json"]) == Report.model_validate(REPORT)
    assert RunInfo.model_validate_json(files["run.json"]) == RUN
    assert all(text.endswith("}\n") for text in files.values())


def test_draft_holds_only_the_model_report(script: ModuleType) -> None:
    draft = files_for(script)["draft.json"]

    assert "human_adjusted" not in draft
    assert '"note"' not in draft
    assert json.loads(draft) == REPORT


def test_no_draft_when_no_report_was_made(script: ModuleType) -> None:
    assert set(files_for(script, "healthy")) == {"diagnosis.json", "run.json"}


# Saving


def test_saves_the_files_and_leaves_the_sample_in_review(
    script: ModuleType, tmp_path: Path
) -> None:
    write_meta(tmp_path / "crm")

    script.save(tmp_path / "crm", files_for(script), [KEY], overwrite=False)

    assert list_samples_in_review(tmp_path) == ["crm"]
    assert list_sample_ids(tmp_path) == []


def test_sample_loads_with_its_run_once_the_author_reviews_it(
    script: ModuleType, tmp_path: Path
) -> None:
    folder = tmp_path / "crm"
    write_meta(folder)
    script.save(folder, files_for(script), [KEY], overwrite=False)
    (folder / "final.json").write_text(json.dumps(REPORT), encoding="utf-8")
    (folder / "changes.md").write_text("I tightened the risks.", encoding="utf-8")

    sample = load_sample(tmp_path, "crm")

    assert sample.run == RUN
    assert sample.draft == Report.model_validate(REPORT)


def test_refuses_to_replace_recorded_files(script: ModuleType, tmp_path: Path) -> None:
    folder = tmp_path / "crm"
    write_meta(folder)
    (folder / "diagnosis.json").write_text("earlier run", encoding="utf-8")

    with pytest.raises(SystemExit, match=r"Already recorded: diagnosis\.json"):
        script.save(folder, files_for(script), [KEY], overwrite=False)

    assert (folder / "diagnosis.json").read_text(encoding="utf-8") == "earlier run"
    assert not (folder / "draft.json").exists()


def test_overwrite_replaces_and_removes_a_stale_draft(script: ModuleType, tmp_path: Path) -> None:
    folder = tmp_path / "crm"
    write_meta(folder)
    script.save(folder, files_for(script), [KEY], overwrite=False)

    script.save(folder, files_for(script, "healthy"), [KEY], overwrite=True)

    assert not (folder / "draft.json").exists()
    assert (
        json.loads((folder / "diagnosis.json").read_text(encoding="utf-8"))["classification"]
        == "healthy"
    )


def test_stops_before_saving_a_file_with_the_key(script: ModuleType, tmp_path: Path) -> None:
    folder = tmp_path / "crm"
    write_meta(folder)
    files = files_for(script) | {"run.json": f'{{"model": "{KEY}"}}\n'}

    with pytest.raises(SystemExit, match="contain the key"):
        script.save(folder, files, [KEY], overwrite=False)

    assert not any((folder / name).exists() for name in files)


# Reading the scenario


def test_reads_the_author_scenario(script: ModuleType, tmp_path: Path) -> None:
    write_meta(tmp_path / "crm")

    assert script.read_scenario(tmp_path / "crm") == SCENARIO


def test_missing_scenario_stops_with_a_hint(script: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "crm").mkdir()

    with pytest.raises(SystemExit, match="Write the scenario first"):
        script.read_scenario(tmp_path / "crm")


def test_never_records_over_the_placeholder(script: ModuleType, tmp_path: Path) -> None:
    write_meta(tmp_path / "placeholder", badge="placeholder")

    with pytest.raises(SystemExit, match="placeholder"):
        script.read_scenario(tmp_path / "placeholder")


# The local key


@pytest.fixture(scope="module")
def secrets() -> ModuleType:
    return load_script("local_secrets")


def write_secrets(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "secrets.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_the_key_from_the_local_secrets_file(secrets: ModuleType, tmp_path: Path) -> None:
    path = write_secrets(tmp_path, f'ANTHROPIC_API_KEY = "{KEY}"\n')

    assert secrets.read_key(path) == KEY


@pytest.mark.parametrize("text", ["", 'ANTHROPIC_API_KEY = ""\n', "ANTHROPIC_API_KEY = 5\n"])
def test_missing_or_empty_key_stops_without_echoing_the_file(
    secrets: ModuleType, tmp_path: Path, text: str
) -> None:
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY is missing"):
        secrets.read_key(write_secrets(tmp_path, text))


def test_missing_secrets_file_stops_clearly(secrets: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="secrets file is missing"):
        secrets.read_key(tmp_path / "absent.toml")


def test_an_empty_key_never_matches_everything(secrets: ModuleType) -> None:
    assert not secrets.contains_key("any text", ["", KEY])
    assert secrets.contains_key(f"has {KEY}", [KEY])
