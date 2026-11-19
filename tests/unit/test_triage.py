import pytest

from troubleshooter.domain.codes import InputClassification
from troubleshooter.domain.models import Diagnosis
from troubleshooter.domain.triage import needs_report

NEEDS_REPORT = {
    InputClassification.TROUBLED: True,
    InputClassification.HEALTHY: False,
    InputClassification.TOO_THIN: False,
    InputClassification.OFF_TOPIC: False,
}


def diagnosis(classification: InputClassification) -> Diagnosis:
    return Diagnosis(
        classification=classification, summary="Summary.", signals=[], things_to_watch=[]
    )


@pytest.mark.parametrize(("classification", "expected"), NEEDS_REPORT.items())
def test_only_a_troubled_project_needs_a_report(
    classification: InputClassification, expected: bool
) -> None:
    assert needs_report(diagnosis(classification)) is expected


def test_every_classification_has_a_decision() -> None:
    # A new classification must get a row above, so its stage 2 behaviour is chosen on purpose.
    assert set(NEEDS_REPORT) == set(InputClassification)
