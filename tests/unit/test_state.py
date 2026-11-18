from typing import Any

import pytest
import streamlit as st

from troubleshooter.domain.codes import Dimension, EscalationLevel, HealthLabel, RaciCode
from troubleshooter.domain.models import Report, Sample
from troubleshooter.domain.scoring import LABEL_SCORES, overall_label, overall_score
from troubleshooter.ui import state
from troubleshooter.ui.state import (
    EditRejected,
    RaciEdit,
    apply_raci_edits,
    apply_risk_edits,
    override_health,
)

from .report_data import diagnosis_data, report_data, risk_data


def original_report() -> Report:
    data = report_data()
    second = risk_data(likelihood=2, impact=2) | {"id": "R2", "signal_ids": []}
    data["risks"].append(second)
    return Report.model_validate(data)


def risk_rows(report: Report) -> list[dict[str, Any]]:
    """The rows the risk editor hands back when nothing has changed."""
    return [risk.model_dump(exclude={"human_adjusted"}) for risk in report.risks]


def raci_edits(report: Report) -> list[RaciEdit]:
    return [
        RaciEdit(row.activity, {a.role: a.code for a in row.assignments}) for row in report.raci
    ]


# Risks


def test_unchanged_risk_rows_keep_the_report_as_it_was() -> None:
    original = original_report()

    assert apply_risk_edits(original, original, risk_rows(original)) == original


def test_edited_risk_is_marked_and_others_are_not() -> None:
    original = original_report()
    rows = risk_rows(original)
    rows[0]["mitigation"] = "Escalate to the vendor's director."

    risks = apply_risk_edits(original, original, rows).risks

    assert risks[0].human_adjusted and risks[0].mitigation == "Escalate to the vendor's director."
    assert not risks[1].human_adjusted


def test_putting_a_value_back_removes_the_marker() -> None:
    original = original_report()
    rows = risk_rows(original)
    rows[0]["impact"] = 1
    edited = apply_risk_edits(original, original, rows)

    rows[0]["impact"] = original.risks[0].impact
    restored = apply_risk_edits(original, edited, rows)

    assert not restored.risks[0].human_adjusted


@pytest.mark.parametrize("missing_id", [None, "", "  "])
def test_added_row_gets_the_next_free_id_and_is_marked(missing_id: str | None) -> None:
    original = original_report()
    new = risk_data(likelihood=1, impact=3) | {"id": missing_id, "signal_ids": None}

    added = apply_risk_edits(original, original, [*risk_rows(original), new]).risks[-1]

    assert (added.id, added.signal_ids, added.human_adjusted) == ("R3", [], True)


def test_added_row_skips_ids_already_in_use() -> None:
    original = original_report()
    rows = risk_rows(original)
    rows[1]["id"] = "R3"  # the editor keeps IDs, so R2 is now free and R3 taken
    new = risk_data() | {"id": None}

    ids = [risk.id for risk in apply_risk_edits(original, original, [*rows, new]).risks]

    assert ids == ["R1", "R3", "R2"]


def test_added_row_without_escalation_gets_the_suggested_level() -> None:
    original = original_report()
    new = risk_data(likelihood=5, impact=4) | {"id": None, "escalation": None}

    added = apply_risk_edits(original, original, [*risk_rows(original), new]).risks[-1]

    assert added.escalation is EscalationLevel.STEERING


def test_escalation_can_differ_from_the_suggested_level() -> None:
    original = original_report()
    rows = risk_rows(original)
    rows[0]["escalation"] = "team"

    risk = apply_risk_edits(original, original, rows).risks[0]

    assert (risk.escalation, risk.human_adjusted) == (EscalationLevel.TEAM, True)


def test_deleted_risk_row_is_removed() -> None:
    original = original_report()

    risks = apply_risk_edits(original, original, risk_rows(original)[1:]).risks

    assert [risk.id for risk in risks] == ["R2"]
    assert not risks[0].human_adjusted


def test_deleting_every_risk_leaves_an_empty_table() -> None:
    original = original_report()

    assert apply_risk_edits(original, original, []).risks == []


def test_risk_edits_keep_other_sections_edits() -> None:
    original = original_report()
    current = override_health(original, original, Dimension.QUALITY, HealthLabel.AT_RISK, None)

    edited = apply_risk_edits(original, current, risk_rows(original))

    assert edited.health == current.health


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("likelihood", 0),
        ("likelihood", 6),
        ("impact", 0),
        ("impact", 6),
        ("likelihood", None),
        ("description", ""),
        ("owner", "   "),
        ("escalation", "board"),
    ],
)
def test_invalid_risk_value_is_rejected_with_its_row_and_field(field: str, value: Any) -> None:
    original = original_report()
    rows = risk_rows(original)
    rows[1][field] = value

    with pytest.raises(EditRejected) as rejected:
        apply_risk_edits(original, original, rows)

    assert (rejected.value.row, rejected.value.field) == (2, field)


