"""The only layer that reads or changes the report in `st.session_state`.

Each visitor's report lives in their own session, never in shared state.

Edits are applied by pure functions, which take the sample's original final version and
return a new report. An item is marked human-adjusted exactly when it differs from the same
item in that original, so putting a value back removes the marker. Only the final version is
ever edited; the AI draft stays as it was recorded.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import streamlit as st
from pydantic import ValidationError

from troubleshooter.domain.codes import Dimension, EscalationLevel, HealthLabel
from troubleshooter.domain.models import DimensionHealth, RaciRow, Report, Risk, Sample
from troubleshooter.domain.scoring import label_for, risk_score, score_for, suggested_escalation

_SAMPLE_KEY = "shown_sample"
_EDITED_KEY = "edited_report"
_EDIT_VERSION_KEY = "edit_version"

# The risk fields a visitor's row may set. Anything else in the row, such as a display-only
# risk score column, is not part of the risk.
RISK_EDIT_FIELDS = (
    "id",
    "description",
    "likelihood",
    "impact",
    "owner",
    "mitigation",
    "escalation",
    "signal_ids",
)
NEW_RISK_ID_PREFIX = "R"
# The risk cells a visitor can type in. A row with all of them blank is empty and dropped;
# the ID and signal links are read-only, so they don't count.
RISK_VISITOR_FIELDS = ("description", "likelihood", "impact", "owner", "mitigation", "escalation")


class EditRejected(ValueError):
    """A visitor's edit doesn't fit the report schema, so the report was left unchanged.

    `row` counts from 1, as the visitor sees the table. `field` is the column: a risk field,
    `activity`, or a RACI role name.
    """

    def __init__(self, row: int, field: str) -> None:
        # The message names the row only: field values and role names are report text,
        # which must never reach logs.
        super().__init__(f"Invalid value in row {row}")
        self.row = row
        self.field = field


@dataclass(frozen=True)
class RaciEdit:
    """One row from the RACI editor: the activity and the code each role holds in it.

    A role with no part in the activity has None or an empty string.
    """

    activity: str | None
    codes: Mapping[str, str | None]


# Pure edits


def apply_risk_edits(
    original: Report, current: Report, rows: Sequence[Mapping[str, Any]]
) -> Report:
    """Replace the risk register with the visitor's rows.

    Args:
        original: the sample's final version as recorded, used to decide what changed.
        current: the report with the visitor's earlier edits, whose other sections are kept.
        rows: the editor's rows, in order. A row whose visitor cells are all blank is empty
            and dropped. A row with no ID is new and gets the next free ID; a row with no
            escalation gets the level its risk score suggests.

    Returns:
        A new report with the edited register and changed rows marked.

    Raises:
        EditRejected: a row has an invalid value or repeats another row's ID. The row
            number counts every row the visitor sees, empty ones included.
    """
    originals = {risk.id: risk for risk in original.risks}
    kept = [
        (number, row)
        for number, row in enumerate(rows, start=1)
        if not all(_is_blank(row.get(field)) for field in RISK_VISITOR_FIELDS)
    ]
    ids = _risk_ids(kept)
    risks = [
        _mark(_risk_from_row(row, risk_id, number, originals), originals.get(risk_id))
        for (number, row), risk_id in zip(kept, ids, strict=True)
    ]
    return current.model_copy(update={"risks": risks})


def apply_raci_edits(original: Report, current: Report, rows: Sequence[RaciEdit]) -> Report:
    """Replace the RACI matrix with the visitor's rows.

    Rows are matched to the original by activity, so renaming an activity marks its row.
    Rows that break the one-A rule are kept, because that rule is a warning. A row with a
    blank activity and no codes is empty and dropped.

    Raises:
        EditRejected: a row has a blank activity or an unknown code. The row number counts
            every row the visitor sees, empty ones included.
    """
    # Each original row matches one edited row at most, so a copied row counts as added.
    originals = {row.activity: row for row in reversed(original.raci)}
    raci = [
        _raci_from_edit(edit, number, originals)
        for number, edit in enumerate(rows, start=1)
        if not (_is_blank(edit.activity) and all(_is_blank(code) for code in edit.codes.values()))
    ]
    return current.model_copy(update={"raci": raci})


def override_health(
    original: Report,
    current: Report,
    dimension: Dimension,
    label: HealthLabel,
    note: str | None,
) -> Report:
    """Set one dimension's label and optional note, keeping the AI rationale.

    A new label takes that label's fixed score. Keeping the AI's label with a note keeps
    the AI's score. Keeping it with no note restores the original dimension.
    """
    ai = getattr(original.health, dimension.value)
    note = note.strip() if note and note.strip() else None
    changes_label = label is not label_for(ai.score)
    if not changes_label and note is None:
        updated: DimensionHealth = ai
    else:
        score = score_for(label) if changes_label else ai.score
        updated = ai.model_copy(update={"score": score, "human_adjusted": True, "note": note})
    health = current.health.model_copy(update={dimension.value: updated})
    return current.model_copy(update={"health": health})


def _is_blank(value: Any) -> bool:
    """True for a cell the visitor left empty: None, blank text, or a number cell's NaN."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return isinstance(value, float) and math.isnan(value)


