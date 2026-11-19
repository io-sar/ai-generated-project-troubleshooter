"""Schema and invariant checks on the sample files that ship with the app."""

import pytest

from troubleshooter.config import SAMPLES_DIR
from troubleshooter.domain.codes import ReportSource
from troubleshooter.domain.models import Report, Sample
from troubleshooter.domain.raci import rows_without_one_accountable
from troubleshooter.engines.sample_engine import (
    RUN_FILE,
    list_sample_ids,
    list_samples_in_review,
    load_sample,
)

SAMPLE_IDS = list_sample_ids(SAMPLES_DIR)


def reports(sample: Sample) -> dict[str, Report]:
    return {"draft": sample.draft, "final": sample.final}


def test_at_least_one_sample_ships() -> None:
    assert SAMPLE_IDS


def test_samples_in_review_hold_their_recorded_files() -> None:
    # A folder is either a reviewed sample or a recording waiting for the author's review.
    for sample_id in list_samples_in_review(SAMPLES_DIR):
        folder = SAMPLES_DIR / sample_id
        assert (folder / "diagnosis.json").is_file(), sample_id
        assert (folder / RUN_FILE).is_file(), sample_id


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_sample_matches_the_schema(sample_id: str) -> None:
    assert load_sample(SAMPLES_DIR, sample_id).id == sample_id


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_every_raci_row_has_one_accountable(sample_id: str) -> None:
    sample = load_sample(SAMPLES_DIR, sample_id)

    for version, report in reports(sample).items():
        assert rows_without_one_accountable(report.raci) == [], version


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_risk_signal_ids_exist_in_the_diagnosis(sample_id: str) -> None:
    sample = load_sample(SAMPLES_DIR, sample_id)
    known = {signal.id for signal in sample.diagnosis.signals}

    for version, report in reports(sample).items():
        for risk in report.risks:
            assert set(risk.signal_ids) <= known, f"{version} {risk.id}"


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_ids_are_unique(sample_id: str) -> None:
    sample = load_sample(SAMPLES_DIR, sample_id)
    signal_ids = [signal.id for signal in sample.diagnosis.signals]

    assert len(signal_ids) == len(set(signal_ids))
    for version, report in reports(sample).items():
        risk_ids = [risk.id for risk in report.risks]
        assert len(risk_ids) == len(set(risk_ids)), version


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_final_differs_from_draft(sample_id: str) -> None:
    sample = load_sample(SAMPLES_DIR, sample_id)

    assert sample.final != sample.draft


def test_placeholder_is_labelled_as_one() -> None:
    assert load_sample(SAMPLES_DIR, "placeholder").badge is ReportSource.PLACEHOLDER
