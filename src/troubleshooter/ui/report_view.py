"""Report display. Shows data only; every calculation lives in `domain`."""

from typing import Literal

import streamlit as st

from troubleshooter.domain.codes import ReportSource
from troubleshooter.domain.models import Sample
from troubleshooter.i18n import t

BadgeColor = Literal["green", "blue", "orange"]

_BADGE_COLORS: dict[ReportSource, BadgeColor] = {
    ReportSource.RECORDED: "green",
    ReportSource.LIVE: "blue",
    ReportSource.PLACEHOLDER: "orange",
}


def render_badge(source: ReportSource) -> None:
    """Show what the report is, as text and colour together."""
    st.badge(t(f"badge.{source}"), color=_BADGE_COLORS[source])


def render_report_header(sample: Sample) -> None:
    """Show the badge, the sample's title, its scenario and its key points."""
    render_badge(sample.badge)
    st.header(sample.title, anchor=False)
    st.subheader(t("report.scenario"), anchor=False)
    st.text(sample.scenario.text)
    if sample.scenario.key_points:
        st.subheader(t("report.key_points"), anchor=False)
        st.markdown("\n".join(f"- {point}" for point in sample.scenario.key_points))
