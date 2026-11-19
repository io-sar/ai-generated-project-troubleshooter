"""App settings. Kept here so no path, number or model name is hard-coded elsewhere."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final


@dataclass(frozen=True)
class ModelChoice:
    """The models offered for one provider.

    Attributes:
        default: The model selected unless the user picks another.
        alternatives: The other models offered, in display order.
    """

    default: str
    alternatives: tuple[str, ...]

    @property
    def all(self) -> tuple[str, ...]:
        """Return the default followed by the alternatives."""
        return (self.default, *self.alternatives)


# Curated list from decision #15. The cheapest model is the default because visitor keys are
# paid keys, often with little credit. Claude is the only provider in v1 (ADR 0006).
MODELS = {
    "anthropic": ModelChoice(
        default="claude-haiku-5-5",
        alternatives=("claude-sonnet-5-5", "claude-opus-5-5"),
    ),
}

# Timeout and retries are chosen together (ADR 0004): one call waits at most about
# LLM_TIMEOUT_SECONDS * (LLM_MAX_RETRIES + 1). The SDK is the only layer that retries.
LLM_TIMEOUT_SECONDS = 120.0
LLM_MAX_RETRIES = 1
# How much the model reasons before answering. Thinking is always on in current Claude models.
LLM_EFFORT: Final = "medium"
# Thinking tokens count toward max_tokens, so these leave room beyond the answer itself.
DIAGNOSE_MAX_TOKENS = 8_000
GENERATE_MAX_TOKENS = 16_000
# A repair call lists at most this many validation errors, so its prompt stays small.
REPAIR_MAX_ERRORS = 20

SAMPLES_DIR = Path(__file__).with_name("samples")
PROMPTS_DIR = Path(__file__).with_name("prompts")
# The prompt version each stage uses. A new version is a new file, so old runs stay traceable.
PROMPT_VERSIONS = {"diagnose": "v1", "generate": "v1", "repair": "v1"}

REPO_URL = "https://github.com/io-sar/ai-generated-project-troubleshooter"
# Links point at develop until release 0.1 puts the docs on main; the roadmap's
# release checklist switches this.
DOCS_BRANCH = "develop"
BOARD_URL = "https://github.com/users/io-sar/projects/5"
BUILDER_LINKEDIN_URL = "https://www.linkedin.com/in/ioannis-sarantidis-52367a74/"

# Page paths are relative to the app root, as st.navigation and st.page_link expect.
ANALYZE_PAGE = "app_pages/analyze.py"
HOW_BUILT_PAGE = "app_pages/how_it_was_built.py"
