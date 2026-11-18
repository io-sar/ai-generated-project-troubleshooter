"""Report display. Shows data only; every calculation lives in `domain`.

Report text may come from a model, so it is shown with `plain()` or in a dataframe,
never as Markdown or HTML.
"""

import re
from typing import Literal

import streamlit as st

from troubleshooter.domain.codes import Dimension, HealthLabel, ReportSource
from troubleshooter.domain.models import HealthScores, Report, Risk, Sample, Sprint
from troubleshooter.domain.scoring import label_for, overall_label, risk_score
from troubleshooter.i18n import t

BadgeColor = Literal["green", "blue", "orange", "red"]

_SOURCE_COLORS: dict[ReportSource, BadgeColor] = {
    ReportSource.RECORDED: "green",
    ReportSource.LIVE: "blue",
    ReportSource.PLACEHOLDER: "orange",
}

_LABEL_COLORS: dict[HealthLabel, BadgeColor] = {
    HealthLabel.GOOD: "green",
    HealthLabel.PROBLEMATIC: "orange",
    HealthLabel.AT_RISK: "red",
}

# Everything Streamlit's Markdown treats as syntax, including :colour[] directives and $maths$.
_MARKDOWN_SYNTAX = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")


def plain(text: str) -> str:
    """Escape Markdown so text shows exactly as written, with no links, images or styling.

    Args:
        text: Text that may come from a model or a visitor.

    Returns:
        The text with every Markdown character backslash-escaped.
    """
    return _MARKDOWN_SYNTAX.sub(r"\\\1", text)


def render_badge(source: ReportSource) -> None:
    """Show what the report is, as text and colour together."""
    st.badge(t(f"badge.{source}"), color=_SOURCE_COLORS[source])


def render_report_header(sample: Sample) -> None:
    """Show the badge, the sample's title, its scenario and its key points."""
    render_badge(sample.badge)
    st.header(sample.title, anchor=False)
    st.subheader(t("report.scenario"), anchor=False)
    st.text(sample.scenario.text)
    if sample.scenario.key_points:
        st.subheader(t("report.key_points"), anchor=False)
        st.markdown("\n".join(f"- {plain(point)}" for point in sample.scenario.key_points))


def render_report(report: Report) -> None:
    """Show every report section, in reading order."""
    render_health(report.health)
    render_risks(report.risks)
    render_recovery_plan(report)


def render_health(health: HealthScores) -> None:
    """Show the overall label and each dimension's label and rationale, without numbers."""
    st.subheader(t("health.title"), anchor=False)
    overall = overall_label(health)
    st.markdown(f"{t('health.overall')} {_label_badge(overall)}")
    for dimension in Dimension:
        status = getattr(health, dimension.value)
        st.markdown(f"**{t(f'dimension.{dimension}')}** {_label_badge(label_for(status.score))}")
        st.caption(plain(status.rationale))


def render_risks(risks: list[Risk]) -> None:
    """Show the risk register as a read-only table."""
    st.subheader(t("risks.title"), anchor=False)
    rows = [
        {
            t("risks.id"): risk.id,
            t("risks.description"): risk.description,
            t("risks.likelihood"): risk.likelihood,
            t("risks.impact"): risk.impact,
            t("risks.score"): risk_score(risk),
            t("risks.owner"): risk.owner,
            t("risks.mitigation"): risk.mitigation,
            t("risks.escalation"): t(f"escalation.{risk.escalation}"),
            t("risks.signals"): ", ".join(risk.signal_ids),
        }
        for risk in risks
    ]
    st.dataframe(rows, hide_index=True)


def render_recovery_plan(report: Report) -> None:
    """Show the three sprints in order, each with its goal and actions."""
    st.subheader(t("plan.title"), anchor=False)
    st.caption(t("plan.sequencing"))
    plan = report.recovery_plan
    for name, sprint in (
        ("stabilize", plan.stabilize),
        ("recover", plan.recover),
        ("sustain", plan.sustain),
    ):
        _render_sprint(t(f"plan.{name}"), sprint)


def _render_sprint(heading: str, sprint: Sprint) -> None:
    st.markdown(f"**{heading}**")
    st.markdown(plain(sprint.goal))
    rows = [
        {
            t("plan.action"): action.description,
            t("plan.owner"): action.owner,
            t("plan.success_signal"): action.success_signal,
        }
        for action in sprint.actions
    ]
    st.dataframe(rows, hide_index=True)


def _label_badge(label: HealthLabel) -> str:
    # Markdown badge directive, so the badge can sit inline after its dimension name.
    return f":{_LABEL_COLORS[label]}-badge[{t(f'health_label.{label}')}]"
