"""The report schema that every engine returns.

Model docstrings become schema descriptions that the LLM reads, so they describe the data
only. Notes for developers go in comments.

Models are frozen, so only `ui/state.py` changes a report, by making an updated copy.
Unknown fields are rejected, so LLM output can't carry extra data past validation.
Derived values (labels, overall rating, risk score) are calculated in `scoring`, not stored.
"""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.json_schema import SkipJsonSchema

from troubleshooter.domain.codes import (
    EscalationLevel,
    InputClassification,
    ProjectType,
    RaciCode,
    ReportSource,
)

SCENARIO_MAX_CHARS = 4000
SCORE_MIN, SCORE_MAX = 0, 100
RATING_MIN, RATING_MAX = 1, 5

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Score = Annotated[int, Field(ge=SCORE_MIN, le=SCORE_MAX)]
Rating = Annotated[int, Field(ge=RATING_MIN, le=RATING_MAX)]

# Human edits live on the report so the app and the export read one object (ADR 0005).
# They are left out of the JSON Schema, so the LLM is never offered them.
HumanAdjusted = SkipJsonSchema[bool]
HumanNote = SkipJsonSchema[Text | None]
# The schema hides these, but Pydantic still accepts them, so an LLM answer that sets any of
# them is rejected before validation.
HUMAN_FIELDS = frozenset({"human_adjusted", "note"})


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Scenario(DomainModel):
    project_type: ProjectType
    text: Annotated[Text, StringConstraints(max_length=SCENARIO_MAX_CHARS)]
    # Only samples have key points; a Live scenario is the visitor's free text.
    key_points: list[Text] = []


class Signal(DomainModel):
    """One fact from the scenario that points to a problem. Risks link back by `id`."""

    id: Text
    observation: Text
    evidence: Text


class Diagnosis(DomainModel):
    classification: InputClassification
    summary: Text
    signals: list[Signal]
    things_to_watch: list[Text]


class DimensionHealth(DomainModel):
    score: Score
    rationale: Text
    human_adjusted: HumanAdjusted = False
    # The visitor's note sits beside the AI rationale, which stays unchanged.
    note: HumanNote = None


class HealthScores(DomainModel):
    schedule: DimensionHealth
    scope: DimensionHealth
    quality: DimensionHealth
    risk_control: DimensionHealth
    stakeholder_confidence: DimensionHealth


class Risk(DomainModel):
    id: Text
    description: Text
    likelihood: Rating
    impact: Rating
    owner: Text
    mitigation: Text
    escalation: EscalationLevel
    signal_ids: list[Text]
    human_adjusted: HumanAdjusted = False


class Action(DomainModel):
    description: Text
    owner: Text
    success_signal: Text


class Sprint(DomainModel):
    goal: Text
    actions: Annotated[list[Action], Field(min_length=1)]


class RecoveryPlan(DomainModel):
    """Three two-week sprints over six weeks, in this order."""

    stabilize: Sprint
    recover: Sprint
    sustain: Sprint


class StakeholderUpdates(DomainModel):
    executive: Text
    delivery_team: Text
    customer: Text


class DecisionOption(DomainModel):
    title: Text
    trade_offs: Text


class DecisionMemo(DomainModel):
    context: Text
    options: Annotated[list[DecisionOption], Field(min_length=2, max_length=4)]
    recommendation: Text
    success_metrics: Annotated[list[Text], Field(min_length=1)]


class RaciAssignment(DomainModel):
    role: Text
    code: RaciCode


class RaciRow(DomainModel):
    """One activity. Roles left out have no part in it."""

    # The one-A rule is checked in `raci`, not here, because a broken row must still load
    # so the app can show a warning instead of rejecting the report.
    activity: Text
    assignments: list[RaciAssignment]
    human_adjusted: HumanAdjusted = False


class Report(DomainModel):
    health: HealthScores
    risks: list[Risk]
    recovery_plan: RecoveryPlan
    stakeholder_updates: StakeholderUpdates
    decision_memo: DecisionMemo
    raci: list[RaciRow]


# Not sent to an LLM, so these docstrings are for developers.
class RunInfo(DomainModel):
    """How a sample was recorded: the model and prompt versions behind its diagnosis and draft.

    `prompt_versions` maps each stage's prompt ID to its version, such as {"diagnose": "v1"}.
    """

    provider: Text
    model: Text
    prompt_versions: dict[Text, Text]
    recorded_on: date


class Sample(DomainModel):
    """A stored demo run: the scenario, the AI's diagnosis and draft, and the final version.

    `changes` is the "What I changed" note, in Markdown. `run` is missing for the
    placeholder sample, which wasn't recorded from a model.
    """

    id: Text
    title: Text
    badge: ReportSource
    scenario: Scenario
    diagnosis: Diagnosis
    draft: Report
    final: Report
    changes: Text
    run: RunInfo | None = None

    @field_validator("badge")
    @classmethod
    def _badge_is_not_live(cls, badge: ReportSource) -> ReportSource:
        if badge is ReportSource.LIVE:
            raise ValueError("a sample is a stored run, so its badge can't be live")
        return badge
