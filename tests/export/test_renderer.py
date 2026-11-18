"""Export snapshots with a fixed clock, plus the parts of an export that must always appear.

To accept an intended change to the output, run once with UPDATE_SNAPSHOTS=1 and review
the diff of tests/export/snapshots/ before committing it.
"""

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from troubleshooter.config import SAMPLES_DIR
from troubleshooter.domain.models import Sample
from troubleshooter.engines.sample_engine import load_sample
from troubleshooter.export.renderer import (
    ExportInput,
    TrustedMarkdown,
    render_html,
    render_markdown,
)
from troubleshooter.i18n import t

SNAPSHOTS = Path(__file__).with_name("snapshots")
FIXED_CLOCK = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
Renderer = Callable[[ExportInput], str]
RENDERERS: dict[str, Renderer] = {"md": render_markdown, "html": render_html}


def export_input(sample: Sample, *, with_note: bool = True) -> ExportInput:
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
        output = render(export_input(placeholder))
        assert output.endswith("\n") and not output.endswith("\n\n")
        assert all(line == line.rstrip() for line in output.splitlines())
