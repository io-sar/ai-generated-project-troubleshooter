"""The deployed app never reads the author's local secrets (SPEC section 6).

The local secrets file holds the author's own key, for the recording and eval scripts only.
The app must work on visitors' keys alone, so no app code may read that file or `st.secrets`.
The scripts in `scripts/` are local tools and are allowed to.
"""

from pathlib import Path

ROOT = Path(__file__).parents[2]
APP_CODE = [ROOT / "src", ROOT / "app_pages", ROOT / "streamlit_app.py"]
# Any way of reaching the author's secrets from app code.
FORBIDDEN = ("st.secrets", "secrets.toml", "streamlit.secrets", "from streamlit import secrets")


def test_app_code_never_reads_the_local_secrets() -> None:
    assert _secret_reads([p for p in APP_CODE if p.exists()]) == []


def test_the_scan_finds_a_secrets_read(tmp_path: Path) -> None:
    planted = tmp_path / "pages" / "planted.py"
    planted.parent.mkdir()
    planted.write_text('key = st.secrets["ANTHROPIC_API_KEY"]\n', encoding="utf-8")
    (tmp_path / "clean.py").write_text("key = st.session_state.get('key')\n", encoding="utf-8")

    assert _secret_reads([tmp_path]) == [(planted, "st.secrets")]


def _secret_reads(paths: list[Path]) -> list[tuple[Path, str]]:
    """Return each (file, pattern) where app code reaches for the local secrets."""
    files = [
        p for path in paths for p in ([path] if path.is_file() else sorted(path.rglob("*.py")))
    ]
    return [
        (file, pattern)
        for file in files
        for pattern in FORBIDDEN
        if pattern in file.read_text(encoding="utf-8")
    ]
