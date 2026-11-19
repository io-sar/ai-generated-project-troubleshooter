"""Export snapshots with a fixed clock, plus the parts of an export that must always appear.

To accept an intended change to the output, run once with UPDATE_SNAPSHOTS=1 and review
the diff of tests/export/snapshots/ before committing it.
"""

import dataclasses
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from troubleshooter.config import SAMPLES_DIR
from troubleshooter.domain.codes import Dimension, HealthLabel
from troubleshooter.domain.models import Report, Sample
from troubleshooter.engines.sample_engine import load_sample
from troubleshooter.export.markdown import escape_markdown
from troubleshooter.export.renderer import (
    ExportInput,
    TrustedMarkdown,
    render_html,
    render_markdown,
)
from troubleshooter.i18n import t
from troubleshooter.ui.state import RaciEdit, apply_raci_edits, apply_risk_edits, override_health

SNAPSHOTS = Path(__file__).with_name("snapshots")
FIXED_CLOCK = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
Renderer = Callable[[ExportInput], str]
RENDERERS: dict[str, Renderer] = {"md": render_markdown, "html": render_html}


def export_input(sample: Sample, *, with_note: bool = True) -> ExportInput:
    assert sample.final is not None
    return ExportInput(
        report=sample.final,
        title=sample.title,
        source=sample.badge,
        scenario=sample.scenario,
        generated_at=FIXED_CLOCK,
        changes=TrustedMarkdown(sample.changes) if with_note else None,
    )


@pytest.fixture(scope="module")
def placeholder() -> Sample:
    return load_sample(SAMPLES_DIR, "placeholder")


@pytest.mark.parametrize("extension", RENDERERS)
def test_export_matches_snapshot(placeholder: Sample, extension: str) -> None:
    output = RENDERERS[extension](export_input(placeholder))
    snapshot = SNAPSHOTS / f"placeholder.{extension}"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        snapshot.write_text(output, encoding="utf-8", newline="\n")
    assert output == snapshot.read_text(encoding="utf-8")


@pytest.mark.parametrize("extension", RENDERERS)
def test_export_shows_badge_timestamp_and_note(placeholder: Sample, extension: str) -> None:
    output = RENDERERS[extension](export_input(placeholder))

    timestamp = {"md": r"2026\-01\-02 03\:04 UTC", "html": "2026-01-02 03:04 UTC"}

    assert t("badge.placeholder") in output
    assert timestamp[extension] in output
    assert t("compare.changes") in output


@pytest.mark.parametrize("extension", RENDERERS)
def test_note_section_is_left_out_when_there_is_no_note(
    placeholder: Sample, extension: str
) -> None:
    output = RENDERERS[extension](export_input(placeholder, with_note=False))

    assert t("compare.changes") not in output


def test_timestamp_is_shown_in_utc(placeholder: Sample) -> None:
    athens = timezone(timedelta(hours=2))
    data = export_input(placeholder)
    local = ExportInput(**{**data.__dict__, "generated_at": FIXED_CLOCK.astimezone(athens)})

    assert "03:04 UTC" in render_html(local)


@pytest.mark.parametrize("extension", RENDERERS)
def test_note_markdown_is_kept_in_markdown_and_escaped_in_html(
    placeholder: Sample, extension: str
) -> None:
    output = RENDERERS[extension](export_input(placeholder))

    if extension == "md":
        assert "- **Added risk R4**" in output
    else:
        assert "<strong>" not in output
        assert "**Added risk R4**" in output


def test_export_files_end_with_one_newline_and_no_trailing_spaces(placeholder: Sample) -> None:
    for render in RENDERERS.values():
        for data in (export_input(placeholder), edited_input(placeholder)):
            output = render(data)
            assert output.endswith("\n") and not output.endswith("\n\n")
            assert all(line == line.rstrip() for line in output.splitlines())


def edited_report(sample: Sample) -> Report:
    """The placeholder's final version after a fixed set of visitor edits."""
    original = sample.final
    assert original is not None
    rows = [risk.model_dump(exclude={"human_adjusted"}) for risk in original.risks]
    rows[2]["impact"] = 5
    report = apply_risk_edits(original, original, rows)
    raci = [
        RaciEdit(row.activity, {a.role: a.code for a in row.assignments}) for row in original.raci
    ]
    raci.append(RaciEdit("Go-live comms", {"Project manager": "A", "Sponsor": "A"}))
    report = apply_raci_edits(original, report, raci)
    return override_health(
        original, report, Dimension.QUALITY, HealthLabel.AT_RISK, "QA found 17 open defects."
    )


def edited_input(sample: Sample) -> ExportInput:
    return dataclasses.replace(export_input(sample), report=edited_report(sample))


@pytest.mark.parametrize("extension", RENDERERS)
def test_edited_export_matches_snapshot(placeholder: Sample, extension: str) -> None:
    output = RENDERERS[extension](edited_input(placeholder))
    snapshot = SNAPSHOTS / f"placeholder-edited.{extension}"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        snapshot.write_text(output, encoding="utf-8", newline="\n")
    assert output == snapshot.read_text(encoding="utf-8")


MARKERS = {
    "md": r" *(Human\-adjusted)*",
    "html": f' <span class="badge">{t("edit.marker")}</span>',
}


@pytest.mark.parametrize("extension", RENDERERS)
def test_each_edited_item_is_marked_once(placeholder: Sample, extension: str) -> None:
    unedited = RENDERERS[extension](export_input(placeholder))
    edited = RENDERERS[extension](edited_input(placeholder))

    # One risk, one RACI row and one health dimension were edited.
    assert MARKERS[extension] not in unedited
    assert edited.count(MARKERS[extension]) == 3


@pytest.mark.parametrize(
    ("extension", "note"),
    [
        ("md", r" — Note\: QA found 17 open defects\. |"),
        ("html", "<br><em>Note: QA found 17 open defects.</em></td>"),
    ],
)
def test_health_note_follows_the_ai_rationale(
    placeholder: Sample, extension: str, note: str
) -> None:
    output = RENDERERS[extension](edited_input(placeholder))

    assert note in output


@pytest.mark.parametrize("extension", RENDERERS)
def test_raci_row_without_one_accountable_is_flagged(placeholder: Sample, extension: str) -> None:
    output = RENDERERS[extension](edited_input(placeholder))

    assert output.count(t("raci.needs_one_a")) == 1


# Where the report covers each key point


def test_each_key_point_shows_where_the_report_covers_it(placeholder: Sample) -> None:
    sample = placeholder
    where = tuple(f"R{n}" for n, _ in enumerate(sample.scenario.key_points, start=1))
    data = dataclasses.replace(export_input(sample), covered_by=where)

    markdown = render_markdown(data)
    html = render_html(data)

    for point, risk in zip(sample.scenario.key_points, where, strict=True):
        covered = t("report.covered_by", where=risk)
        assert f"- {escape_markdown(point)} {escape_markdown(f'({covered})')}\n" in markdown
        assert f"<li>{point} <em>({covered})</em></li>" in html


def test_covered_by_text_is_escaped(placeholder: Sample) -> None:
    sample = placeholder
    hostile = ("<script>alert(1)</script> [x](http://evil.example)",) * len(
        sample.scenario.key_points
    )
    data = dataclasses.replace(export_input(sample), covered_by=hostile)

    assert "<script>" not in render_html(data)
    assert "[x](http://evil.example)" not in render_markdown(data)


def test_key_points_without_coverage_show_no_covered_by_line(placeholder: Sample) -> None:
    data = export_input(placeholder)

    assert t("report.covered_by", where="") not in render_markdown(data)