def _risk_ids(rows: Sequence[tuple[int, Mapping[str, Any]]]) -> list[str]:
    """Each numbered row's ID, with new IDs for rows that have none."""
    given = [str(row.get("id") or "").strip() for _, row in rows]
    seen: set[str] = set()
    for (number, _), risk_id in zip(rows, given, strict=True):
        if risk_id in seen:
            raise EditRejected(number, "id")
        if risk_id:
            seen.add(risk_id)
    free = (f"{NEW_RISK_ID_PREFIX}{n}" for n in range(1, len(rows) + len(seen) + 2))
    unused = (risk_id for risk_id in free if risk_id not in seen)
    return [risk_id or next(unused) for risk_id in given]


def _risk_from_row(
    row: Mapping[str, Any], risk_id: str, number: int, originals: Mapping[str, Risk]
) -> Risk:
    data = {field: row.get(field) for field in RISK_EDIT_FIELDS} | {"id": risk_id}
    if data["signal_ids"] is None:
        kept = originals.get(risk_id)
        data["signal_ids"] = kept.signal_ids if kept else []
    escalation = data["escalation"]
    if escalation is None:
        # Validated with a stand-in level first, because the suggestion needs a valid score.
        data["escalation"] = EscalationLevel.TEAM
    try:
        risk = Risk.model_validate(data)
    except ValidationError as error:
        raise EditRejected(number, _field_of(error)) from error
    if escalation is None:
        risk = risk.model_copy(update={"escalation": suggested_escalation(risk_score(risk))})
    return risk


def _raci_from_edit(edit: RaciEdit, number: int, originals: dict[str, RaciRow]) -> RaciRow:
    roles = [role for role, code in edit.codes.items() if code]
    assignments = [{"role": role, "code": edit.codes[role]} for role in roles]
    try:
        row = RaciRow.model_validate({"activity": edit.activity, "assignments": assignments})
    except ValidationError as error:
        location = error.errors()[0]["loc"]
        field = roles[int(location[1])] if location[0] == "assignments" else str(location[0])
        raise EditRejected(number, field) from error
    kept = originals.get(row.activity)
    if kept is not None and _same_assignments(row, kept):
        del originals[row.activity]
        return kept
    return row.model_copy(update={"human_adjusted": True})


def _same_assignments(row: RaciRow, other: RaciRow) -> bool:
    # The editor lists roles in the grid's column order, which needn't match the row's.
    def key(r: RaciRow) -> list[tuple[str, str]]:
        return sorted((a.role, a.code) for a in r.assignments)

    return key(row) == key(other)


def _mark(risk: Risk, kept: Risk | None) -> Risk:
    if risk == kept:
        return kept
    return risk.model_copy(update={"human_adjusted": True})


def _field_of(error: ValidationError) -> str:
    return str(error.errors()[0]["loc"][0])


# Session


def show_sample(sample: Sample) -> None:
    """Make this sample the report shown to the visitor, clearing any earlier edits."""
    st.session_state[_SAMPLE_KEY] = sample
    st.session_state.pop(_EDITED_KEY, None)
    _new_edit_version()


def shown_sample() -> Sample | None:
    """Return the sample whose report is shown, or None before the first Analyze."""
    sample = st.session_state.get(_SAMPLE_KEY)
    return sample if isinstance(sample, Sample) else None


def shown_report() -> Report | None:
    """Return the final version with the visitor's edits.

    Returns None before the first Analyze, and for a sample whose project got no report.
    """
    sample = shown_sample()
    if sample is None:
        return None
    edited = st.session_state.get(_EDITED_KEY)
    return edited if isinstance(edited, Report) else sample.final


def save_risk_edits(rows: Sequence[Mapping[str, Any]]) -> None:
    """Apply the risk editor's rows to the shown report. See `apply_risk_edits`."""
    original, current = _editable()
    _save(apply_risk_edits(original, current, rows))


def save_raci_edits(rows: Sequence[RaciEdit]) -> None:
    """Apply the RACI editor's rows to the shown report. See `apply_raci_edits`."""
    original, current = _editable()
    _save(apply_raci_edits(original, current, rows))


def save_health_override(dimension: Dimension, label: HealthLabel, note: str | None) -> None:
    """Apply a health label override to the shown report. See `override_health`."""
    original, current = _editable()
    _save(override_health(original, current, dimension, label, note))


def _editable() -> tuple[Report, Report]:
    sample = shown_sample()
    current = shown_report()
    if sample is None or sample.final is None or current is None:
        raise LookupError("There is no sample report shown to edit")
    return sample.final, current


def editor_key(name: str) -> str:
    """The widget key for an editor, which changes whenever the shown report changes.

    An editor keeps the visitor's pending changes as a diff against the table it was
    given. A new key starts it fresh from the new report, so a diff is never applied twice
    or to another sample.
    """
    return f"{name}_editor_{st.session_state.get(_EDIT_VERSION_KEY, 0)}"


def _new_edit_version() -> None:
    st.session_state[_EDIT_VERSION_KEY] = st.session_state.get(_EDIT_VERSION_KEY, 0) + 1


def _save(report: Report) -> None:
    st.session_state[_EDITED_KEY] = report
    _new_edit_version()
