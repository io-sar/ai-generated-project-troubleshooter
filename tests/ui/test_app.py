import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

import troubleshooter
from troubleshooter import config
from troubleshooter.engines.sample_engine import load_sample
from troubleshooter.export.markdown import escape_markdown
from troubleshooter.export.renderer import ExportInput, render_markdown
from troubleshooter.i18n import t
from troubleshooter.ui import report_view

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


def warnings_besides_refresh(app: AppTest) -> list[str]:
    """Warnings other than the refresh notice, which the final view always shows."""
    return [w.value for w in app.warning if w.value != t("edit.refresh_warning")]


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


MARKER_BADGE = f":gray-badge[{t('edit.marker')}]"


def test_final_view_has_adjust_controls_for_each_dimension() -> None:
    app = run_app(sample="placeholder")

    assert [expander.label for expander in app.expander].count(t("edit.adjust")) == 5


def override_health(app: AppTest, dimension: str, label: str, note: str = "") -> AppTest:
    """Pick a label and note in one dimension's Adjust form, then click Apply."""
    name = t(f"dimension.{dimension}")
    select = next(box for box in app.selectbox if box.label == t("edit.label_for", dimension=name))
    select.set_value(label)
    note_input = next(
        box for box in app.text_input if box.label == t("edit.note_for", dimension=name)
    )
    note_input.input(note)
    app.button(key=f"health_{dimension}_apply").click().run()
    return app


def test_health_label_override_shows_the_marker_and_recalculates() -> None:
    app = run_app(sample="placeholder")

    override_health(app, "scope", "at_risk")

    text = markdown_text(app)
    assert not app.exception
    # Scope's 65 becomes At Risk's 15, so the average of 34 is At Risk.
    assert f"{t('health.overall')} {badge('at_risk')}" in text
    assert f"**{t('dimension.scope')}** {badge('at_risk')} {MARKER_BADGE}" in text
    assert f"**{t('dimension.schedule')}** {badge('at_risk')}" in text


def test_health_note_appears_beside_the_ai_rationale() -> None:
    app = run_app(sample="placeholder")
    rationale = load_sample(config.SAMPLES_DIR, "placeholder").final.health.quality.rationale

    override_health(app, "quality", "problematic", "QA *signed* off.")

    captions = [element.value for element in app.caption]
    assert captions[captions.index(escape_markdown(rationale)) + 1] == t(
        "edit.note_shown", note=r"QA \*signed\* off\."
    )
    assert f"**{t('dimension.quality')}** {badge('problematic')} {MARKER_BADGE}" in (
        markdown_text(app)
    )


def test_choosing_the_ai_label_without_a_note_removes_the_marker() -> None:
    app = run_app(sample="placeholder")
    override_health(app, "scope", "at_risk", "Too optimistic.")

    override_health(app, "scope", "problematic", "")

    text = markdown_text(app)
    assert f"**{t('dimension.scope')}** {badge('problematic')}" in text
    assert f"{t('health.overall')} {badge('problematic')}" in text
    assert not any(MARKER_BADGE in line for line in text)


def test_compare_view_has_no_health_controls() -> None:
    app = compare_view()

    assert t("edit.adjust") not in [expander.label for expander in app.expander]


def test_risk_register_lists_final_risks_with_their_scores_and_levels() -> None:
    app = run_app(sample="placeholder")
    risks = app.dataframe[0].value

    assert list(risks["id"]) == ["R1", "R2", "R3", "R4"]
    assert list(risks["score"]) == [20, 16, 9, 16]
    # The editor holds codes; its dropdown shows them translated.
    assert list(risks["escalation"]) == ["steering", "sponsor", "pm", "sponsor"]
    assert list(risks["suggested"]) == [
        t("escalation.steering"),
        t("escalation.sponsor"),
        t("escalation.pm"),
        t("escalation.sponsor"),
    ]
    assert list(risks["edited"]) == ["", "", "", ""]


EDITORS = ("risks", "raci")


def edit_table(app: AppTest, table: str, delta: dict[str, Any]) -> AppTest:
    """Make edits in one editor, as a visitor would, then click its Apply button."""
    editor = app.data_editor[EDITORS.index(table)]
    assert editor.key is not None
    app.session_state[editor.key] = {
        "edited_rows": {},
        "added_rows": [],
        "deleted_rows": [],
    } | delta
    app.button(key=f"{table}_apply").click().run()
    return app


def edit_risks(app: AppTest, delta: dict[str, Any]) -> AppTest:
    return edit_table(app, "risks", delta)


def test_final_view_has_editable_risk_and_raci_tables() -> None:
    app = run_app(sample="placeholder")

    assert [editor.editing_mode for editor in app.data_editor] == ["dynamic", "dynamic"]
    assert [app.button(key=f"{table}_apply").label for table in EDITORS] == [
        t("edit.apply"),
        t("edit.apply"),
    ]


