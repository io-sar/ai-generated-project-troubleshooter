"""Record a sample's diagnosis and AI draft from the real pipeline. Local only; costs money.

Run with: uv run python scripts/record_sample.py SAMPLE_ID [--model MODEL] [--overwrite]

The sample folder must already hold the author's scenario.yaml. The script runs stage 1,
then stage 2 only for a troubled project, and saves diagnosis.json, draft.json (if a report
was made) and run.json. The sample stays in review until the author adds final.json and
changes.md (M5). Recorded files are never hand-edited, so the script refuses to replace
them unless --overwrite is given.

The key is read from the gitignored local secrets file, never printed, and checked against
every file before anything is saved.
"""

import argparse
import logging
import sys
from dataclasses import fields
from datetime import date
from pathlib import Path

import yaml
from local_secrets import contains_key, read_key

from troubleshooter import config
from troubleshooter.domain.codes import ReportSource
from troubleshooter.domain.models import Diagnosis, Report, RunInfo, Scenario
from troubleshooter.domain.triage import needs_report
from troubleshooter.engines.llm_engine import LLMEngine, Prompts
from troubleshooter.engines.prompts import load_prompts, prompt_fingerprint
from troubleshooter.engines.sample_engine import RUN_FILE
from troubleshooter.llm.base import Provider
from troubleshooter.llm.factory import create_client
from troubleshooter.llm.logs import quiet_sdk_loggers

RECORDED_FILES = ("diagnosis.json", "draft.json", RUN_FILE)

logger = logging.getLogger("record_sample")


def record(engine: LLMEngine, scenario: Scenario) -> tuple[Diagnosis, Report | None]:
    """Run both stages, skipping stage 2 when the project needs no report."""
    diagnosis = engine.diagnose(scenario)
    report = engine.generate(scenario, diagnosis) if needs_report(diagnosis) else None
    return diagnosis, report


def run_info(
    provider: Provider, model: str, prompts: Prompts, on: date, root: Path = config.PROMPTS_DIR
) -> RunInfo:
    """Describe the run: the provider, model, and every prompt version the engine had.

    Each prompt file's fingerprint is kept too, so a later edit to it can be caught.
    """
    versions = {
        getattr(prompts, f.name).id: getattr(prompts, f.name).version for f in fields(prompts)
    }
    return RunInfo(
        provider=provider.value,
        model=model,
        prompt_versions=versions,
        prompt_fingerprints={
            prompt_id: prompt_fingerprint(root, prompt_id, version)
            for prompt_id, version in versions.items()
        },
        recorded_on=on,
    )


def sample_files(diagnosis: Diagnosis, report: Report | None, run: RunInfo) -> dict[str, str]:
    """Return each recorded file's name and text.

    The draft leaves out the fields only people set, which are always unset in a draft, so
    the file holds exactly the model's report.
    """
    files = {
        "diagnosis.json": diagnosis.model_dump_json(indent=2),
        RUN_FILE: run.model_dump_json(indent=2),
    }
    if report is not None:
        files["draft.json"] = report.model_dump_json(indent=2, exclude_defaults=True)
    return {name: text + "\n" for name, text in files.items()}


def save(folder: Path, files: dict[str, str], keys: list[str], overwrite: bool) -> None:
    """Write the recorded files, or stop before writing anything.

    Stops when a file would contain a key, or when recorded files exist and `overwrite`
    isn't set. With `overwrite`, a draft left from an earlier run is removed if this run
    made none, so the folder never mixes two runs.
    """
    if any(contains_key(text, keys) for text in files.values()):
        raise SystemExit("Stopped: a recorded file would contain the key")
    existing = [name for name in RECORDED_FILES if (folder / name).exists()]
    if existing and not overwrite:
        raise SystemExit(f"Already recorded: {', '.join(existing)}. Use --overwrite to replace.")
    for name in existing:
        if name not in files:
            (folder / name).unlink()
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")


def read_scenario(folder: Path) -> Scenario:
    """Return the author's scenario from the sample folder, refusing the placeholder."""
    meta_path = folder / "scenario.yaml"
    if not meta_path.is_file():
        raise SystemExit(f"No scenario.yaml in {folder.name}. Write the scenario first.")
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise SystemExit(f"{folder.name}/scenario.yaml is not a mapping")
    if meta.get("badge") == ReportSource.PLACEHOLDER.value:
        raise SystemExit("The placeholder sample is hand-written and is never recorded over")
    return Scenario.model_validate(meta.get("scenario"))


def main() -> int:
    """Record one sample with the chosen model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample_id", help="The sample folder under the samples directory.")
    parser.add_argument(
        "--provider", default=Provider.ANTHROPIC.value, choices=[p.value for p in Provider]
    )
    parser.add_argument(
        "--model", help="A model from config.MODELS (default: the provider's default)."
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace earlier recorded files.")
    parser.add_argument("--samples-dir", type=Path, default=config.SAMPLES_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    quiet_sdk_loggers()

    provider = Provider(args.provider)
    model = args.model or config.MODELS[provider.value].default
    folder = args.samples_dir / args.sample_id
    scenario = read_scenario(folder)
    key = read_key()
    prompts = load_prompts()
    engine = LLMEngine(create_client(provider, key, model), prompts)

    diagnosis, report = record(engine, scenario)
    files = sample_files(diagnosis, report, run_info(provider, model, prompts, date.today()))
    save(folder, files, [key], args.overwrite)
    logger.info(
        "recorded sample=%s model=%s classification=%s files=%s",
        args.sample_id,
        model,
        diagnosis.classification.value,
        ",".join(sorted(files)),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
