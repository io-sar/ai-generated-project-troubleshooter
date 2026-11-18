"""Every text field in an export is escaped, so model text can't inject HTML or Markdown."""

from datetime import UTC, datetime
from typing import Any

import pytest

from tests.unit.report_data import report_data
from troubleshooter.domain.codes import ProjectType, ReportSource
from troubleshooter.domain.models import Report, Scenario
from troubleshooter.export.renderer import ExportInput, render_html, render_markdown

SCRIPT = "<script>alert(1)</script>"
LINK = "[click](http://evil.example)"
IMAGE = "![x](http://evil.example/t.png)"
PAYLOAD = f"{SCRIPT} {LINK} {IMAGE}"
# Fields that hold codes, not text; the schema rejects anything else in them.
CODE_FIELDS = {"escalation", "code"}


def poison(node: Any, key: str = "") -> Any:
    """Replace every text value in raw report data with the payload."""
    if isinstance(node, dict):
        return {name: poison(value, name) for name, value in node.items()}
    if isinstance(node, list):
        return [poison(item, key) for item in node]
    if isinstance(node, str) and key not in CODE_FIELDS:
        return PAYLOAD
    return node


@pytest.fixture(scope="module")
def hostile() -> ExportInput:
    return ExportInput(
        report=Report.model_validate(poison(report_data())),
        title=PAYLOAD,
        source=ReportSource.LIVE,
        scenario=Scenario(
            project_type=ProjectType.SOFTWARE_DELIVERY, text=PAYLOAD, key_points=[PAYLOAD]
        ),
        generated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def test_poisoned_report_reaches_every_text_field(hostile: ExportInput) -> None:
    dumped = hostile.report.model_dump_json()

    assert dumped.count("evil.example/t.png") > 20


def test_html_escapes_every_field(hostile: ExportInput) -> None:
    html = render_html(hostile)

    assert SCRIPT not in html
    assert "<a " not in html and "<img" not in html
    assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;") > 20


def test_markdown_escapes_every_field(hostile: ExportInput) -> None:
    markdown = render_markdown(hostile)

    assert SCRIPT not in markdown
    assert "](http" not in markdown
    assert "![" not in markdown
    assert markdown.count(r"\<script\>alert\(1\)\</script\>") > 20


def test_markdown_table_cells_stay_on_one_line() -> None:
    data = report_data()
    data["risks"][0]["description"] = "First line\nsecond line | with a pipe"
    export = ExportInput(
        report=Report.model_validate(data),
        title="T",
        source=ReportSource.LIVE,
        scenario=Scenario(project_type=ProjectType.SOFTWARE_DELIVERY, text="S"),
        generated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert r"| First line second line \| with a pipe |" in render_markdown(export)