def test_duplicate_risk_id_is_rejected() -> None:
    original = original_report()
    rows = risk_rows(original)
    rows[1]["id"] = "R1"

    with pytest.raises(EditRejected) as rejected:
        apply_risk_edits(original, original, rows)

    assert (rejected.value.row, rejected.value.field) == (2, "id")


def test_rejection_message_holds_no_report_text() -> None:
    # The message may reach logs, so it names the place only, never the visitor's text.
    original = original_report()
    rows = risk_rows(original)
    rows[0]["escalation"] = "secret plan"

    with pytest.raises(EditRejected) as rejected:
        apply_risk_edits(original, original, rows)

    assert "secret plan" not in str(rejected.value)


# RACI


def test_unchanged_raci_rows_keep_the_report_as_it_was() -> None:
    original = original_report()

    assert apply_raci_edits(original, original, raci_edits(original)) == original


def test_role_order_does_not_count_as_a_change() -> None:
    original = original_report()
    row = original.raci[0]
    reordered = RaciEdit(row.activity, {a.role: a.code for a in reversed(row.assignments)})

    assert apply_raci_edits(original, original, [reordered]) == original


def test_changed_code_marks_the_raci_row() -> None:
    original = original_report()
    edit = RaciEdit("Vendor follow-up", {"PM": "A", "Vendor manager": "C"})

    row = apply_raci_edits(original, original, [edit]).raci[0]

    assert row.human_adjusted
    assert {a.role: a.code for a in row.assignments}["Vendor manager"] is RaciCode.CONSULTED


@pytest.mark.parametrize("empty", [None, ""])
def test_empty_cells_are_dropped(empty: str | None) -> None:
    original = original_report()
    edit = RaciEdit("Vendor follow-up", {"PM": "A", "Vendor manager": empty})

    row = apply_raci_edits(original, original, [edit]).raci[0]

    assert [a.role for a in row.assignments] == ["PM"]
    assert row.human_adjusted


def test_renamed_activity_counts_as_a_change() -> None:
    original = original_report()
    edit = RaciEdit("Vendor escalation", {"PM": "A", "Vendor manager": "R"})

    assert apply_raci_edits(original, original, [edit]).raci[0].human_adjusted


def test_added_raci_row_is_marked() -> None:
    original = original_report()
    new = RaciEdit("Release sign-off", {"PM": "A"})

    raci = apply_raci_edits(original, original, [*raci_edits(original), new]).raci

    assert [row.human_adjusted for row in raci] == [False, True]


def test_copied_raci_row_is_marked_as_added() -> None:
    original = original_report()
    rows = raci_edits(original)

    raci = apply_raci_edits(original, original, [*rows, *rows]).raci

    assert [row.human_adjusted for row in raci] == [False, True]


def test_raci_row_breaking_the_one_a_rule_is_kept() -> None:
    # The one-A rule is a warning shown by the app, not a reason to reject the edit.
    original = original_report()
    edit = RaciEdit("Vendor follow-up", {"PM": "A", "Vendor manager": "A"})

    row = apply_raci_edits(original, original, [edit]).raci[0]

    assert [a.code for a in row.assignments] == [RaciCode.ACCOUNTABLE] * 2


def test_deleting_every_raci_row_leaves_an_empty_table() -> None:
    original = original_report()

    assert apply_raci_edits(original, original, []).raci == []


@pytest.mark.parametrize(
    ("edit", "field"),
    [
        (RaciEdit("", {"PM": "A"}), "activity"),
        (RaciEdit(None, {"PM": "A"}), "activity"),
        (RaciEdit("Vendor follow-up", {"PM": "X"}), "PM"),
    ],
)
def test_invalid_raci_value_is_rejected_with_its_row_and_field(edit: RaciEdit, field: str) -> None:
    original = original_report()

    with pytest.raises(EditRejected) as rejected:
        apply_raci_edits(original, original, [*raci_edits(original), edit])

    assert (rejected.value.row, rejected.value.field) == (2, field)


# Health


def test_label_override_sets_the_label_score_and_marks_it() -> None:
    original = original_report()

    edited = override_health(original, original, Dimension.QUALITY, HealthLabel.AT_RISK, None)

    quality = edited.health.quality
    assert (quality.score, quality.human_adjusted) == (LABEL_SCORES[HealthLabel.AT_RISK], True)
    assert quality.rationale == original.health.quality.rationale


