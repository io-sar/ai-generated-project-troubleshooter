"""The only layer that reads or changes the report in `st.session_state`.

Each visitor's report lives in their own session, never in shared state.
"""

import streamlit as st

from troubleshooter.domain.models import Sample

_SAMPLE_KEY = "shown_sample"


def show_sample(sample: Sample) -> None:
    """Make this sample the report shown to the visitor."""
    st.session_state[_SAMPLE_KEY] = sample


def shown_sample() -> Sample | None:
    """Return the sample whose report is shown, or None before the first Analyze."""
    sample = st.session_state.get(_SAMPLE_KEY)
    return sample if isinstance(sample, Sample) else None
