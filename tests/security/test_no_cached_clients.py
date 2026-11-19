"""Clients hold a key, so they must never be cached or shared between sessions.

The same goes for a visitor's scenario and report, so the app uses no Streamlit cache at all.
"""

from pathlib import Path

from troubleshooter import config
from troubleshooter.llm.anthropic_client import AnthropicClient
from troubleshooter.llm.base import Provider
from troubleshooter.llm.factory import create_client

ROOT = Path(__file__).parents[2]
APP_CODE = [ROOT / "src", ROOT / "app_pages", ROOT / "streamlit_app.py"]
CACHES = ("cache_resource", "cache_data", "experimental_singleton", "experimental_memo")


def test_each_call_builds_a_new_client_and_sdk() -> None:
    model = config.MODELS["anthropic"].default

    first = create_client(Provider.ANTHROPIC, "sk-ant-visitor-a", model)
    second = create_client(Provider.ANTHROPIC, "sk-ant-visitor-a", model)

    assert isinstance(first, AnthropicClient)
    assert isinstance(second, AnthropicClient)
    assert first is not second
    assert first._sdk is not second._sdk


def test_two_visitors_never_share_a_key() -> None:
    model = config.MODELS["anthropic"].default

    first = create_client(Provider.ANTHROPIC, "sk-ant-visitor-a", model)
    second = create_client(Provider.ANTHROPIC, "sk-ant-visitor-b", model)

    assert isinstance(first, AnthropicClient)
    assert isinstance(second, AnthropicClient)
    assert first._sdk.api_key == "sk-ant-visitor-a"
    assert second._sdk.api_key == "sk-ant-visitor-b"


def test_app_code_uses_no_streamlit_cache() -> None:
    assert _cache_uses([p for p in APP_CODE if p.exists()]) == []


def test_the_scan_finds_a_cached_function(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text("@st.cache_resource\ndef client(): ...\n", encoding="utf-8")

    assert _cache_uses([tmp_path]) == [(planted, "cache_resource")]


def _cache_uses(paths: list[Path]) -> list[tuple[Path, str]]:
    """Return each (file, cache name) where app code mentions a Streamlit cache."""
    files = [
        p for path in paths for p in ([path] if path.is_file() else sorted(path.rglob("*.py")))
    ]
    return [
        (file, cache)
        for file in files
        for cache in CACHES
        if cache in file.read_text(encoding="utf-8")
    ]
