from pathlib import Path

from streamlit.testing.v1 import AppTest

import troubleshooter
from troubleshooter.i18n import t

APP = Path(__file__).parents[2] / "streamlit_app.py"


def run_app() -> AppTest:
    app = AppTest.from_file(str(APP))
    app.run()
    return app


def test_app_runs_without_errors() -> None:
    assert not run_app().exception


def test_default_page_shows_package_version() -> None:
    app = run_app()
    assert app.title[0].value == t("app.title")
    assert app.caption[0].value == t("app.version", version=troubleshooter.__version__)
