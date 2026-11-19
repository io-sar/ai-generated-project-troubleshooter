"""Keeps the provider libraries' own logs free of visitor content.

At DEBUG level the SDKs log each request's body, which holds the scenario text, and the
full traceback of network errors. The project never logs scenario text, so these loggers
are capped at WARNING whatever level the rest of the app runs at.
"""

import logging

SDK_LOGGERS = ("anthropic", "openai", "httpx2", "httpcore2")


def quiet_sdk_loggers() -> None:
    """Cap the provider libraries' loggers at WARNING. Safe to call more than once."""
    for name in SDK_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
