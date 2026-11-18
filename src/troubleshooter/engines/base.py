"""The engine contract shared by every analysis mode."""

from typing import Protocol

from troubleshooter.domain.models import Diagnosis, Report, Scenario


class AnalysisEngine(Protocol):
    """Turns a scenario into a diagnosis, then into the AI's report."""

    def diagnose(self, scenario: Scenario) -> Diagnosis:
        """Return what is wrong with the project, and whether it's a troubled project at all."""
        ...

    def generate(self, scenario: Scenario, diagnosis: Diagnosis) -> Report:
        """Return the AI's report for a troubled project."""
        ...
