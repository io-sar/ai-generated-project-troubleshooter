"""The browser-facing settings the app controls stay safe (threat model T9 and T12).

Streamlit Community Cloud sets the response headers, so these are the only web defences the
app owns: request-forgery and cross-origin protection stay on, error details stay hidden,
and no app code turns off Streamlit's escaping of HTML.
"""

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CONFIG = ROOT / ".streamlit" / "config.toml"
APP_CODE = [ROOT / "src", ROOT / "app_pages", ROOT / "streamlit_app.py"]
# Any way of rendering raw HTML, which would let model or visitor text run in the browser.
RAW_HTML = ("unsafe_allow_html", "st.html", "components.html", "components.v1.html")


def settings() -> dict[str, dict[str, object]]:
    with CONFIG.open("rb") as file:
        return tomllib.load(file)


@pytest.mark.parametrize("name", ["enableXsrfProtection", "enableCORS"])
def test_browser_protections_are_not_turned_off(name: str) -> None:
    # Unset means Streamlit's default, which is on.
    assert settings().get("server", {}).get(name, True) is True


def test_error_details_stay_hidden() -> None:
    assert settings()["client"]["showErrorDetails"] == "none"


def test_app_code_never_renders_raw_html() -> None:
    assert _raw_html_uses([p for p in APP_CODE if p.exists()]) == []


def test_the_scan_finds_raw_html(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text("st.markdown(text, unsafe_allow_html=True)\n", encoding="utf-8")
    (tmp_path / "clean.py").write_text("st.markdown(plain(text))\n", encoding="utf-8")

    assert _raw_html_uses([tmp_path]) == [(planted, "unsafe_allow_html")]


def _raw_html_uses(paths: list[Path]) -> list[tuple[Path, str]]:
    """Return each (file, pattern) where app code renders raw HTML."""
    files = [
        p for path in paths for p in ([path] if path.is_file() else sorted(path.rglob("*.py")))
    ]
    return [
        (file, pattern)
        for file in files
        for pattern in RAW_HTML
        if pattern in file.read_text(encoding="utf-8")
    ]
