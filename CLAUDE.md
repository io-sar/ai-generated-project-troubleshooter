# CLAUDE.md

AI Project Troubleshooter is a public Streamlit app that assesses a troubled project and produces a recovery pack. Its main audience is recruiters, so a visitor must reach a full report with no setup.

- Requirements: [SPEC.md](SPEC.md)
- Milestones and current status: [ROADMAP.md](ROADMAP.md)

## Git workflow
This repo follows [Gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow).

- `main` holds releases only. `develop` is the integration branch.
- Never commit directly to `main` or `develop`.
- Each milestone gets a `feature/*` branch from `develop`, named as in the roadmap (for example `feature/m0-foundation`).
- Feature branches reach `develop` through a pull request with CI green.
- When a milestone's branch starts, delete the feature branch from two milestones back, locally and on GitHub, and keep the previous one. For example, starting M3 deletes `feature/m1-domain`. First check that the branch is fully merged into `develop`. If it has commits that aren't there, stop and show them.
- `release/*` branches start from `develop`, and `hotfix/*` branches start from `main`. Both merge into `main`, with a tag, and back into `develop`.
- Ask for approval before every commit, push, merge or pull request. Show the branch and the proposed message first.
- Write commit messages in the plain imperative: `Add risk score calculation`.
- Keep the `Co-Authored-By: Claude` line on commits made by Claude.

## Issues and the board
- Track work as issues on the public GitHub Project board, using the task, risk and decision templates in `.github/ISSUE_TEMPLATE`.
- Each milestone has about 5 to 10 issues, and each issue belongs to a GitHub milestone.
- Use real data only. Never backdate or invent progress, risks or decisions.
- Pull requests list their issues with `Refs #n`. Closing keywords only work on the default branch (`main`), so close issues by hand once the pull request reaches `develop`.
- Ask for approval before creating, editing or closing issues. Show the text first.
- Risk ratings, status updates and retrospectives are the author's judgment. Claude only drafts them.

## Author's work
Never write these, because they must be the author's own judgment:

- "What I changed" notes.
- Corrections to the final version of a sample.

Scenario text can be drafted by AI. The author reviews all Greek UI text.

## Rules that must not break
- **Secrets:** no key in code or the repo. Visitor keys live only in `st.session_state` and never reach logs, disk, exceptions or exports.
- **API clients:** never cache them with `st.cache_resource` or `st.cache_data`.
- **Demo mode:** it makes no network calls and needs no key.
- **Untrusted input:** wrap scenario text and regeneration feedback in delimiters in prompts. LLM output must validate against the Pydantic schemas, and HTML export must autoescape all content.
- **Errors:** no key, stack trace or raw provider error reaches the UI.
- **Dependencies:** no native packages, to keep Streamlit Cloud deploys reliable.
- **UI text:** all of it goes through `t()`. Fixed values are stored as codes and translated for display only.
- **Prompts:** keep them in versioned Markdown files, never inline.
- **One report schema:** every engine returns `Report`, so the report view and export don't branch on mode.
- **Protected files:** never read `.streamlit/secrets.toml`.
- **Paid runs:** ask before running `scripts/record_sample.py`, the evals, or anything else that spends the author's API credit.
- **Recorded evidence:** never hand-edit `draft.json` or `evals/results/`. They are real recorded output.

## Decisions
- Roadmap "Decide first" items are the author's call. Ask, and give a recommendation.
- Check the SPEC non-goals before adding anything.
- If the spec needs to change, ask first.

## Code design
- Write the simplest code that meets the spec.
- Generalize when a second real case needs it, not in advance. The protocols in the spec (`AnalysisEngine`, `SectionRegenerator`, `LLMClient`) are the planned extension points.
- Dependencies point one way, with no circular imports:
  - `ui` may import `engines`, `export`, `i18n` and `domain`.
  - `engines` may import `llm` and `domain`.
  - `export` may import `i18n` and `domain`.
  - `domain`, `llm` and `i18n` import no other project package.
