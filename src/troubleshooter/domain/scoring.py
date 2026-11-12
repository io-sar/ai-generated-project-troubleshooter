"""Health scoring rules, decided in issue #14 and recorded in ADR 0001.

Scores run 0-100 and higher is always healthier. These are pure functions, so the overall
rating recalculates whenever a score changes.
"""

from troubleshooter.domain.codes import Dimension, HealthLabel
from troubleshooter.domain.models import HealthScores

GOOD_MIN_SCORE = 70
PROBLEMATIC_MIN_SCORE = 40

# The score a dimension takes when a person overrides its label. Each sits inside its band.
LABEL_SCORES: dict[HealthLabel, int] = {
    HealthLabel.GOOD: 85,
    HealthLabel.PROBLEMATIC: 55,
    HealthLabel.AT_RISK: 25,
}


def label_for(score: int) -> HealthLabel:
    if score >= GOOD_MIN_SCORE:
        return HealthLabel.GOOD
    if score >= PROBLEMATIC_MIN_SCORE:
        return HealthLabel.PROBLEMATIC
    return HealthLabel.AT_RISK


def score_for(label: HealthLabel) -> int:
    return LABEL_SCORES[label]


def dimension_scores(health: HealthScores) -> dict[Dimension, int]:
    return {dimension: getattr(health, dimension.value).score for dimension in Dimension}


def overall_score(health: HealthScores) -> int:
    """Equal-weight average of the five dimensions.

    The sum of five whole numbers divided by 5 never ends in .5, so rounding has no ties.
    """
    scores = dimension_scores(health).values()
    return round(sum(scores) / len(scores))


def overall_label(health: HealthScores) -> HealthLabel:
    """The overall label, which can't be Good while any dimension is At Risk.

    Without this cap, an average could hide one failing dimension behind four healthy ones.
    """
    label = label_for(overall_score(health))
    has_at_risk = any(
        label_for(score) is HealthLabel.AT_RISK for score in dimension_scores(health).values()
    )
    if label is HealthLabel.GOOD and has_at_risk:
        return HealthLabel.PROBLEMATIC
    return label