def test_label_override_recalculates_the_overall_rating() -> None:
    original = original_report()  # scores 30, 55, 75, 45, 60: overall 53, Problematic

    edited = override_health(original, original, Dimension.SCHEDULE, HealthLabel.GOOD, None)

    assert overall_score(original.health) == 53
    assert overall_score(edited.health) == 64
    assert overall_label(edited.health) is HealthLabel.PROBLEMATIC


def test_note_without_a_label_change_keeps_the_ai_score() -> None:
    original = original_report()

    edited = override_health(
        original, original, Dimension.QUALITY, HealthLabel.GOOD, "  Tests are green.  "
    )

    quality = edited.health.quality
    assert (quality.score, quality.note) == (original.health.quality.score, "Tests are green.")
    assert quality.human_adjusted


def test_choosing_the_ai_label_with_no_note_restores_the_original() -> None:
    original = original_report()
    edited = override_health(original, original, Dimension.QUALITY, HealthLabel.AT_RISK, "Hm.")

    restored = override_health(original, edited, Dimension.QUALITY, HealthLabel.GOOD, "  ")

    assert restored == original


def test_health_override_keeps_other_edits() -> None:
    original = original_report()
    rows = risk_rows(original)[1:]
    current = apply_risk_edits(original, original, rows)

    edited = override_health(original, current, Dimension.SCOPE, HealthLabel.GOOD, None)

    assert edited.risks == current.risks


# Session


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    fake: dict[str, Any] = {}
    monkeypatch.setattr(st, "session_state", fake)
    return fake


def make_sample(sample_id: str = "vendor") -> Sample:
    report = original_report()
    return Sample.model_validate(
        {
            "id": sample_id,
            "title": "Vendor slipping",
            "badge": "placeholder",
            "scenario": {"project_type": "software_delivery", "text": "The vendor is late."},
            "diagnosis": diagnosis_data(),
            "draft": report.model_dump(),
            "final": report.model_dump(),
            "changes": "Nothing yet.",
        }
    )


@pytest.mark.usefixtures("session")
def test_shown_report_is_none_before_a_sample_is_shown() -> None:
    assert state.shown_report() is None


@pytest.mark.usefixtures("session")
def test_shown_report_is_the_final_version_until_edited() -> None:
    sample = make_sample()
    state.show_sample(sample)

    assert state.shown_report() == sample.final


@pytest.mark.usefixtures("session")
def test_saved_edits_build_on_each_other() -> None:
    sample = make_sample()
    state.show_sample(sample)

    state.save_risk_edits(risk_rows(sample.final)[1:])
    state.save_raci_edits([])
    state.save_health_override(Dimension.QUALITY, HealthLabel.AT_RISK, None)

    shown = state.shown_report()
    assert shown is not None
    assert ([r.id for r in shown.risks], shown.raci) == (["R2"], [])
    assert shown.health.quality.human_adjusted


@pytest.mark.usefixtures("session")
def test_showing_a_sample_clears_earlier_edits() -> None:
    state.show_sample(make_sample("vendor"))
    state.save_risk_edits([])

    other = make_sample("launch")
    state.show_sample(other)

    assert state.shown_report() == other.final


@pytest.mark.usefixtures("session")
def test_rejected_edit_leaves_the_shown_report_unchanged() -> None:
    sample = make_sample()
    state.show_sample(sample)
    state.save_risk_edits(risk_rows(sample.final)[1:])
    before = state.shown_report()
    rows = risk_rows(sample.final)
    rows[0]["impact"] = 9

    with pytest.raises(EditRejected):
        state.save_risk_edits(rows)

    assert state.shown_report() == before


@pytest.mark.usefixtures("session")
def test_saving_without_a_shown_sample_fails_clearly() -> None:
    with pytest.raises(LookupError, match="no sample"):
        state.save_risk_edits([])


@pytest.mark.usefixtures("session")
def test_editor_key_changes_when_the_report_changes() -> None:
    sample = make_sample()
    state.show_sample(sample)
    shown = state.editor_key("risks")

    assert state.editor_key("risks") == shown
    state.save_risk_edits([])
    saved = state.editor_key("risks")
    state.show_sample(sample)

    assert len({shown, saved, state.editor_key("risks")}) == 3


@pytest.mark.usefixtures("session")
def test_rejected_edit_keeps_the_editor_key() -> None:
    # The same key keeps the visitor's pending changes in the table, so they can fix them.
    state.show_sample(make_sample())
    before = state.editor_key("risks")

    with pytest.raises(EditRejected):
        state.save_risk_edits([risk_data(likelihood=9)])

    assert state.editor_key("risks") == before


def test_drafts_are_never_edited(session: dict[str, Any]) -> None:
    sample = make_sample()
    state.show_sample(sample)

    state.save_risk_edits([])

    shown = state.shown_sample()
    assert shown is not None and shown.draft == sample.draft
