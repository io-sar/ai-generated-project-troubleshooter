import pytest

from troubleshooter.domain.codes import Dimension, HealthLabel
from troubleshooter.domain.models import DimensionHealth, HealthScores
from troubleshooter.domain.scoring import (
    dimension_scores,
    label_for,
    overall_label,
    overall_score,
    score_for,
)

GOOD, PROBLEMATIC, AT_RISK = HealthLabel.GOOD, HealthLabel.PROBLEMATIC, HealthLabel.AT_RISK


def make_health(*scores: int) -> HealthScores:
    """Health with scores in Dimension order: schedule, scope, quality, risk control, confidence."""
    return HealthScores.model_validate(
        {
            dimension.value: {"score": score, "rationale": "Because."}
            for dimension, score in zip(Dimension, scores, strict=True)
        }
    )


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (0, AT_RISK),
        (39, AT_RISK),
        (40, PROBLEMATIC),
        (69, PROBLEMATIC),
        (70, GOOD),
        (100, GOOD),
    ],
)
def test_label_for_score_at_band_edges(score: int, label: HealthLabel) -> None:
    assert label_for(score) is label


@pytest.mark.parametrize("label", list(HealthLabel))
def test_label_score_sits_inside_its_own_band(label: HealthLabel) -> None:
    assert label_for(score_for(label)) is label


def test_label_scores_match_the_decision() -> None:
    assert [score_for(label) for label in (GOOD, PROBLEMATIC, AT_RISK)] == [85, 55, 15]


def test_dimension_codes_match_health_score_fields() -> None:
    # dimension_scores reads fields by code, so the two must stay in step.
    assert set(HealthScores.model_fields) == {dimension.value for dimension in Dimension}


def test_dimension_scores_are_keyed_by_dimension() -> None:
    scores = dimension_scores(make_health(10, 20, 30, 40, 50))

    assert scores == {
        Dimension.SCHEDULE: 10,
        Dimension.SCOPE: 20,
        Dimension.QUALITY: 30,
        Dimension.RISK_CONTROL: 40,
        Dimension.STAKEHOLDER_CONFIDENCE: 50,
    }


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ((0, 0, 0, 0, 0), 0),
        ((100, 100, 100, 100, 100), 100),
        ((10, 20, 30, 40, 50), 30),
        ((70, 70, 70, 70, 71), 70),  # 70.2 rounds down
        ((70, 70, 70, 71, 71), 70),  # 70.4 rounds down
        ((70, 70, 71, 71, 71), 71),  # 70.6 rounds up
    ],
)
def test_overall_score_is_the_rounded_equal_weight_average(
    scores: tuple[int, ...], expected: int
) -> None:
    assert overall_score(make_health(*scores)) == expected


@pytest.mark.parametrize(
    ("scores", "label"),
    [
        ((39, 39, 39, 39, 41), AT_RISK),  # 39.4 rounds to 39
        ((40, 40, 40, 40, 40), PROBLEMATIC),
        ((69, 69, 69, 69, 71), PROBLEMATIC),  # 69.4 rounds to 69
        ((70, 70, 70, 70, 70), GOOD),
        ((69, 69, 70, 70, 71), GOOD),  # 69.8 rounds to 70
    ],
)
def test_overall_label_at_band_edges(scores: tuple[int, ...], label: HealthLabel) -> None:
    assert overall_label(make_health(*scores)) is label


def test_overall_good_is_capped_when_a_dimension_is_at_risk() -> None:
    health = make_health(90, 90, 90, 90, 20)

    assert overall_score(health) == 76
    assert overall_label(health) is PROBLEMATIC


def test_cap_applies_at_the_at_risk_edge_only() -> None:
    assert overall_label(make_health(100, 100, 100, 100, 39)) is PROBLEMATIC
    assert overall_label(make_health(100, 100, 100, 100, 40)) is GOOD


def test_cap_never_raises_a_lower_overall() -> None:
    assert overall_label(make_health(20, 20, 20, 20, 90)) is AT_RISK


def test_overall_recalculates_after_a_label_override() -> None:
    health = make_health(90, 90, 90, 90, 90)
    assert overall_label(health) is GOOD

    override = DimensionHealth(score=score_for(AT_RISK), rationale="Two outages this week.")
    overridden = health.model_copy(update={"quality": override})

    assert overall_score(overridden) == 75  # (90 * 4 + 15) / 5
    assert overall_label(overridden) is PROBLEMATIC  # 75 alone is Good; the red cap applies
