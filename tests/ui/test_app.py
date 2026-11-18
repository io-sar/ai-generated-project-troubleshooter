import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import troubleshooter
from troubleshooter import config
from troubleshooter.i18n import t

APP = Path(__file__).parents[2] / "streamlit_app.py"
PLACEHOLDER_BADGE = f":orange-badge[{t('badge.placeholder')}]"
# The first run that draws a table imports pandas and pyarrow, which can pass
# AppTest's 3-second default on a cold or slow CI machine. Later runs take under 1 s.
RUN_TIMEOUT_SECONDS = 15


def run_app(sample: str | None = None) -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=RUN_TIMEOUT_SECONDS)
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
    assert any(r"- Data quality blocks the migration\." in line for line in markdown_text(app))
    assert app.query_params["sample"] == "placeholder"


def badge(label: str) -> str:
    colors = {"good": "green", "problematic": "orange", "at_risk": "red"}
    return f":{colors[label]}-badge[{t(f'health_label.{label}')}]"


def test_health_dashboard_shows_labels_not_numbers() -> None:
    text = markdown_text(run_app(sample="placeholder"))

    # Final placeholder scores: schedule 30, scope 65, quality 40, risk control 50,
    # stakeholder confidence 35, so the overall average of 44 is Problematic.
    assert f"{t('health.overall')} {badge('problematic')}" in text
    expected = {
        "schedule": "at_risk",
        "scope": "problematic",
        "quality": "problematic",
        "risk_control": "problematic",
        "stakeholder_confidence": "at_risk",
    }
    for dimension, label in expected.items():
        assert f"**{t(f'dimension.{dimension}')}** {badge(label)}" in text
    for score in ("30", "65", "40", "50", "35", "44"):
        assert not any(score in line for line in text)


def test_risk_register_lists_final_risks_with_translated_escalation() -> None:
    app = run_app(sample="placeholder")
    risks = app.dataframe[0].value

    assert list(risks[t("risks.id")]) == ["R1", "R2", "R3", "R4"]
    assert list(risks[t("risks.score")]) == [20, 16, 9, 16]
    assert list(risks[t("risks.escalation")]) == [
        t("escalation.steering"),
        t("escalation.sponsor"),
        t("escalation.pm"),
        t("escalation.sponsor"),
    ]


def test_recovery_plan_shows_three_sprints_in_order() -> None:
    text = markdown_text(run_app(sample="placeholder"))
    headings = [f"**{t(f'plan.{name}')}**" for name in ("stabilize", "recover", "sustain")]

    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)


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
