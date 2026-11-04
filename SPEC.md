# SPEC — AI Project Troubleshooter

## 1. Goal
A free, public web app that shows how a troubled project can be assessed and recovered. For each scenario it produces health ratings, a risk register, a recovery plan, stakeholder updates, a decision memo, a RACI matrix and a downloadable report.

**Primary goal:** show recruiters that the author can use AI tools such as Claude Code, and can apply project, delivery and service management skills to fix real project problems. The repo backs this with senior engineering practice: clean architecture, typed schemas, tests, evals, CI and safe key handling.

**Secondary goal:** give people a useful first view on how to fix their own project, if a problem exists, based on the author's knowledge and AI.

**Success criteria**
- With no API key, a recruiter reaches a full report in **3 steps or fewer** (open the app, pick a sample, click Analyze) and **under 10 s**. Time runs from the Analyze click to the rendered report, on an awake deployed app.
- Each sample passes the review checklist in section 10.
- The README contains an architecture diagram, the data flow, and links to prompts, tests and ADRs, and CI is green.
- No secret is ever committed, logged or persisted, as shown by the canary key test in section 10.

## 2. Users
| Persona | Need | Time budget |
|---|---|---|
| Recruiter / talent partner (primary) | See credible output quickly, with no setup; share the link | 1–3 min |
| Hiring manager (delivery/product/eng) | Judge PM reasoning, including how the author corrected the AI; try their own scenario with a key | 5–10 min |
| Technical reviewer | Inspect code, prompts, tests, architecture | 10–30 min, mostly in GitHub |
| Person with a struggling project (secondary) | Get a first view on what to do next | 5–10 min |

## 3. User stories and acceptance criteria
1. As a recruiter, I can pick a **sample scenario** and see a complete report without signing up or entering a key.
   - All 5 samples open from the selector with no key and make no network calls.
   - Each report shows a badge saying what it is, and a link to "How this was built with Claude Code".
2. As a recruiter, I can compare the **AI draft** with the **author's final version** and read a short **"What I changed" note**.
   - Draft and final appear side by side on desktop and stacked on phones.
   - The draft is read-only.
   - The report states how it addresses each key point of the scenario.
3. As a visitor with an API key, I can switch to **Live AI mode**, choose **Claude or OpenAI**, pick a **project type** (software delivery, AI implementation, service migration, product launch), paste my own scenario and get an AI-generated analysis.
   - Free text is available only in Live mode, with a hard limit of 4,000 characters and a visible counter.
   - The key field is masked and the key lasts only for the session.
   - The report cites facts from the scenario.
   - Analyze is disabled while a run is in progress.
4. As a Live-mode user, I am told when my text isn't a troubled project.
   - Off-topic or too-thin text gets a short request for details and no full report.
   - A healthy project gets a brief summary with things to watch.
   - Stage 2 is skipped in both cases.
5. As a user, I can view a **health dashboard** with five dimensions: schedule, scope, quality, risk control and stakeholder confidence.
   - Each dimension shows a word label (Good, Problematic or At Risk), its colour and a one-line rationale.
   - Numeric scores appear only in "Under the hood".
6. As a user, I can **edit** the risk register and RACI tables and **override** a health label, on the final version of a sample or on a Live report.
   - Each changed row or label is marked human-adjusted, in the app and in the export.
   - The overall rating recalculates.
   - The AI rationale stays visible next to an optional note.
   - A RACI row without exactly one A is highlighted with a warning, and the export is allowed and shows the issue.
7. As a Live-mode user, I can **regenerate one section** with feedback (e.g. "make the exec update shorter and more direct").
   - Human-adjusted rows are kept unchanged.
   - Related sections get a "may be out of date" flag with a suggestion on how to update them.
8. As a user, I can **copy** any stakeholder update and **download** the report as Markdown or print-ready HTML.
   - All three audience updates (Executive, Delivery team, Customer) appear in tabs, each with a copy control.
   - Downloads include human edits and their markers.
9. As a Greek-speaking user, I can switch the **UI language to Greek**.
   - All UI text is in Greek, and Live output is in Greek.
   - Samples stay in English, with a short notice saying so.
   - If the language changes after a Live run, the report stays in its original language with a notice.
