import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import troubleshooter
from troubleshooter import config
from troubleshooter.i18n import t

APP = Path(__file__).parents[2] / "streamlit_app.py"
PLACEHOLDER_BADGE = f":orange-badge[{t('badge.placeholder')}]"


def run_app(sample: str | None = None) -> AppTest:
    app = AppTest.from_file(str(APP))
    if sample is not None:
        app.query_params["sample"] = sample
    app.run()
    return app


def markdown_text(app: AppTest) -> list[str]:
    return [element.value for element in app.markdown]


def shows_report(app: AppTest) -> bool:
    return PLACEHOLDER_BADGE in markdown_text(app)


def test_app_runs_without_errors() -> None:
    assert not run_app().exception


def test_default_page_shows_package_version() -> None:
    app = run_app()
    assert app.title[0].value == t("app.title")
    assert app.caption[0].value == t("app.version", version=troubleshooter.__version__)


def test_selector_lists_samples_by_title_and_no_report_yet() -> None:
    app = run_app()

    assert app.selectbox[0].label == t("analyze.sample_label")
    assert app.selectbox[0].options == ["Placeholder: CRM migration running late"]
    assert not shows_report(app)


def test_analyze_shows_the_report_and_a_shareable_link() -> None:
    app = run_app()

    app.button[0].click().run()

    assert not app.exception
    assert shows_report(app)
    assert app.header[0].value == "Placeholder: CRM migration running late"
    assert "- Data quality blocks the migration." in markdown_text(app)[-1]
    assert app.query_params["sample"] == "placeholder"


def test_shared_link_opens_the_report_without_a_click() -> None:
    app = run_app(sample="placeholder")

    assert not app.exception
    assert shows_report(app)
    assert not app.warning


@pytest.mark.parametrize("sample", ["nope", "../placeholder", ""])
def test_unknown_shared_link_falls_back_to_the_selector(sample: str) -> None:
    app = run_app(sample=sample)

    assert not app.exception
    assert app.warning[0].value == t("errors.sample_not_found")
    assert app.selectbox
    assert not shows_report(app)


def test_broken_sample_shows_a_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "placeholder"
    shutil.copytree(config.SAMPLES_DIR / "placeholder", broken)
    (broken / "draft.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(config, "SAMPLES_DIR", tmp_path)

    app = run_app(sample="placeholder")

    assert not app.exception
    assert app.error[0].value == t("errors.no_samples")
    assert not shows_report(app)
