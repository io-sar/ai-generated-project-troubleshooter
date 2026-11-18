"""Entry point: page config, navigation and sidebar.

Run with: uv run streamlit run streamlit_app.py
"""

import streamlit as st

from troubleshooter import config
from troubleshooter.i18n import t
from troubleshooter.ui.about import render_about_sidebar

st.set_page_config(page_title=t("app.title"), layout="wide")

page = st.navigation(
    [
        st.Page(config.ANALYZE_PAGE, title=t("nav.analyze"), default=True),
        st.Page(config.HOW_BUILT_PAGE, title=t("nav.how_built")),
    ]
)
render_about_sidebar()
page.run()
