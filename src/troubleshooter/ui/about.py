"""The "About the builder" sidebar and the links into the public repo."""

import streamlit as st

from troubleshooter import config
from troubleshooter.i18n import t


def repo_url(path: str = "") -> str:
    """Return the GitHub link to a file or folder in the repo, on the docs branch.

    Args:
        path: Path from the repo root, such as ``"docs/adr"``. Empty links the repo itself.

    Returns:
        The full URL.
    """
    if not path:
        return config.REPO_URL
    return f"{config.REPO_URL}/tree/{config.DOCS_BRANCH}/{path}"


def link(label_key: str, url: str) -> None:
    """Show one external link. The label is catalog text and the URL comes from config."""
    st.markdown(f"[{t(label_key)}]({url})")


def render_about_sidebar() -> None:
    """Show who built the app, with links to their profile and the repo.

    The build story is in the page menu just above, so it isn't linked here again.
    """
    with st.sidebar:
        st.subheader(t("about.title"))
        st.markdown(f"**{t('about.name')}**")
        st.caption(t("about.role"))
        link("about.linkedin", config.BUILDER_LINKEDIN_URL)
        link("about.repo", repo_url())
