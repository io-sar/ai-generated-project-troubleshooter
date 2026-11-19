import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from troubleshooter.llm.logs import SDK_LOGGERS, quiet_sdk_loggers

APP = Path(__file__).parents[2] / "streamlit_app.py"
# The first app run imports pandas and pyarrow, which can be slow on a cold CI machine.
RUN_TIMEOUT_SECONDS = 15


@pytest.fixture
def unset_sdk_levels() -> Iterator[list[logging.Logger]]:
    """Start with the SDK loggers unset, and restore their levels afterwards."""
    loggers = [logging.getLogger(name) for name in SDK_LOGGERS]
    levels = [logger.level for logger in loggers]
    for logger in loggers:
        logger.setLevel(logging.NOTSET)
    yield loggers
    for logger, level in zip(loggers, levels, strict=True):
        logger.setLevel(level)


def test_caps_every_sdk_logger_at_warning(unset_sdk_levels: list[logging.Logger]) -> None:
    quiet_sdk_loggers()
    quiet_sdk_loggers()

    assert [logger.level for logger in unset_sdk_levels] == [logging.WARNING] * len(SDK_LOGGERS)


def test_covers_the_sdks_and_their_http_libraries() -> None:
    assert set(SDK_LOGGERS) == {"anthropic", "openai", "httpx2", "httpcore2"}


def test_leaves_the_project_loggers_alone(unset_sdk_levels: list[logging.Logger]) -> None:
    project = logging.getLogger("troubleshooter.llm.anthropic_client")
    before = project.level

    quiet_sdk_loggers()

    assert project.level == before


def test_the_app_quiets_the_sdk_loggers_on_start(unset_sdk_levels: list[logging.Logger]) -> None:
    app = AppTest.from_file(str(APP), default_timeout=RUN_TIMEOUT_SECONDS)
    app.run()

    assert not app.exception
    assert [logger.level for logger in unset_sdk_levels] == [logging.WARNING] * len(SDK_LOGGERS)
