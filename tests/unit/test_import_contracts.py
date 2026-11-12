"""Proves the import-linter contracts in pyproject.toml catch imports that break the rules.

Each case copies the package to a temporary folder, plants one import, and runs
lint-imports with the real config against that copy.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"


def run_lint_imports(
    tmp_path: Path, planted: tuple[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    src = tmp_path / "src"
    shutil.copytree(ROOT / "src" / "troubleshooter", src / "troubleshooter")
    if planted is not None:
        importer, imported = planted
        (src / "troubleshooter" / importer / "planted.py").write_text(
            f"import troubleshooter.{imported}\n", encoding="utf-8"
        )
    # PYTHONPATH puts the copy ahead of the installed package.
    env = {**os.environ, "PYTHONPATH": str(src)}
    result = subprocess.run(  # noqa: S603 - fixed executable and arguments, no shell
        [str(LINT_IMPORTS), "--config", str(ROOT / "pyproject.toml"), "--no-cache"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    return result


def assert_kept(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 broken" in result.stdout


def assert_broken(result: subprocess.CompletedProcess[str]) -> None:
    # Checking for BROKEN means a config error can't pass as a caught import.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "BROKEN" in result.stdout


def test_clean_copy_keeps_all_contracts(tmp_path: Path) -> None:
    assert_kept(run_lint_imports(tmp_path))


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        ("domain", "engines"),
        ("domain", "llm"),
        ("llm", "domain"),
        ("i18n", "domain"),
        ("engines", "ui"),
        ("engines", "export"),
        ("export", "llm"),
        ("ui", "llm"),
    ],
)
def test_forbidden_import_breaks_a_contract(tmp_path: Path, importer: str, imported: str) -> None:
    assert_broken(run_lint_imports(tmp_path, planted=(importer, imported)))


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        ("engines", "llm"),
        ("engines", "domain"),
        ("export", "i18n"),
        ("ui", "engines"),
        ("ui", "export"),
    ],
)
def test_allowed_import_keeps_all_contracts(tmp_path: Path, importer: str, imported: str) -> None:
    assert_kept(run_lint_imports(tmp_path, planted=(importer, imported)))
