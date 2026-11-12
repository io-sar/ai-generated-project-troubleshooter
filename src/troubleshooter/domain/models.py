"""The report schema that every engine returns.

Models are frozen, so only `ui/state.py` changes a report, by making an updated copy.
Unknown fields are rejected, so LLM output can't carry extra data past validation.
Derived values (labels, overall rating, risk score) are calculated in `scoring`, not stored.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from troubleshooter.domain.codes import (
    EscalationLevel,
    InputClassification,
    ProjectType,
    RaciCode,
)

SCENARIO_MAX_CHARS = 4000

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Score = Annotated[int, Field(ge=0, le=100)]
Rating = Annotated[int, Field(ge=1, le=5)]


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
    """One activity. Roles left out have no part in it.

    The one-A rule is checked in `raci`, not here, because a broken row must still load
    so the app can show a warning instead of rejecting the report.
    """

    activity: Text
    assignments: list[RaciAssignment]


class Report(DomainModel):
    health: HealthScores
    risks: list[Risk]
    recovery_plan: RecoveryPlan
    stakeholder_updates: StakeholderUpdates
    decision_memo: DecisionMemo
    raci: list[RaciRow]
