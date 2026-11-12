"""Entry point: page config and navigation. Run with: uv run streamlit run streamlit_app.py"""

import streamlit as st

st.set_page_config(page_title="AI Project Troubleshooter", layout="wide")

page = st.navigation([st.Page("app_pages/analyze.py", title="Analyze", default=True)])
page.run()
