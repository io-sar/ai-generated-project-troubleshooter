# Roadmap — AI Project Troubleshooter

A public web app that assesses a troubled project and produces a recovery pack: health ratings, risks, a recovery plan, stakeholder updates, a decision memo and a RACI matrix. It is built with AI coding tools, and the delivery judgment behind it is the author's. The full requirements are in [SPEC.md](SPEC.md).

**Current status:** requirements reviewed and planned. Next up: M0.

The first release is a public demo that needs no setup. The second adds analysis of your own project using your own API key. This is a working plan and is expected to change.

## Overview
| # | Milestone | Size | Branch | Result |
|---|---|---|---|---|
| M0 | Foundation and first deploy | S | `feature/m0-foundation` | Empty app live, CI green |
| M1 | Domain model and scoring | M | `feature/m1-domain` | Report schema and rules tested |
| M2 | Report display and export | L | `feature/m2-report-ui` | A placeholder sample renders and downloads |
| M3 | Human editing | M | `feature/m3-editing` | Edits and markers reach the export |
| M4 | AI pipeline | L | `feature/m4-ai-pipeline` | Two-stage pipeline works from a local script |
| M5 | Real samples | L | `feature/m5-samples` | 5 reviewed samples in the app |
| | **Release v0.1: public demo** | | `release/0.1.0` | Shareable with recruiters |
| M6 | Live AI mode | L | `feature/m6-live-mode` | Visitors can use their own key |
| M7 | Greek UI | S | `feature/m7-greek` | Full Greek interface |
| M8 | Evals, docs and polish | M | `feature/m8-release-prep` | Release checks complete |
| | **Release v1.0** | | `release/1.0.0` | Full spec delivered |

Sizes are relative: S is small, M is medium, L is large.

**Why this order:** the no-setup demo reaches the most people, so it ships first at v0.1. Live mode comes after it because it needs an API key. The pipeline (M4) still comes before the samples, because the samples are recorded from it.

**Git flow:** create `develop` from `main` before M0. Each milestone gets a feature branch from `develop` and merges back when its "Done when" list is complete. Each release goes through a `release/` branch into `main`, with a tag, and back into `develop`.

## M0 — Foundation and first deploy
**Goal:** prove the toolchain and hosting before building on them.

- Project setup with uv, the `src/troubleshooter` package and an exported `requirements.txt`.
- ruff, strict mypy, pytest, pre-commit and gitleaks.
- import-linter in CI, to enforce the module dependency rules in `CLAUDE.md`.
- GitHub Actions CI.
- `.gitignore` entry for `.streamlit/secrets.toml`, and `.streamlit/config.toml`.
- Bare-bones `streamlit_app.py` using `st.navigation` that imports from the package.
- First deploy to Streamlit Community Cloud, with the Python version set in the deploy settings.

**Done when**
- The deployed app loads and shows a value imported from `src/troubleshooter`.
- CI is green on a pull request.
- A fake key committed on a test branch is caught by gitleaks.

## M1 — Domain model and scoring
**Goal:** define the one contract that every other part depends on.

- Pydantic models: `Scenario`, `Diagnosis` (with input classification), `HealthScores`, `Risk` (with `signal_ids`), `RecoveryPlan`, `StakeholderUpdates`, `DecisionMemo`, `RaciRow`, `Report`.
- Fixed values stored as codes.
- Health labels and thresholds, overall rating, risk score, suggested escalation level.
- RACI check for exactly one A per activity.
- ADR 0001 for scoring.

**Decide first:** overall rating weights, the fixed score behind each label, and the mapping from risk score to escalation level.

**Done when**
- Unit tests cover thresholds and their boundaries, recalculation, the RACI rule and the escalation mapping.
- Generated JSON Schemas are checked for fit with both providers' structured output.

## M2 — Report display and export
**Goal:** the full demo experience, using one hand-made placeholder sample.

- `AnalysisEngine` protocol and `SampleEngine`.
- Sample file format and loader.
- i18n layer with `t()` and `en.yaml`, used from the start so Greek is a later add-on.
- Sample selector, Analyze button, badges and shared links (`?sample=…`).
- Health dashboard, risk register, recovery plan, stakeholder tabs with copy, decision memo, RACI and "Under the hood".
- Draft and final side by side, and the "What I changed" note.
- Markdown and HTML export with autoescaping.
- "About the builder" sidebar and a first version of "How this was built", linked from the results screen.
- Phone layout check.

