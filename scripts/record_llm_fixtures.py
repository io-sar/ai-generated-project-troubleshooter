"""Record real Anthropic responses for the adapter tests. Local only, and it costs money.

Run with: uv run python scripts/record_llm_fixtures.py [--models MODEL ...]

The key is read from ANTHROPIC_API_KEY in the gitignored local secrets file, and is never
printed or saved. Each response is saved as its status code and JSON body only, with no
headers, under tests/llm/fixtures/anthropic/. The script stops before saving anything that
contains a key.
"""

import argparse
import json
import logging
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
import httpx2
from pydantic import BaseModel

from troubleshooter import config
from troubleshooter.domain.models import Diagnosis, Report
from troubleshooter.engines.sample_engine import load_sample
from troubleshooter.llm.anthropic_client import AnthropicClient
from troubleshooter.llm.errors import InvalidOutputError, LLMError
from troubleshooter.llm.logs import quiet_sdk_loggers

ROOT = Path(__file__).parents[1]
SECRETS = ROOT / ".streamlit" / "secrets.toml"
OUT_DIR = ROOT / "tests" / "llm" / "fixtures" / "anthropic"
PROMPT = ROOT / "tests" / "llm" / "fixtures" / "recording_prompt.md"
SAMPLE_ID = "placeholder"
INVALID_KEY = "sk-ant-invalid-recording-key"
UNKNOWN_MODEL = "claude-model-that-does-not-exist"
# Small enough that the model stops before finishing the report.
TRUNCATING_MAX_TOKENS = 200

logger = logging.getLogger("record_llm_fixtures")


class RecordingTransport(httpx2.BaseTransport):
    """Passes requests through and keeps each response's status and body."""

    def __init__(self) -> None:
        self._inner = httpx2.HTTPTransport()
        self.responses: list[tuple[int, Any]] = []

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        response = self._inner.handle_request(request)
        response.read()
        self.responses.append((response.status_code, response.json()))
        return response


def fixture_text(case: str, model: str, status: int, body: Any, keys: list[str]) -> str:
    """Return the fixture file's text, or stop if any key appears in it."""
    text = json.dumps({"case": case, "model": model, "status": status, "body": body}, indent=2)
    if any(key in text for key in keys):
        raise SystemExit(f"Stopped: the response for {case} contains a key")
    return text + "\n"


@dataclass(frozen=True)
class Recording:
    """One recording session: the real key and the prompt every case sends."""

    key: str
    system: str
    user: str

    def record(
        self,
        case: str,
        model: str,
        answer: type[BaseModel],
        max_tokens: int,
        key: str | None = None,
    ) -> None:
        """Make one call and save its raw response as `<case>.json`."""
        used_key = key or self.key
        transport = RecordingTransport()
        sdk = anthropic.Anthropic(
            api_key=used_key,
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=0,
            http_client=httpx2.Client(transport=transport),
        )
        client = AnthropicClient(sdk, model, config.LLM_EFFORT)
        try:
            client.complete_structured(
                self.system, self.user, answer.model_json_schema(), max_tokens
            )
            outcome = "ok"
        except LLMError as error:
            outcome = error.kind.value
        except InvalidOutputError:
            outcome = "invalid_output"
        status, body = transport.responses[-1]
        text = fixture_text(case, model, status, body, [self.key, used_key])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{case}.json").write_text(text, encoding="utf-8")
        logger.info("recorded case=%s model=%s status=%s outcome=%s", case, model, status, outcome)


def main() -> int:
    """Record every case, with a full report from each model asked for."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        nargs="+",
        default=[config.MODELS["anthropic"].default],
        choices=config.MODELS["anthropic"].all,
        help="Models to record a full report from (default: the default model only).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    quiet_sdk_loggers()

    sample = load_sample(config.SAMPLES_DIR, SAMPLE_ID)
    run = Recording(
        key=_read_key(),
        system=PROMPT.read_text(encoding="utf-8"),
        user=f"<scenario>\n{sample.scenario.text}\n</scenario>",
    )
    default = config.MODELS["anthropic"].default

    run.record("diagnosis-success", default, Diagnosis, config.DIAGNOSE_MAX_TOKENS)
    for model in args.models:
        run.record(f"report-success-{model}", model, Report, config.GENERATE_MAX_TOKENS)
    run.record("report-truncated", default, Report, TRUNCATING_MAX_TOKENS)
    run.record("invalid-key", default, Diagnosis, config.DIAGNOSE_MAX_TOKENS, key=INVALID_KEY)
    run.record("unknown-model", UNKNOWN_MODEL, Diagnosis, config.DIAGNOSE_MAX_TOKENS)
    return 0


def _read_key() -> str:
    with SECRETS.open("rb") as file:
        key = tomllib.load(file).get("ANTHROPIC_API_KEY", "")
    if not isinstance(key, str) or not key.strip():
        raise SystemExit("ANTHROPIC_API_KEY is missing from the local secrets file")
    return key


if __name__ == "__main__":
    sys.exit(main())
