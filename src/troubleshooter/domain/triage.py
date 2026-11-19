"""Which inputs go on to a full report. The one place this rule lives."""

from troubleshooter.domain.codes import InputClassification
from troubleshooter.domain.models import Diagnosis


def needs_report(diagnosis: Diagnosis) -> bool:
    """Return True when stage 2 should run: only a troubled project gets a full report.

    Healthy, too thin and off-topic inputs get a short result built from the diagnosis.
    """
    return diagnosis.classification is InputClassification.TROUBLED