**Done when**
- The placeholder sample renders fully with no network calls.
- `AppTest` covers sample selection and export.
- Export snapshot tests use a fixed clock, and HTML escaping tests pass.
- Reports read well on a real phone.

## M3 — Human editing
**Goal:** let visitors try human-in-the-loop on samples.

- `ui/state.py` as the single layer for edits and human-adjusted marks.
- Editable risk and RACI tables and health label dropdowns, on the final version only.
- Recalculation, optional notes, RACI warnings and the refresh warning.
- Edits and markers included in exports.

**Done when**
- State layer tests cover edits, added and deleted rows, out-of-range values and empty tables.
- `AppTest` confirms that an edit appears in the export with its marker.
- The AI draft can't be edited.

## M4 — AI pipeline
**Goal:** the two-stage pipeline, working from a script with no UI.

- `LLMClient` protocol, Anthropic and OpenAI adapters, and a factory that never caches clients.
- Prompts `diagnose.v1.md` and `generate.v1.md`, with untrusted input wrapped in delimiters.
- Stage 1 input classification, stage 2 skipped when it doesn't apply, one repair retry.
- Provider error mapping to sanitized messages.
- `scripts/record_sample.py`.
- Canary key test.

**Decide first:** the curated model list per provider.

**Author task:** local key in the gitignored secrets file.

**Done when**
- A local script produces a valid report from each provider.
- Adapter and pipeline tests pass against saved real responses.
- The canary key test and the no-cached-clients test pass.
- Off-topic, thin and healthy inputs are classified correctly by hand on a few examples.

## M5 — Real samples
**Goal:** real AI output, corrected with human delivery judgment.

- Scenario text and key points for all 5 samples.
- Recording each run with `scripts/record_sample.py`.
- Reviewing and correcting each final version, and writing each "What I changed" note.
- Showing how each report addresses its key points.
- Short "looks healthy" result for the healthy sample.
- Schema and invariant checks on sample files.

**Author task:** this milestone is mostly the author's. AI can draft scenarios, but the corrections and notes are the author's own judgment.

**Done when**
- All 5 samples pass the sample review checklist in SPEC section 10.
- The placeholder sample is removed.

## Release v0.1 — public demo
- README with overview, diagram, data flow and links.
- Screenshot or short GIF for the README and CV.
- Timing check of the sample path on the awake deployed app.

## M6 — Live AI mode
**Goal:** visitors can analyze their own project with their own key.

- Mode toggle, provider, model, project type, key field and text box with character counter.
- Key check before a run where the provider allows it, and help text about API keys and subscriptions.
- Trust notices by the key field and above the text box.
- Progress display, Analyze disabled during a run, diagnosis kept if stage 2 fails.
- Short results for off-topic, thin and healthy input.
- `SectionRegenerator`, `regenerate.v1.md`, locked human-adjusted rows, and "may be out of date" flags with suggestions.

**Done when**
- `AppTest` with a fake client covers a full run, each failure message and regeneration.
- Human-adjusted rows survive regeneration.
- A manual smoke test passes on each provider, including a bad key and a wrong provider's key.

## M7 — Greek UI
**Goal:** full Greek interface.

- `el.yaml`, language switch, Live output in the selected language.
- Notice that samples are in English, and the notice for Live reports after a language change.
- `?lang=el` in shared links.

**Author task:** review the Greek text.

**Done when**
- The catalog parity test passes.
- `AppTest` covers the language switch.
- Greek output validates on each provider.

## M8 — Evals, docs and polish
**Goal:** finish the engineering evidence.

- `evals/cases`, `run_evals.py` and committed results.
- `docs/ARCHITECTURE.md`, `PROMPTS.md`, `BUILT_WITH_AI.md`, remaining ADRs.
- Final "How this was built" page and README.

**Decide first:** eval settings. SPEC section 10 has the current defaults (3 runs per case per provider, 100% on schema and RACI, 90% on the rest).

**Done when**
- An eval pass meets the agreed thresholds.
- The README checklist in the success criteria is met.

## Release v1.0
- Smoke test on each provider.
- Timing check on the deployed app.
- Final read of the Greek UI.
- Tag and deploy from `main`.

## Future ideas
Not planned yet, and left out of v1 on purpose:

- Greek versions of the samples.
- File uploads, such as status reports and Jira exports.
- Integrations with Jira, Slack and email.
- Accounts and saved history.
