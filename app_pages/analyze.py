"""Main page: pick a sample, click Analyze, read the report.

A link such as ``?sample=<id>`` opens that sample's report directly.
"""

import logging

import streamlit as st

import troubleshooter
from troubleshooter import config
from troubleshooter.domain.models import Sample
from troubleshooter.engines.sample_engine import SampleFormatError, list_sample_ids, load_sample
from troubleshooter.i18n import t
from troubleshooter.ui import state
from troubleshooter.ui.report_view import render_report, render_report_header

logger = logging.getLogger(__name__)


def available_samples() -> dict[str, Sample]:
    """Load every sample, skipping broken ones so one bad file can't take the page down."""
    samples: dict[str, Sample] = {}
    for sample_id in list_sample_ids(config.SAMPLES_DIR):
        try:
            samples[sample_id] = load_sample(config.SAMPLES_DIR, sample_id)
        except SampleFormatError as error:
            # The message names the file only, never its contents.
            logger.error("Skipping sample %r: %s", sample_id, error)
    return samples


st.title(t("app.title"))
st.caption(t("app.version", version=troubleshooter.__version__))

samples = available_samples()
if not samples:
    st.error(t("errors.no_samples"))
    st.stop()

requested = st.query_params.get("sample")
if requested is not None and requested not in samples:
    st.warning(t("errors.sample_not_found"))

ids = list(samples)
chosen = st.selectbox(
    t("analyze.sample_label"),
    ids,
    index=ids.index(requested) if requested in samples else 0,
    format_func=lambda sample_id: samples[sample_id].title,
)

if st.button(t("analyze.button"), type="primary"):
    state.show_sample(samples[chosen])
    st.query_params["sample"] = chosen
elif requested in samples:
    shown = state.shown_sample()
    if shown is None or shown.id != requested:
        state.show_sample(samples[requested])

shown = state.shown_sample()
if shown is not None:
    st.divider()
    render_report_header(shown)
    # The author's reviewed version is the main report; the AI draft is shown for comparison.
    render_report(shown.final)
