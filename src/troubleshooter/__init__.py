"""AI Project Troubleshooter: assesses a troubled project and produces a recovery pack."""

from importlib.metadata import version

# Read from the installed package metadata, so pyproject.toml stays the one place the version lives.
__version__ = version("ai-project-troubleshooter")
