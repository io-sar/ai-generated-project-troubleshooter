"""Loads a local script as a module, the way `python scripts/<name>.py` would run it."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).parents[1] / "scripts"


def load_script(name: str) -> ModuleType:
    """Import `scripts/<name>.py`, with the scripts folder on the path for its own imports."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))
