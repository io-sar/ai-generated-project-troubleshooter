"""Main page. For now it only proves the app can import the troubleshooter package."""

import streamlit as st

import troubleshooter
from troubleshooter.i18n import t

st.title(t("app.title"))
st.caption(t("app.version", version=troubleshooter.__version__))
