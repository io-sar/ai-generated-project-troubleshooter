"""Report display. Shows data only; every calculation lives in `domain`.

Report text may come from a model, so it is shown with `plain()` or in a dataframe,
never as Markdown or HTML.
"""

from datetime import datetime
from typing import Any, Literal

import streamlit as st

from troubleshooter.domain.codes import Dimension, EscalationLevel, HealthLabel, ReportSource
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
from troubleshooter.domain.raci import codes_by_role, roles_in_order, rows_without_one_accountable
from troubleshooter.domain.scoring import (
    dimension_scores,
    label_for,
    overall_label,
    overall_score,
    risk_score,
    suggested_escalation,
)
from troubleshooter.export.markdown import escape_markdown as plain
from troubleshooter.export.renderer import (
    ExportInput,
    TrustedMarkdown,
    render_html,
    render_markdown,
)
from troubleshooter.i18n import t
from troubleshooter.ui import state
from troubleshooter.ui.state import EditRejected

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


def render_comparison(sample: Sample, final: Report) -> None:
    """Show the "What I changed" note, then the AI draft and the final version side by side.

    `final` is the final version with any of the visitor's edits, shown read-only here.
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
        render_report(final)


def render_report(report: Report, *, editable: bool = False) -> None:
    """Show every report section, in reading order.

    Pass `editable=True` only for the final version: the AI draft is never edited.
    """
    render_health(report.health)
    if editable:
        render_risk_editor(report.risks)
    else:
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
    roles = roles_in_order(raci)
    rows = [
        {t("raci.activity"): row.activity}
        | codes_by_role(row, roles)
        | {t("raci.check"): t("raci.needs_one_a") if position in broken else ""}
        for position, row in enumerate(raci)
    ]
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


# Risk editor columns, keyed by code; derived and display-only columns can't be edited.
_RISK_LABELS = {
    "id": "risks.id",
    "description": "risks.description",
    "likelihood": "risks.likelihood",
    "impact": "risks.impact",
    "score": "risks.score",
    "owner": "risks.owner",
    "mitigation": "risks.mitigation",
    "escalation": "risks.escalation",
    "suggested": "risks.suggested",
    "signals": "risks.signals",
    "edited": "edit.column",
}
_RISK_READ_ONLY = ["id", "score", "suggested", "signals", "edited"]


def render_risk_editor(risks: list[Risk]) -> None:
    """Show the risk register as an editable table, applied with one button.

    Edits are applied together so a visitor can fill a new row cell by cell. A rejected
    edit stays in the table, so the visitor can fix it.
    """
    st.subheader(t("risks.title"), anchor=False)
    st.caption(t("edit.help"))
    with st.form("risk_form", border=False):
        edited = st.data_editor(
            [_risk_row(risk) for risk in risks],
            column_config=_risk_columns(),
            disabled=_RISK_READ_ONLY,
            num_rows="dynamic",
            hide_index=True,
            key=state.editor_key("risks"),
        )
        applied = st.form_submit_button(t("edit.apply"))
    if not applied:
        return
    try:
        state.save_risk_edits(edited)
    except EditRejected as rejected:
        column = t(_RISK_LABELS[rejected.field])
        st.error(t("edit.rejected", row=rejected.row, column=column))
        return
    st.rerun()


def _risk_row(risk: Risk) -> dict[str, object]:
    score = risk_score(risk)
    return {
        "id": risk.id,
        "description": risk.description,
        "likelihood": risk.likelihood,
        "impact": risk.impact,
        "score": score,
        "owner": risk.owner,
        "mitigation": risk.mitigation,
        "escalation": risk.escalation.value,
        "suggested": t(f"escalation.{suggested_escalation(score)}"),
        # Display text under its own key, which the state layer ignores, so the risk keeps
        # its links and new risks start with none.
        "signals": ", ".join(risk.signal_ids),
        "edited": t("edit.marker") if risk.human_adjusted else "",
    }


def _risk_columns() -> dict[str, Any]:
    labels = {name: t(key) for name, key in _RISK_LABELS.items()}
    return labels | {
        "likelihood": _rating_column(labels["likelihood"]),
        "impact": _rating_column(labels["impact"]),
        "escalation": st.column_config.SelectboxColumn(
            labels["escalation"],
            options=[level.value for level in EscalationLevel],
            format_func=lambda code: t(f"escalation.{code}"),
        ),
    }


def _rating_column(label: str) -> Any:
    # The editor's own limits; the state layer checks them again when edits are applied.
    return st.column_config.NumberColumn(label, min_value=1, max_value=5, step=1)


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


def render_downloads(sample: Sample, generated_at: datetime) -> None:
    """Offer the final version as Markdown and as print-ready HTML."""
    data = ExportInput(
        report=sample.final,
        title=sample.title,
        source=sample.badge,
        scenario=sample.scenario,
        generated_at=generated_at,
        changes=TrustedMarkdown(sample.changes),
    )
    markdown_column, html_column = st.columns(2)
    markdown_column.download_button(
        t("export.download_markdown"),
        data=render_markdown(data),
        file_name=f"{sample.id}-report.md",
        mime="text/markdown",
    )
    html_column.download_button(
        t("export.download_html"),
        data=render_html(data),
        file_name=f"{sample.id}-report.html",
        mime="text/html",
    )
