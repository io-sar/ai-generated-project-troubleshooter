import pytest

from troubleshooter.domain.codes import EscalationLevel
from troubleshooter.domain.models import Risk
from troubleshooter.domain.scoring import risk_score, suggested_escalation

from .report_data import risk_data

TEAM, PM = EscalationLevel.TEAM, EscalationLevel.PM
SPONSOR, STEERING = EscalationLevel.SPONSOR, EscalationLevel.STEERING


@pytest.mark.parametrize(
    ("likelihood", "impact", "score"),
    [(1, 1, 1), (2, 3, 6), (3, 2, 6), (4, 5, 20), (5, 5, 25)],
)
def test_risk_score_is_likelihood_times_impact(likelihood: int, impact: int, score: int) -> None:
    assert risk_score(Risk.model_validate(risk_data(likelihood, impact))) == score


def test_risk_score_recalculates_after_an_edit() -> None:
    risk = Risk.model_validate(risk_data(likelihood=2, impact=2))
    edited = risk.model_copy(update={"likelihood": 5})

    assert (risk_score(risk), risk_score(edited)) == (4, 10)


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (1, TEAM),
        (4, TEAM),
        (5, PM),
        (9, PM),
        (10, SPONSOR),
        (16, SPONSOR),
        (17, STEERING),
        (25, STEERING),
    ],
)
def test_suggested_escalation_at_band_edges(score: int, level: EscalationLevel) -> None:
    assert suggested_escalation(score) is level


def test_every_reachable_score_maps_as_decided() -> None:
    # Only products of two numbers from 1 to 5 can occur; this pins the whole table.
    ratings = range(1, 6)
    reachable = sorted({likelihood * impact for likelihood in ratings for impact in ratings})
    by_level: dict[EscalationLevel, list[int]] = {}
    for score in reachable:
        by_level.setdefault(suggested_escalation(score), []).append(score)

    assert by_level == {
        TEAM: [1, 2, 3, 4],
        PM: [5, 6, 8, 9],
        SPONSOR: [10, 12, 15, 16],
        STEERING: [20, 25],
    }


@pytest.mark.parametrize("score", [0, -1])
def test_score_below_1_is_an_error(score: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        suggested_escalation(score)