10. As any visitor, I can open an **"About the builder"** sidebar and a **"How this was built"** page.
    - They link to the repo, prompts, tests and architecture docs.
11. As a recruiter, I can open a **shared link** to a specific sample.
    - A link such as `?sample=vendor&lang=el` opens that sample in that UI language.

## 4. MVP scope (v1)
**Modes**
- **Demo (default):** a selector with 5 fixed samples. The scenario text can't be edited, and no key is needed.
- **Live AI:** free text, project type select, provider select, model select and a password-type key field.

**Samples** (English only; picked by ID; always show the recorded run, including in Live mode)
1. Scope creep on a fixed budget
2. Failed go-live with outages
3. Vendor dependency slipping
4. Key people leaving
5. A healthy project, showing the short "looks healthy" result

Each sample is a real recorded AI run, generated once by the author with a local script, then reviewed and corrected. It stores the scenario and its key points, the diagnosis, the raw AI draft, the author's final version and a "What I changed" note.

**Badges:** every report shows either "Recorded AI run, reviewed by the author" or "Live AI".

**Output** (tabs or sections)
- **Health dashboard:** 5 dimensions and an overall rating. Higher scores are always healthier. Scores run 0–100 under the hood. The display shows Good (Green, 70+), Problematic (Amber, 40–69) or At Risk (Red, under 40), with a one-line rationale.
- **Risk register:** ID, description, likelihood (1–5), impact (1–5), risk score (likelihood × impact, 1–25), owner (role), mitigation, escalation level (Team / PM / Sponsor / Steering) and `signal_ids` linking back to the diagnosis. Escalation level is suggested from the risk score and can be edited.
- **Recovery plan:** 3 two-week sprints over 6 weeks: Stabilize, Recover, Sustain. Each action has an owner and a success signal. The app and report state that sprints are sequenced for the best fix and use of resources.
- **Stakeholder updates:** Executive, Delivery team and Customer variants, in tabs. Copying uses `st.code`.
- **Decision memo:** context, 2–4 options with trade-offs, recommendation, success metrics.
- **RACI matrix:** activities × roles with R/A/C/I, stored as rows. Each activity should have exactly one A.
- **Under the hood** expander: numeric scores, diagnosis JSON, extracted signals, engine used, prompt version, and latency and tokens for Live runs. It works on samples and Live reports.

**Human in the loop**
- `st.data_editor` for risks and RACI, and a label dropdown for health overrides. Each label maps to a fixed score behind the scenes.
- Live mode only: "Regenerate section with feedback" per section.
- A visible warning says that edits are lost on refresh, so download first.

**Export**
- Markdown and standalone HTML (inline CSS, print stylesheet, browser Print → PDF) from Jinja2 templates. Each export includes a timestamp, the report's badge and per-item human-adjusted markers.

**Live failure handling**
- Each failure gets a specific message: invalid key, wrong provider's key, no credit, low rate limit, model not available, timeout, refusal, truncated response.
- If stage 2 fails, the diagnosis is kept and a retry repeats only stage 2.

**Visitor keys vary**
- The app does not assume what a key can do. It may be on a free or limited tier, or lack access to a given model.
- It offers a curated list of tested models and checks the key before a run where the provider allows it.
- Help text explains that a paid chat subscription is not an API key.

**Trust notices**
- By the key field: a link to the code and a suggestion to use a temporary, low-limit key.
- Above the text box: do not paste confidential information; the text is sent to the chosen provider.

**i18n**
- EN/EL UI strings. In Live mode the LLM is told to answer in the selected UI language. Fixed values (escalation levels, R/A/C/I, labels) are stored as codes and translated for display only.

**Device support**
- Reports must read well on phones. Editing is a desktop feature.

## 5. Non-goals (v1)
- User accounts, saved history, databases or analytics on scenario content.
- File uploads (status reports, Jira exports, PDFs).
- Integrations (Jira, Slack, email, calendar). Copy and download only.
- Pasting your own scenario without an API key.
- The deployed app using the author's API key, or any paid hosted inference. The author's key is used only locally, to record samples and run evals.
- Greek versions of the samples.
- Native PDF generation (HTML → browser print instead).
- Real-time collaboration and multi-user editing.
- Fine-tuning, RAG or vector stores.