- Provider SDKs appear only in `llm/`. Streamlit stays in `ui/`, `app_pages/` and `streamlit_app.py`.
- Pass dependencies in. Engines receive an `LLMClient` and never create one.
- Keep logic separate from side effects. Scoring and recalculation are pure functions. Network, files, the clock and `st.session_state` stay at the edges.
- Validate at the boundaries, then trust the data. Pydantic checks LLM output and sample files as they enter the app, and inner code doesn't re-check them.
- Only `ui/state.py` changes a report.
- Fail clearly. No bare `except` and no swallowed errors. Provider errors become typed errors in `llm/errors.py`.
- Settings live in `config.py`. No magic numbers or model names in the code.
- Each business rule lives in one place, such as scoring thresholds, the RACI check and the escalation mapping.
- Keep functions small, with one job and a clear name. Comments explain why, not what.
- Fix the cause of a bug, not the symptom. Keep unrelated refactors out of a change.

**Why we don't strictly follow SOLID or DRY:** they are useful guides, but applied strictly they add abstraction this small app doesn't need, and a principle's name is too vague to check in a review. So we keep the parts that solve a real problem here, as the concrete rules above. DRY applies to business rules, which must never be duplicated. Code that only looks alike can stay separate until a second real case shows it is the same thing, because a wrong abstraction costs more than a small duplicate. SOLID's dependency inversion applies at the planned protocols, and we add no interfaces beyond them without a real need.

## Testing
- Every change comes with tests that cover normal cases, boundaries and failures.
- Tests never call real APIs, and CI needs no key.
- Engine, pipeline and UI tests mock the API with a fake `LLMClient`.
- Adapter tests replay saved real responses, so they check the providers' actual format.
- Snapshot tests use a fixed clock.

## Definition of done
- A change is done when it is tested, all checks pass, and the results are reported before asking to commit.
- A milestone is done only when every item on its "Done when" list is met and tested. Then update the status line in the roadmap.

## Writing
Repo docs are public. Write them for outside readers, in plain language.

<!-- project-init:start v0.5.0 2026-11-17 -->
## Project standards

### Project profile
Stage: MVP · Data: none stored · Interfaces: web UI · Growth: stays small · Regulation: none confirmed (GDPR, EU AI Act, EAA open) · Team: solo · Architecture: modular monolith · AI: uses LLMs · Hosting: Streamlit Community Cloud

### Commands
| Task | Command |
|---|---|
| Setup | `uv sync`, then `uv run pre-commit install` |
| Run | `uv run streamlit run streamlit_app.py` |
| Test | `uv run pytest -q` |
| Lint / format | `uv run ruff check` · `uv run ruff format` |
| Type check | `uv run mypy` |
| Import contracts | `uv run lint-imports` |

### Non-negotiables
- Never delete, skip or weaken a test to make it pass.
- Never read `.env`, key or credential files.
- For changes touching several files or the architecture, propose a plan first and wait for agreement.
- When editing existing code, follow the patterns already in that module unless a rule says otherwise.

### Standards
- Always loaded: `.claude/rules/security.md` (visitor-data isolation, web safety, dependencies), `code-quality.md` (tooling, docstrings, debt), `operations.md` (logging).
- Loaded with matching files: `testing.md` for `tests/`; `ai-llm.md` for `llm/`, `engines/`, prompts, scripts and evals; `frontend.md` for `app_pages/`, `ui/` and `streamlit_app.py`; `delivery.md` for `.github/` and pre-commit.
- On demand: `docs/standards/<topic>.md` gives each rule's reason and trade-off. Read the matching file before changing security, the LLM pipeline, CI or the architecture.

### Decisions
Architecture decisions are in `docs/adr/`. Read the relevant ADR before changing a design. Never edit an accepted ADR; supersede it. Hard-to-reverse choices (data model, provider, hosting, licence, a paid tool) get an ADR. Easy-to-reverse ones don't.
Standards planned for later milestones are in `docs/standards-adoption.md`. Don't apply them unless asked.
<!-- project-init:end · Re-run /project-init to update this block; content outside the markers is never changed by the skill. -->
