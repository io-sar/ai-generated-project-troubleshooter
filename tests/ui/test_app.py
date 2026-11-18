import json
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import troubleshooter
from troubleshooter import config
from troubleshooter.engines.sample_engine import load_sample
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


@pytest.fixture
def sample_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the placeholder that the app loads instead, so a test can break it."""
    folder = tmp_path / "placeholder"
    shutil.copytree(config.SAMPLES_DIR / "placeholder", folder)
    monkeypatch.setattr(config, "SAMPLES_DIR", tmp_path)
    return folder


def test_broken_sample_shows_a_friendly_error(sample_copy: Path) -> None:
    (sample_copy / "draft.json").write_text("{not json", encoding="utf-8")

    app = run_app(sample="placeholder")

    assert not app.exception
    assert app.error[0].value == t("errors.no_samples")
    assert not shows_report(app)


def test_stakeholder_updates_have_one_copyable_tab_each() -> None:
    app = run_app(sample="placeholder")
    final = load_sample(config.SAMPLES_DIR, "placeholder").final.stakeholder_updates

    assert [tab.label for tab in app.tabs] == [
        t("updates.executive"),
        t("updates.delivery_team"),
        t("updates.customer"),
    ]
    assert [block.value for block in app.code] == [
        final.executive,
        final.delivery_team,
        final.customer,
    ]


def test_decision_memo_shows_options_and_recommendation() -> None:
    app = run_app(sample="placeholder")
    options = app.dataframe[4].value

    assert list(options[t("memo.option")]) == [
        "Keep the April date",
        "Extend the licence by two months",
    ]
    assert r"Extend the licence by two months and cut over in June\." in markdown_text(app)


def test_raci_grid_shows_codes_by_role_with_no_warning() -> None:
    app = run_app(sample="placeholder")
    raci = app.dataframe[5].value

    assert list(raci[t("raci.activity")]) == [
        "Schema handover",
        "Data cleaning",
        "Cutover decision",
    ]
    assert list(raci["Data analyst"]) == ["", "R", ""]
    assert list(raci[t("raci.check")]) == ["", "", ""]
    assert not app.warning


def test_raci_row_with_two_accountables_is_flagged(sample_copy: Path) -> None:
    final_path = sample_copy / "final.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    final["raci"][1]["assignments"][1]["code"] = "A"
    final_path.write_text(json.dumps(final), encoding="utf-8")

    app = run_app(sample="placeholder")
    raci = app.dataframe[5].value

    assert not app.exception
    assert list(raci[t("raci.check")]) == ["", t("raci.needs_one_a"), ""]
    assert app.warning[0].value == t("raci.warning", activities="Data cleaning")


def test_under_the_hood_shows_scores_signals_and_diagnosis() -> None:
    app = run_app(sample="placeholder")
    scores = app.dataframe[6].value
    signals = app.dataframe[7].value

    assert app.expander[0].label == t("hood.title")
    assert list(scores[t("hood.score")]) == [30, 65, 40, 50, 35, 44]
    assert list(signals[t("hood.signal_id")]) == ["S1", "S2", "S3", "S4", "S5"]
    assert app.json[0].value


def compare_view() -> AppTest:
    app = run_app(sample="placeholder")
    app.segmented_control[0].set_value("compare").run()
    return app


def test_default_view_shows_only_the_final_report() -> None:
    app = run_app(sample="placeholder")

    assert app.segmented_control[0].label == t("view.label")
    assert app.segmented_control[0].value == "final"
    assert t("compare.changes") not in [element.value for element in app.subheader]
    assert len(app.dataframe[0].value) == 4


def test_compare_view_shows_the_note_then_draft_beside_final() -> None:
    app = compare_view()
    risk_tables = [app.dataframe[0].value, app.dataframe[6].value]

    assert not app.exception
    assert app.subheader[2].value == t("compare.changes")
    assert any("**Added risk R4**" in line for line in markdown_text(app))
    assert [element.value for element in app.header][1:] == [
        t("compare.draft"),
        t("compare.final"),
    ]
    assert [len(table) for table in risk_tables] == [3, 4]


def test_draft_has_no_input_widgets() -> None:
    app = compare_view()

    # The only inputs on the page are the sample picker, Analyze and the view switch.
    assert len(app.selectbox) == 1
    assert len(app.button) == 1
    assert len(app.segmented_control) == 1
    assert not app.text_input
    assert not app.text_area
    assert not app.number_input


def test_switching_back_shows_the_final_report_again() -> None:
    app = compare_view()

    app.segmented_control[0].set_value("final").run()

    assert t("compare.draft") not in [element.value for element in app.header]
    assert len(app.dataframe[0].value) == 4