## 6. Constraints
- **Hosting:** Streamlit Community Cloud from a public GitHub repo, on the free tier (≈1 GB RAM). We choose not to use native packages, to keep deploys reliable. The Python version is set in the deploy settings.
- **Cold starts:** the app can sleep when unused, so the 10-second target applies to an awake app. The README and the CV link include a screenshot or short GIF as a fallback.
- **Secrets:** no key in code or the repo. Visitor keys live only in `st.session_state` and are never logged, written to disk, or included in exceptions or exports. API clients are never cached with `st.cache_resource` or `st.cache_data`. `.streamlit/secrets.toml` is gitignored and is for local recording and eval scripts only; the deployed app never reads it. Gitleaks runs in pre-commit and in CI.
- **Safety:** scenario text and regeneration feedback are untrusted. Both are wrapped in delimiters in prompts, and LLM output must validate against the Pydantic schemas (with one repair retry). Delimiters reduce prompt injection but don't prevent it, so HTML export must autoescape all content. No key, stack trace or raw provider error reaches the UI.
- **Cost/latency:** Demo mode needs zero network calls. A Live run is 2 LLM calls normally and up to 4 with repair retries. Each regeneration is 1 call, or 2 with a retry.

## 7. Tech stack options & trade-offs
| Concern | Chosen | Alternatives considered | Why |
|---|---|---|---|
| UI / hosting | **Streamlit** on Community Cloud | Gradio on HF Spaces; FastAPI + React on Vercel/Render | Free one-click deploy from GitHub and fast to build data tables and editors. Trade-off: less UI control, and full reruns need care with state. |
| Language | **Python 3.12** | — | Native to Streamlit and both SDKs. |
| Schemas | **Pydantic v2** | dataclasses, TypedDict | Validation, JSON Schema generation for structured LLM output, and one contract shared by all engines. |
| LLM access | **Official `anthropic` + `openai` SDKs behind an `LLMClient` protocol** | LiteLLM; LangChain | Thin, explicit adapters show design skill and keep structured output reliable (Claude tool use / OpenAI JSON-schema response format). Trade-off: two adapters to maintain, and schemas must stay simple enough for both providers. |
| Prompts | **Versioned Markdown files** (`prompts/diagnose.v1.md`, …) | Inline strings; a prompt framework | Reviewable in GitHub and diffable; the version is recorded in the output. |
| Templating/export | **Jinja2** → MD/HTML | WeasyPrint/fpdf2 PDF | No native dependencies, so deploys are reliable. |
| i18n | **YAML string catalogs + `t()` helper** | gettext/Babel | Simple, and parity between languages is checkable in tests. Trade-off: no pluralization rules (not needed). |
| Tooling | **uv** (dev) + exported `requirements.txt` (deploy), **ruff**, **mypy (strict)**, **import-linter**, **pytest**, **pre-commit**, **GitHub Actions** | pip-tools, poetry | Modern, fast, and Streamlit Cloud reads `requirements.txt`. |

