"""Main page. For now it only proves the app can import the troubleshooter package."""

import streamlit as st

import troubleshooter

st.title("AI Project Troubleshooter")
st.caption(f"Version {troubleshooter.__version__}")
