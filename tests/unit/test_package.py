import re
import tomllib
from pathlib import Path

import troubleshooter

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    expected = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert troubleshooter.__version__ == expected


def test_version_is_a_valid_release_string() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", troubleshooter.__version__)