## 8. Proposed architecture
```
streamlit_app.py            # entry: page config, st.navigation, sidebar
app_pages/
  analyze.py                # main page: samples, Live input, report
  how_it_was_built.py       # AI-tooling story, links to docs/prompts/tests
src/troubleshooter/
  domain/models.py          # Scenario, Diagnosis, HealthScores, Risk, RecoveryPlan,
                            # StakeholderUpdates, DecisionMemo, RaciRow, Report
  engines/
    base.py                 # AnalysisEngine protocol:
                            #   diagnose(Scenario) -> Diagnosis
                            #   generate(Scenario, Diagnosis) -> Report
                            # SectionRegenerator protocol:
                            #   regenerate(Scenario, Diagnosis, Report, section, feedback)
                            #     -> Report
    sample_engine.py        # returns recorded samples (AnalysisEngine only)
    llm_engine.py           # two-stage Live pipeline; also a SectionRegenerator
  llm/
    base.py                 # LLMClient protocol: complete_structured(system, user, schema)
    anthropic_client.py
    openai_client.py
    factory.py              # provider + key -> client (never cached)
    errors.py               # provider errors -> friendly, sanitized messages
  prompts/                  # diagnose.v1.md, generate.v1.md, regenerate.v1.md
  samples/                  # <id>/scenario.yaml, diagnosis.json, draft.json,
                            # final.json, changes.md
  export/                   # renderer.py + templates/report.md.j2, report.html.j2
  i18n/                     # en.yaml, el.yaml, t()
  ui/
    state.py                # single tested layer for edits and human-adjusted marks
                            # plus components: dashboard, tables, updates, under_the_hood
scripts/
  record_sample.py          # local only: runs the pipeline and saves a sample draft
tests/
  unit/                     # models, RACI rule, scoring, recalculation, state layer
  samples/                  # schema and invariant checks on sample files
  export/                   # snapshots with a fixed clock; HTML escaping
  llm/                      # adapters & pipeline against saved real responses
  security/                 # canary key test; no cached API clients
  ui/                       # AppTest: sample selection, editing, export, language switch
  test_i18n_parity.py       # en/el keys match
evals/
  cases/*.yaml, run_evals.py, results/
docs/
  ARCHITECTURE.md (+ Mermaid diagram), PROMPTS.md, BUILT_WITH_AI.md, adr/0001-…md
.github/workflows/ci.yml    # ruff, mypy, import-linter, pytest, gitleaks
.streamlit/config.toml      # theme; secrets.toml gitignored
```

The package is installed through `requirements.txt` so `src/` imports work on Streamlit Cloud. A bare-bones app is deployed early to prove this.

**Data flow**
- **Demo:** sample ID → `SampleEngine` → stored diagnosis, draft and final → `st.session_state`.
- **Live:** UI → `Scenario` → `LLMEngine.diagnose` → `Diagnosis`, which classifies the input as troubled, healthy, too thin or off-topic. Only a troubled project goes on to `LLMEngine.generate` → `Report` → `st.session_state`.
- **Both:** `ui.state` applies edits and human-adjusted marks → `export.renderer` → MD/HTML download.

**Key design points**
- **Same report display in every mode:** every engine returns the same `Report` schema, so the report view and export don't branch on mode. Input controls and the regenerate action do differ.
- **Two-stage LLM:** stage 1 returns a `Diagnosis`. Stage 2 generates the `Report` from scenario + diagnosis.
- **Regeneration:** receives the scenario, diagnosis, current report and feedback. Human-adjusted rows are passed as fixed. Related sections are flagged, not changed.
- **Structured output:** the JSON Schema is derived from the Pydantic models, kept within what both providers support. If validation fails, one repair retry is made, then a friendly error.
- **Explainability:** "Under the hood" shows signals, diagnosis and prompt version, so the reasoning is visible in the app.

## 9. Open items for implementation
- The curated model list per provider (confirm at build time; configurable in `config.py`).
- Weights for the overall health rating, the fixed score behind each label, and the mapping from risk score to escalation level (documented in an ADR).
- Scenario text and key points for the 5 samples, then recording and review.

## 10. Quality and verification
**Sample review checklist** (before a sample ships)
- Every key point of the scenario is addressed, and the report states how.
- The "What I changed" note is present and accurate.
- All schema and invariant checks pass.

**Automated, in CI**
- Unit tests for models, the RACI rule, scoring, recalculation and the state layer.
- Schema and invariant checks on all sample files.
- Export snapshots with a fixed clock, and HTML escaping tests.
- Adapter and pipeline tests against saved real API responses.
- `AppTest` UI tests for sample selection, editing, export and language switch.
- Security tests:
  - a fake canary key must never appear in logs, exceptions, exports or session dumps
  - API clients must never be cached
- EN/EL catalog parity.

**Manual, before each release**
- Evals, run by the author on their own key: 3 runs per case per provider, with results committed under `evals/results/`.
  - Schema validity and the one-A RACI rule must pass 100%.
  - Other rubric checks must pass at least 90%, including that each risk's `signal_ids` exist in the diagnosis.
- A smoke test on each provider.
- A timing check of the sample path on the awake deployed app.
- The author's review of the Greek UI text.
