from pathlib import Path

import pytest

from troubleshooter import config
from troubleshooter.config import ModelChoice

ROOT = Path(__file__).parents[2]
CONFIG_FILE = ROOT / "src" / "troubleshooter" / "config.py"
# Code that may need a model ID. Tests are left out, since they may name models on purpose.
SCANNED = [ROOT / "src", ROOT / "app_pages", ROOT / "scripts", ROOT / "streamlit_app.py"]

ALL_MODEL_IDS = [model for choice in config.MODELS.values() for model in choice.all]


def test_each_provider_offers_the_decided_models() -> None:
    assert config.MODELS["anthropic"].default == "claude-haiku-5-5"
    assert config.MODELS["openai"].default == "gpt-6-luna"
    assert set(config.MODELS) == {"anthropic", "openai"}


def test_all_lists_the_default_first() -> None:
    choice = ModelChoice(default="a", alternatives=("b", "c"))

    assert choice.all == ("a", "b", "c")


def test_a_provider_with_no_alternatives_offers_only_its_default() -> None:
    assert ModelChoice(default="a", alternatives=()).all == ("a",)


@pytest.mark.parametrize("provider", sorted(config.MODELS))
def test_default_is_not_repeated_among_alternatives(provider: str) -> None:
    choice = config.MODELS[provider]

    assert choice.default not in choice.alternatives


def test_model_ids_are_unique_across_providers() -> None:
    assert len(ALL_MODEL_IDS) == len(set(ALL_MODEL_IDS))


@pytest.mark.parametrize("model", ALL_MODEL_IDS)
def test_model_ids_are_not_floating_aliases(model: str) -> None:
    assert model.strip() == model
    assert model
    assert "latest" not in model


def test_model_ids_appear_only_in_config() -> None:
    assert _hard_coded_models([p for p in SCANNED if p.exists()]) == []


def test_the_scan_reports_a_hard_coded_model(tmp_path: Path) -> None:
    planted = tmp_path / "pkg" / "planted.py"
    planted.parent.mkdir()
    planted.write_text(f'MODEL = "{ALL_MODEL_IDS[0]}"\n', encoding="utf-8")
    (tmp_path / "clean.py").write_text("MODEL = config.MODELS\n", encoding="utf-8")

    assert _hard_coded_models([tmp_path]) == [(planted, ALL_MODEL_IDS[0])]


def _hard_coded_models(paths: list[Path]) -> list[tuple[Path, str]]:
    """Return each (file, model ID) where a Python file other than config.py names a model."""
    files = [
        p for path in paths for p in ([path] if path.is_file() else sorted(path.rglob("*.py")))
    ]
    return [
        (file, model)
        for file in files
        if file != CONFIG_FILE
        for model in ALL_MODEL_IDS
        if model in file.read_text(encoding="utf-8")
    ]
