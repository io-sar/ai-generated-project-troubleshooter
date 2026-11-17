# ADR 0002: Quality attributes and architecture style

- **Status:** Accepted
- **Date:** 2026-11-17

## Context
The app is a public demo for recruiters, built and run by one person, with no budget for hosting or inference. The spec already sets the main constraints: the demo must reach a full report with no setup, visitor keys must never leak, and the app runs on the free tier of Streamlit Community Cloud. Naming the qualities that matter most makes the trade-offs in later decisions explicit, instead of accidental.

## Decision
The three quality attributes that drive the design, in priority order:

| # | Quality attribute | Target | How it is checked |
|---|---|---|---|
| 1 | **Security of visitor keys** | A key never reaches logs, disk, exceptions, exports or another visitor's session | Canary key test and no-cached-clients test (SPEC section 10), gitleaks |
| 2 | **Time to first report** | A visitor sees a full sample report with no setup, no key and no network calls, within 10 seconds on an awake app | `AppTest` on the sample path, timing check before each release |
| 3 | **Running cost** | Zero hosting cost and no paid inference on the deployed app | Free-tier hosting, Live mode only with the visitor's own key |

The architecture style is a **modular monolith**: one Streamlit app, with the `src/troubleshooter` package split into layers (`domain`, `llm`, `i18n`, `engines`, `export`, `ui`) whose one-way dependencies are enforced by import-linter in CI.

## Why
- One deployable app is the simplest thing that meets all three attributes, and the only shape the free hosting tier supports well.
- Layers with checked dependencies keep the domain pure and testable, and keep provider SDKs in one place, so the security rules can be tested at clear boundaries.
- Modifiability for a single maintainer comes from the layering and from CI, not from separate deployables.

## Alternatives considered
- **Gradio on Hugging Face Spaces:** similar cost, but weaker support for the editable tables the report needs.
- **FastAPI backend with a React frontend:** more UI control, but two deployables, more code and paid or more complex hosting for one person.
- **Separate services:** no independent scaling or team need justifies the network and operations cost.

## Consequences
- The app runs in one process per visitor session on a small instance, so every visitor's data must stay in their own session state.
- Features that need a server-side store, background workers or custom response headers don't fit this hosting and would need a new ADR.
- If the project outgrows the free tier or gains accounts, this ADR is superseded, not edited.
