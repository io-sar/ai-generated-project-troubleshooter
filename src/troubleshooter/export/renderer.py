"""Render a report as Markdown or standalone HTML for download.

Every value placed in a template is escaped by the template environment itself:
HTML with Jinja2 autoescaping, Markdown with `escape_markdown` as the finalize hook.
So a template can't forget to escape model text.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from troubleshooter.domain.codes import Dimension, ReportSource
from troubleshooter.domain.models import DimensionHealth, HealthScores, Report, Scenario
from troubleshooter.domain.raci import codes_by_role, roles_in_order, rows_without_one_accountable
from troubleshooter.domain.scoring import label_for, overall_label, risk_score
from troubleshooter.export.markdown import escape_markdown
from troubleshooter.i18n import t

_TEMPLATES = Path(__file__).with_name("templates")


class TrustedMarkdown(str):
    """Markdown from the repo, such as the author's note, that keeps its formatting."""

    __slots__ = ()


@dataclass(frozen=True)
class ExportInput:
    """Everything an export shows. Plain values, so every engine's report exports alike."""

    report: Report
    title: str
    source: ReportSource
    scenario: Scenario
    generated_at: datetime
    # The "What I changed" note, for reports that have one.
    changes: TrustedMarkdown | None = None
    # Where the report covers each key point, in key point order; empty if not given.
    covered_by: tuple[str, ...] = ()


def render_markdown(data: ExportInput) -> str:
    """Return the report as a Markdown document.

    Args:
        data: The report and the details shown around it.

    Returns:
        Markdown text in which every value is escaped, except a trusted note.
    """
    return _MARKDOWN_ENV.get_template("report.md.j2").render(_context(data))


def render_html(data: ExportInput) -> str:
    """Return the report as a standalone HTML page with inline CSS and print styles.

    Args:
        data: The report and the details shown around it.

    Returns:
        An HTML document in which every value is HTML-escaped.
    """
    return _HTML_ENV.get_template("report.html.j2").render(_context(data))


def _escape_markdown_value(value: Any) -> str:
    if isinstance(value, TrustedMarkdown):
        return str(value)
    return escape_markdown(str(value))


def _one_line(value: str) -> str:
    # Table cells can't hold line breaks in Markdown.
    return " ".join(value.split())


_MARKDOWN_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    # HTML escaping is the wrong rule for Markdown; finalize escapes every value instead,
    # and tests/export/test_export_escaping.py proves it.
    autoescape=False,  # noqa: S701
    finalize=_escape_markdown_value,
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
_MARKDOWN_ENV.filters["one_line"] = _one_line
_MARKDOWN_ENV.globals["t"] = t

_HTML_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    autoescape=True,
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
_HTML_ENV.globals["t"] = t


def key_points_with_coverage(
    points: list[str], covered_by: tuple[str, ...] | list[str]
) -> list[tuple[str, str | None]]:
    """Pair each key point with where the report covers it, or None if not given."""
    return [(point, covered_by[n] if covered_by else None) for n, point in enumerate(points)]


def _context(data: ExportInput) -> dict[str, Any]:
    report = data.report
    plan = report.recovery_plan
    broken = set(rows_without_one_accountable(report.raci))
    roles = roles_in_order(report.raci)
    return {
        "title": data.title,
        "source": data.source,
        "scenario": data.scenario,
        "key_points": key_points_with_coverage(data.scenario.key_points, data.covered_by),
        "changes": data.changes,
        "generated": data.generated_at.astimezone(UTC).strftime(t("export.date_format")),
        "overall": overall_label(report.health),
        "dimensions": [_dimension(report.health, dimension) for dimension in Dimension],
        "risks": [{"risk": risk, "score": risk_score(risk)} for risk in report.risks],
        "sprints": [
            ("stabilize", plan.stabilize),
            ("recover", plan.recover),
            ("sustain", plan.sustain),
        ],
        "updates": [
            ("executive", report.stakeholder_updates.executive),
            ("delivery_team", report.stakeholder_updates.delivery_team),
            ("customer", report.stakeholder_updates.customer),
        ],
        "memo": report.decision_memo,
        "roles": roles,
        "raci": [
            {
                "activity": row.activity,
                "cells": codes_by_role(row, roles),
                "broken": position in broken,
                "adjusted": row.human_adjusted,
            }
            for position, row in enumerate(report.raci)
        ],
    }


def _dimension(health: HealthScores, dimension: Dimension) -> dict[str, Any]:
    status: DimensionHealth = getattr(health, dimension.value)
    return {
        "code": dimension,
        "label": label_for(status.score),
        "rationale": status.rationale,
        "adjusted": status.human_adjusted,
        "note": status.note,
    }
