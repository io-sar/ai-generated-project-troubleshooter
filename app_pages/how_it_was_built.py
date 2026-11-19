"""How this was built: who did what, and links to the plan, decisions and tests."""

import streamlit as st

from troubleshooter import config
from troubleshooter.i18n import t
from troubleshooter.ui.about import link, repo_url

# The same split as the README's RACI. Activity keys are under "how.raci".
RACI = [
    ("scope", "A, R", "C"),
    ("code", "A", "R"),
    ("scenarios", "A", "R"),
    ("corrections", "A, R", ""),
    ("greek", "A, R", ""),
    ("reviews", "A, R", "C"),
]

st.title(t("how.title"))
st.write(t("how.intro"))

st.subheader(t("how.split_title"))
st.dataframe(
    [
        {
            t("how.raci.activity"): t(f"how.raci.{activity}"),
            t("how.raci.author"): author,
            t("how.raci.claude"): claude,
        }
        for activity, author, claude in RACI
    ],
    hide_index=True,
)
st.caption(t("how.raci.legend"))

st.subheader(t("how.managed_title"))
st.write(t("how.managed_intro"))
link("how.links.spec", repo_url("SPEC.md"))
link("how.links.roadmap", repo_url("ROADMAP.md"))
link("how.links.board", config.BOARD_URL)
link("how.links.adrs", repo_url("docs/adr"))
link("how.links.prompts", repo_url("src/troubleshooter/prompts"))

st.subheader(t("how.checks_title"))
st.write(t("how.checks_intro"))
link("how.links.tests", repo_url("tests"))
link("how.links.ci", repo_url(".github/workflows/ci.yml"))
link("how.links.repo", repo_url())