def test_applied_risk_edit_updates_the_score_and_shows_the_marker() -> None:
    app = run_app(sample="placeholder")

    edit_risks(app, {"edited_rows": {2: {"impact": 5}}})

    risks = app.dataframe[0].value
    assert not app.exception and not app.error
    assert list(risks["score"]) == [20, 16, 15, 16]
    assert list(risks["edited"]) == ["", "", t("edit.marker"), ""]
    # Under the hood reads the same edited report, so nothing else changed there.
    assert list(app.dataframe[6].value[t("hood.score")]) == [30, 65, 40, 50, 35, 44]


def test_added_risk_gets_an_id_and_the_suggested_level() -> None:
    app = run_app(sample="placeholder")
    new = {
        "description": "Key engineer leaves.",
        "likelihood": 2,
        "impact": 3,
        "owner": "PM",
        "mitigation": "Pair on the cutover scripts.",
    }

    edit_risks(app, {"added_rows": [new]})

    risks = app.dataframe[0].value
    assert not app.error
    assert list(risks["id"])[-1] == "R5"
    assert list(risks["escalation"])[-1] == "pm"
    assert list(risks["edited"])[-1] == t("edit.marker")


def test_deleted_risk_is_gone() -> None:
    app = run_app(sample="placeholder")

    edit_risks(app, {"deleted_rows": [0]})

    assert list(app.dataframe[0].value["id"]) == ["R2", "R3", "R4"]


def test_invalid_risk_edit_shows_an_error_and_changes_nothing() -> None:
    app = run_app(sample="placeholder")

    edit_risks(app, {"edited_rows": {1: {"likelihood": 9}}})

    assert not app.exception
    assert app.error[0].value == t("edit.rejected", row=2, column=t("risks.likelihood"))
    # The table is drawn from the unchanged report, with the visitor's edit kept on top
    # under the same key so they can fix it.
    risks = app.dataframe[0].value
    assert list(risks["likelihood"]) == [4, 4, 3, 4]
    assert list(risks["edited"]) == ["", "", "", ""]
    key = app.data_editor[0].key
    assert key is not None
    assert app.session_state[key]["edited_rows"]


def test_compare_view_shows_the_edited_final_read_only() -> None:
    app = run_app(sample="placeholder")
    edit_risks(app, {"deleted_rows": [3]})

    app.segmented_control[0].set_value("compare").run()

    assert not app.data_editor
    assert [len(app.dataframe[0].value), len(app.dataframe[6].value)] == [3, 3]


def test_recovery_plan_shows_three_sprints_in_order() -> None:
    text = markdown_text(run_app(sample="placeholder"))
    headings = [f"**{t(f'plan.{name}')}**" for name in ("stabilize", "recover", "sustain")]

    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_shared_link_opens_the_report_without_a_click() -> None:
    app = run_app(sample="placeholder")

    assert not app.exception
    assert shows_report(app)
    assert not warnings_besides_refresh(app)


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


# Placeholder roles, in the order they first appear: IT manager, Database administrator,
# Project manager, Data lead, Data analyst, Support manager, Sponsor.
DATA_ANALYST = "role_4"
PROJECT_MANAGER = "role_2"


def test_raci_grid_shows_codes_by_role_with_no_warning() -> None:
    app = run_app(sample="placeholder")
    raci = app.dataframe[5].value

    assert list(raci["activity"]) == [
        "Schema handover",
        "Data cleaning",
        "Cutover decision",
    ]
    assert codes(raci[DATA_ANALYST]) == [None, "R", None]
    assert list(raci["check"]) == ["", "", ""]
    assert not warnings_besides_refresh(app)


def codes(column: Any) -> list[str | None]:
    # AppTest reads empty cells back as NaN; the app itself receives None.
    return [value if isinstance(value, str) else None for value in column]


def edit_raci(app: AppTest, delta: dict[str, Any]) -> AppTest:
    return edit_table(app, "raci", delta)


def test_changed_raci_code_marks_the_row() -> None:
    app = run_app(sample="placeholder")

    edit_raci(app, {"edited_rows": {0: {PROJECT_MANAGER: "C"}}})

    raci = app.dataframe[5].value
    assert not app.exception and not app.error
    assert codes(raci[PROJECT_MANAGER]) == ["C", None, "R"]
    assert list(raci["edited"]) == [t("edit.marker"), "", ""]


def test_second_accountable_warns_but_still_exports() -> None:
    app = run_app(sample="placeholder")

    edit_raci(app, {"edited_rows": {1: {DATA_ANALYST: "A"}}})

    raci = app.dataframe[5].value
    assert not app.error
    assert list(raci["check"]) == ["", t("raci.needs_one_a"), ""]
    assert warnings_besides_refresh(app) == [t("raci.warning", activities="Data cleaning")]
    assert len(app.download_button) == 2


