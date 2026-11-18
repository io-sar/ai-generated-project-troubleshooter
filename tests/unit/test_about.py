import pytest

from troubleshooter import config
from troubleshooter.ui.about import repo_url


def test_empty_path_links_the_repo_itself() -> None:
    assert repo_url() == config.REPO_URL


def test_path_links_into_the_docs_branch() -> None:
    assert repo_url("docs/adr") == f"{config.REPO_URL}/tree/develop/docs/adr"


def test_branch_comes_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DOCS_BRANCH", "main")

    assert repo_url("SPEC.md") == f"{config.REPO_URL}/tree/main/SPEC.md"
