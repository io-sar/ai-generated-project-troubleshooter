# Threat model

- **Status:** Draft by Claude, for the author's review
- **Date:** 2026-11-19
- **Scope:** the app as it will be after M6 (Live AI mode), when visitors enter their own API key and their own text. Demo mode, the only mode in v0.1, makes no network calls and takes no key or free text, so most of these threats don't apply to it yet.

The model uses [STRIDE](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats): spoofing, tampering, repudiation, information disclosure, denial of service and elevation of privilege. Each threat names its mitigation and the test or rule that enforces it. **Open** marks a gap, with the issue that closes it.

## What we protect
| Asset | Why it matters |
|---|---|
| A visitor's API key | It spends the visitor's money. Losing it is the worst outcome this app can cause. |
| A visitor's scenario and report | Their project text may be confidential to their employer. |
| The visitor's browser | Model output and scenario text are shown on the page and in exported HTML files. |
| The author's API key | Used only locally, to record samples and run evals. The deployed app never has it. |
| The repo and its build | Public. Anything committed is exposed, and a tampered dependency runs with access to keys. |

## How data flows
```
Visitor's browser ──HTTPS──▶ Streamlit Community Cloud (one Python process, many sessions)
   key, scenario                   │  st.session_state (per visitor)
                                   │  LLMEngine ──▶ AnthropicClient ──HTTPS──▶ api.anthropic.com
   report, exports  ◀──────────────┘
```

**Trust boundaries**
1. Browser to app: anything the visitor sends is untrusted.
2. App to model provider: the model's answer is untrusted, because the scenario inside the prompt may steer it.
3. Session to session: all visitors share one server process, so one visitor's data must never reach another.
4. Repo and dependencies to the deployed app: the code that runs is only as safe as what is merged and installed.

**What we trust:** Streamlit Community Cloud (it runs the process and sees its memory), Anthropic's API, GitHub and the TLS between them. The app can't defend against those, so the trust notice in Live mode says so plainly.

## Threats

### Spoofing
| # | Threat | Mitigation | Enforced by |
|---|---|---|---|
| T1 | **A fake copy of the app collects keys.** The code is public, so anyone can deploy a look-alike and log what visitors paste. | The app can't stop a copy. It can make the real one easy to check and a stolen key cheap: the trust notice names the official address, links to the code, and suggests a temporary, low-limit key. | **Open:** [#66](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/66) |
| T2 | **The key is sent somewhere other than Anthropic.** The Anthropic SDK reads an `ANTHROPIC_BASE_URL` environment variable, so a variable set on the host could redirect every key. | The client factory pins the official address from `config.py`. | [tests/security/test_key_destination.py](../tests/security/test_key_destination.py) |
| T3 | **The deployed app runs on the author's key.** If the app read the local secrets file or `st.secrets`, visitors would spend the author's credit. | App code never reads them. Only the local scripts in `scripts/` do. | [tests/security/test_no_secrets_in_app.py](../tests/security/test_no_secrets_in_app.py) |