def test_fixing_a_broken_raci_row_clears_the_warning(sample_copy: Path) -> None:
    final_path = sample_copy / "final.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    final["raci"][1]["assignments"][1]["code"] = "A"
    final_path.write_text(json.dumps(final), encoding="utf-8")
    app = run_app(sample="placeholder")

    edit_raci(app, {"edited_rows": {1: {DATA_ANALYST: "R"}}})

    assert not warnings_besides_refresh(app)
    assert list(app.dataframe[5].value["edited"]) == ["", t("edit.marker"), ""]


def test_added_and_deleted_raci_rows() -> None:
    app = run_app(sample="placeholder")
    new = {"activity": "Go-live comms", PROJECT_MANAGER: "A"}

    edit_raci(app, {"added_rows": [new], "deleted_rows": [0]})

    raci = app.dataframe[5].value
    assert list(raci["activity"]) == ["Data cleaning", "Cutover decision", "Go-live comms"]
    assert list(raci["edited"]) == ["", "", t("edit.marker")]


def test_raci_row_without_an_activity_is_rejected() -> None:
    app = run_app(sample="placeholder")

    edit_raci(app, {"added_rows": [{PROJECT_MANAGER: "A"}]})

    assert not app.exception
    assert app.error[0].value == t("edit.rejected", row=4, column=t("raci.activity"))
    assert len(app.dataframe[5].value) == 3


def test_raci_row_with_two_accountables_is_flagged(sample_copy: Path) -> None:
    final_path = sample_copy / "final.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    final["raci"][1]["assignments"][1]["code"] = "A"
    final_path.write_text(json.dumps(final), encoding="utf-8")

    app = run_app(sample="placeholder")
    raci = app.dataframe[5].value

    assert not app.exception
    assert list(raci["check"]) == ["", t("raci.needs_one_a"), ""]
    assert warnings_besides_refresh(app) == [t("raci.warning", activities="Data cleaning")]


def test_under_the_hood_shows_scores_signals_and_diagnosis() -> None:
    app = run_app(sample="placeholder")
    scores = app.dataframe[6].value
    signals = app.dataframe[7].value

    assert app.expander[-1].label == t("hood.title")
    assert list(scores[t("hood.score")]) == [30, 65, 40, 50, 35, 44]
    assert list(signals[t("hood.signal_id")]) == ["S1", "S2", "S3", "S4", "S5"]
    assert app.json[0].value


def hood_text(app: AppTest) -> list[str]:
    """The Markdown lines in Under the hood, which is the last expander."""
    return [element.value for element in app.expander[-1].markdown]


def test_under_the_hood_shows_how_a_recorded_sample_was_made(sample_copy: Path) -> None:
    run = {
        "provider": "anthropic",
        "model": "claude-sonnet-5-5",
        "prompt_versions": {"generate": "v2", "diagnose": "v1"},
        "prompt_fingerprints": {"generate": "a" * 64, "diagnose": "b" * 64},
        "recorded_on": "2026-11-20",
    }
    (sample_copy / "run.json").write_text(json.dumps(run), encoding="utf-8")

    app = run_app(sample="placeholder")

    assert hood_text(app)[1:4] == [
        f"**{t('hood.model')}:** claude\\-sonnet\\-5\\-5",
        f"**{t('hood.prompts')}:** "
        + ", ".join(
            [
                t("hood.prompt_version", prompt="diagnose", version="v1"),
                t("hood.prompt_version", prompt="generate", version="v2"),
            ]
        ),
        f"**{t('hood.recorded')}:** 2026-11-20",
    ]


def test_under_the_hood_shows_no_run_for_a_sample_not_recorded() -> None:
    app = run_app(sample="placeholder")

    labels = [t("hood.model"), t("hood.prompts"), t("hood.recorded")]
    assert not [line for line in hood_text(app) if any(f"**{label}:**" in line for label in labels)]


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
    assert not app.data_editor
    assert t("edit.adjust") not in [expander.label for expander in app.expander]


def test_final_view_warns_that_refreshing_loses_edits() -> None:
    final = run_app(sample="placeholder")
    compare = compare_view()

    assert [w.value for w in final.warning] == [t("edit.refresh_warning")]
    assert t("edit.refresh_warning") not in [w.value for w in compare.warning]


def test_refresh_warning_comes_before_the_editors() -> None:
    app = run_app(sample="placeholder")
    values = [getattr(element, "value", None) for element in app.main]

    assert values.index(t("edit.refresh_warning")) < values.index(t("health.title"))


