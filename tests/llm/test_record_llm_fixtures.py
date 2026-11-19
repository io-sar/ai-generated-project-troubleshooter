"""The recording script's key guard. The script itself only runs locally, with a real key."""

import json

import pytest

from ..script_loading import load_script


def test_fixture_keeps_case_model_status_and_body() -> None:
    script = load_script("record_llm_fixtures")

    text = script.fixture_text("case-a", "model-a", 200, {"id": "msg_1"}, ["sk-ant-real"])

    assert json.loads(text) == {
        "case": "case-a",
        "model": "model-a",
        "status": 200,
        "body": {"id": "msg_1"},
    }


@pytest.mark.parametrize("key", ["sk-ant-real", "sk-ant-other"])
def test_fixture_with_a_key_in_it_is_never_returned(key: str) -> None:
    script = load_script("record_llm_fixtures")
    body = {"error": {"message": f"bad key {key}"}}

    with pytest.raises(SystemExit, match="contains a key"):
        script.fixture_text("case-a", "model-a", 401, body, ["sk-ant-real", "sk-ant-other"])