### Tampering
| # | Threat | Mitigation | Enforced by |
|---|---|---|---|
| T4 | **Prompt injection.** Scenario text tells the model to ignore its instructions, leak its prompt, or write something harmful into the report. | Scenario text and feedback go inside delimiter tags, and any delimiter tag in them is replaced, so the text can't close its block. Prompts say the delimited text is data. The model has no tools and the prompt holds no secret, so the worst case is a misleading report that only the person who wrote the scenario sees. Delimiters reduce injection but don't prevent it, so the defences below assume it can happen. | [tests/llm/test_llm_engine.py](../tests/llm/test_llm_engine.py) (`test_delimiter_tags_in_untrusted_text_are_replaced`), [tests/llm/test_prompts.py](../tests/llm/test_prompts.py) |
| T5 | **Model output carries active content.** Injected text makes the model return a script, a link or a Markdown image. An image would call an outside address as soon as the page renders. | Model output must validate against the Pydantic schemas, with one repair attempt. The HTML export autoescapes everything, and the Markdown export escapes Markdown syntax. The on-screen report escapes model text with `escape_markdown`. | Exports: [tests/export/test_export_escaping.py](../tests/export/test_export_escaping.py). Screen: rule in `.claude/rules/security.md`. **Open:** no test yet for the screen, [#67](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/67) |
| T6 | **A sample file is tampered with.** A sample in the repo carries broken or hostile data. | Sample files are validated against the schemas when loaded, and every change reaches `develop` through a reviewed pull request with CI. | [tests/unit/test_sample_engine.py](../tests/unit/test_sample_engine.py) |

### Repudiation
The app has no accounts, stores nothing, and changes nothing outside the visitor's session. There is no action a visitor could later deny that would harm anyone else, so no audit trail is needed. Logs hold metadata only (see T7), which is enough to debug a failed run.

### Information disclosure
| # | Threat | Mitigation | Enforced by |
|---|---|---|---|
| T7 | **The key or scenario leaks** into logs, error messages, exceptions, the client's text form or an export. | Logs hold only metadata such as the prompt ID, model and outcome. The SDK's own loggers are capped at WARNING, because their debug output includes request bodies. Provider errors become typed errors with no provider text. A canary key runs through the whole pipeline and must appear nowhere. | [tests/security/test_canary_key.py](../tests/security/test_canary_key.py), [tests/llm/test_logs.py](../tests/llm/test_logs.py), [tests/llm/test_anthropic_client.py](../tests/llm/test_anthropic_client.py). **Open:** the canary doesn't cover the Live mode screens yet, [#68](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/68) |
| T8 | **One visitor sees another's key or report.** All sessions share one process, so a cache or module global would share data between them. | Keys, scenarios and reports live only in `st.session_state`. App code uses no Streamlit cache, and each run builds a new client. | [tests/security/test_no_cached_clients.py](../tests/security/test_no_cached_clients.py). **Open:** a two-session Live mode test, [#68](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/68) |
| T9 | **Error details reveal internals.** A stack trace shows code paths, settings or a key in a variable. | `showErrorDetails = "none"`, and the UI shows only our own translated messages. | [tests/security/test_web_settings.py](../tests/security/test_web_settings.py) |
| T10 | **A key is committed to the public repo.** | `.streamlit/secrets.toml` is gitignored. gitleaks runs in pre-commit and on the full history in CI. Recorded fixtures and samples are checked for keys before they are saved. | gitleaks in [.pre-commit-config.yaml](../.pre-commit-config.yaml) and [CI](../.github/workflows/ci.yml), [tests/llm/test_record_sample.py](../tests/llm/test_record_sample.py), [tests/llm/test_anthropic_recorded.py](../tests/llm/test_anthropic_recorded.py). Risk tracked in [#11](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/11) |

### Denial of service
| # | Threat | Mitigation | Enforced by |
|---|---|---|---|
| T11 | **A visitor runs up cost or ties up the app** with very long text or many runs. | Runs use the visitor's own key, so the cost is theirs, not the author's. Scenario text is capped at 4,000 characters, each stage has a fixed `max_tokens` in `config.py`, and Analyze is disabled during a run. Rate limiting is out of scope for a free demo: if the shared app is overloaded, Streamlit Cloud restarts it and no data is lost, because none is stored. | [tests/unit/test_models.py](../tests/unit/test_models.py) (scenario length), `max_tokens` in [config.py](../src/troubleshooter/config.py). Analyze lock: planned in M6 |

### Elevation of privilege
| # | Threat | Mitigation | Enforced by |
|---|---|---|---|
| T12 | **Script runs in the visitor's browser** through cross-site scripting or a forged request. | Streamlit escapes text by default, and app code never renders raw HTML. Cross-site request and cross-origin protection stay on. Streamlit Cloud sets the response headers, so the app can't add a content security policy. | [tests/security/test_web_settings.py](../tests/security/test_web_settings.py) |
| T13 | **A compromised dependency or Action** runs inside the app, where it can read every key in memory. | Dependencies are pinned in `uv.lock` and `requirements.txt`, and CI checks they agree. No native packages. | Pinning: CI. **Open:** vulnerability scanning, Dependabot, SHA-pinned Actions and `SECURITY.md`, [#69](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/69) |

## Accepted risks
- **The host sees keys in memory.** Streamlit Community Cloud runs the process, so its operator could in principle read a key. The trust notice says so, and suggests a temporary, low-limit key.
- **Prompt injection can still mislead a report.** Only the visitor who wrote the scenario sees the result, and the report is advice for a human to judge, not an action the app takes.
- **No rate limiting.** The app is a free demo that stores nothing. Abuse costs the abuser's own key.

## Keeping this current
Review this model when the app gains a new input, output, provider or stored data, and before each release. A new threat gets a row here, with its test or an issue.