def test_analyzing_again_restores_the_original_final_version() -> None:
    app = run_app(sample="placeholder")
    edit_risks(app, {"deleted_rows": [0]})
    assert len(app.dataframe[0].value) == 3

    app.button[0].click().run()

    risks = app.dataframe[0].value
    assert list(risks["id"]) == ["R1", "R2", "R3", "R4"]
    assert list(risks["edited"]) == ["", "", "", ""]


def test_switching_back_shows_the_final_report_again() -> None:
    app = compare_view()

    app.segmented_control[0].set_value("final").run()

    assert t("compare.draft") not in [element.value for element in app.header]
    assert len(app.dataframe[0].value) == 4


def sidebar_text(app: AppTest) -> list[str]:
    return [element.value for element in app.sidebar.markdown]


def test_sidebar_shows_the_builder_and_their_links() -> None:
    app = run_app()

    assert app.sidebar.subheader[0].value == t("about.title")
    assert f"**{t('about.name')}**" in sidebar_text(app)
    assert app.sidebar.caption[0].value == t("about.role")
    assert f"[{t('about.linkedin')}]({config.BUILDER_LINKEDIN_URL})" in sidebar_text(app)
    assert f"[{t('about.repo')}]({config.REPO_URL})" in sidebar_text(app)
    # The page menu already lists How this was built, so the sidebar doesn't repeat it.
    assert not app.sidebar.page_link


def test_results_screen_links_to_how_this_was_built_after_the_report() -> None:
    before = run_app()
    after = run_app(sample="placeholder")

    main_links = [link.label for link in after.main.page_link]
    assert main_links == [t("how.link")]
    assert not before.main.page_link
    # The reader sees the whole report first; the build story comes last.
    assert list(after.main)[-1] == after.main.page_link[0]


def how_built_page() -> AppTest:
    app = run_app()
    app.switch_page(config.HOW_BUILT_PAGE).run()
    return app


def test_how_this_was_built_page_renders() -> None:
    app = how_built_page()

    assert not app.exception
    assert app.title[0].value == t("how.title")
    raci = app.dataframe[0].value
    assert len(raci) == 6
    assert raci[t("how.raci.activity")].iloc[0] == t("how.raci.scope")
    assert list(raci[t("how.raci.claude")]) == ["C", "R", "R", "", "", "C"]


@pytest.mark.parametrize(
    ("label_key", "path"),
    [
        ("how.links.spec", "SPEC.md"),
        ("how.links.roadmap", "ROADMAP.md"),
        ("how.links.adrs", "docs/adr"),
        ("how.links.prompts", "src/troubleshooter/prompts"),
        ("how.links.tests", "tests"),
        ("how.links.ci", ".github/workflows/ci.yml"),
    ],
)
def test_how_this_was_built_links_into_the_repo(label_key: str, path: str) -> None:
    url = f"{config.REPO_URL}/tree/{config.DOCS_BRANCH}/{path}"

    assert f"[{t(label_key)}]({url})" in [
        element.value for element in how_built_page().main.markdown
    ]


def test_how_this_was_built_links_the_board_and_repo() -> None:
    text = [element.value for element in how_built_page().main.markdown]

    assert f"[{t('how.links.board')}]({config.BOARD_URL})" in text
    assert f"[{t('how.links.repo')}]({config.REPO_URL})" in text


@pytest.fixture
def exported(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The Markdown each run offers for download, newest last.

    AppTest can't read a download's contents, so this wraps the app's renderer instead.
    """
    outputs: list[str] = []

    def spy(data: ExportInput) -> str:
        outputs.append(render_markdown(data))
        return outputs[-1]

    monkeypatch.setattr(report_view, "render_markdown", spy)
    return outputs


def test_edit_reaches_the_download_with_its_marker(exported: list[str]) -> None:
    app = run_app(sample="placeholder")
    assert r"*(Human\-adjusted)*" not in exported[-1]

    edit_risks(app, {"edited_rows": {2: {"impact": 5}}})

    risk_line = next(line for line in exported[-1].splitlines() if line.startswith("| R3"))
    assert risk_line.startswith(r"| R3 *(Human\-adjusted)* |")
    assert "| 3 | 5 | 15 |" in risk_line


@pytest.mark.parametrize(("table", "frame"), [("risks", 0), ("raci", 5)])
def test_empty_added_row_is_dropped_and_never_reaches_the_download(
    exported: list[str], table: str, frame: int
) -> None:
    app = run_app(sample="placeholder")
    rows_before = len(app.dataframe[frame].value)
    export_before = exported[-1]

    edit_table(app, table, {"added_rows": [{}]})

    assert not app.exception and not app.error
    assert len(app.dataframe[frame].value) == rows_before
    assert exported[-1] == export_before


def test_report_offers_markdown_and_html_downloads() -> None:
    app = run_app(sample="placeholder")

    assert [button.label for button in app.download_button] == [
        t("export.download_markdown"),
        t("export.download_html"),
    ]
