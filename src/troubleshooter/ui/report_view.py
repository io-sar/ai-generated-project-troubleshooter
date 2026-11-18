"""Report display. Shows data only; every calculation lives in `domain`.

Report text may come from a model, so it is shown with `plain()` or in a dataframe,
never as Markdown or HTML.
"""

import re
from typing import Literal

import streamlit as st

from troubleshooter.domain.codes import Dimension, HealthLabel, ReportSource
from troubleshooter.domain.models import (
    DecisionMemo,
    Diagnosis,
    HealthScores,
    RaciRow,
    Report,
    Risk,
    Sample,
    Sprint,
    StakeholderUpdates,
)
from troubleshooter.domain.raci import rows_without_one_accountable
from troubleshooter.domain.scoring import (
    dimension_scores,
    label_for,
    overall_label,
    overall_score,
    risk_score,
)
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


def render_comparison(sample: Sample) -> None:
    """Show the "What I changed" note, then the AI draft and the final version side by side.

    Streamlit stacks the two columns on narrow screens, so phones read them one after
    the other.
    """
    st.subheader(t("compare.changes"), anchor=False)
    # The note is the author's own text from the repo, so Markdown is allowed; HTML never is.
    st.markdown(sample.changes)
    draft_column, final_column = st.columns(2)
    with draft_column:
        st.header(t("compare.draft"), anchor=False)
        # Read-only by design: the draft records what the AI produced.
        render_report(sample.draft)
    with final_column:
        st.header(t("compare.final"), anchor=False)
        render_report(sample.final)


def render_report(report: Report) -> None:
    """Show every report section, in reading order."""
    render_health(report.health)
    render_risks(report.risks)
    render_recovery_plan(report)
    render_stakeholder_updates(report.stakeholder_updates)
    render_decision_memo(report.decision_memo)
    render_raci(report.raci)


def render_stakeholder_updates(updates: StakeholderUpdates) -> None:
    """Show one tab per audience, each with a copy button."""
    st.subheader(t("updates.title"), anchor=False)
    audiences = {
        "executive": updates.executive,
        "delivery_team": updates.delivery_team,
        "customer": updates.customer,
    }
    tabs = st.tabs([t(f"updates.{audience}") for audience in audiences])
    for tab, text in zip(tabs, audiences.values(), strict=True):
        # A code block copies with one click and never renders Markdown.
        tab.code(text, language=None, wrap_lines=True)


def render_decision_memo(memo: DecisionMemo) -> None:
    """Show the context, the options and their trade-offs, the recommendation and metrics."""
    st.subheader(t("memo.title"), anchor=False)
    st.markdown(f"**{t('memo.context')}**")
    st.markdown(plain(memo.context))
    rows = [
        {t("memo.option"): option.title, t("memo.trade_offs"): option.trade_offs}
        for option in memo.options
    ]
    st.dataframe(rows, hide_index=True)
    st.markdown(f"**{t('memo.recommendation')}**")
    st.markdown(plain(memo.recommendation))
    st.markdown(f"**{t('memo.success_metrics')}**")
    st.markdown("\n".join(f"- {plain(metric)}" for metric in memo.success_metrics))


def render_raci(raci: list[RaciRow]) -> None:
    """Show activities by roles, and flag rows that don't have exactly one Accountable."""
    st.subheader(t("raci.title"), anchor=False)
    broken = set(rows_without_one_accountable(raci))
    roles = list(dict.fromkeys(a.role for row in raci for a in row.assignments))
    rows = []
    for position, row in enumerate(raci):
        cells: dict[str, list[str]] = {role: [] for role in roles}
        for assignment in row.assignments:
            # A role listed twice keeps both codes rather than silently losing one.
            cells[assignment.role].append(assignment.code)
        check = t("raci.needs_one_a") if position in broken else ""
        rows.append(
            {t("raci.activity"): row.activity}
            | {role: ", ".join(codes) for role, codes in cells.items()}
            | {t("raci.check"): check}
        )
    st.dataframe(rows, hide_index=True)
    if broken:
        names = ", ".join(raci[position].activity for position in sorted(broken))
        st.warning(t("raci.warning", activities=plain(names)))


def render_under_the_hood(report: Report, diagnosis: Diagnosis) -> None:
    """Show the numbers and data behind the report, for readers who want the detail."""
    with st.expander(t("hood.title")):
        st.markdown(f"**{t('hood.engine')}:** {t('hood.sample_engine')}")
        scores = dimension_scores(report.health)
        rows = [
            {t("hood.dimension"): t(f"dimension.{dimension}"), t("hood.score"): score}
            for dimension, score in scores.items()
        ]
        rows.append(
            {
                t("hood.dimension"): t("health.overall"),
                t("hood.score"): overall_score(report.health),
            }
        )
        st.markdown(f"**{t('hood.scores')}**")
        st.dataframe(rows, hide_index=True)
        st.markdown(f"**{t('hood.signals')}**")
        signals = [
            {
                t("hood.signal_id"): signal.id,
                t("hood.observation"): signal.observation,
                t("hood.evidence"): signal.evidence,
            }
            for signal in diagnosis.signals
        ]
        st.dataframe(signals, hide_index=True)
        st.markdown(f"**{t('hood.diagnosis')}**")
        st.json(diagnosis.model_dump(mode="json"), expanded=False)


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
