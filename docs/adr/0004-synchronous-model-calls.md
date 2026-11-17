# ADR 0004: Synchronous model calls with timeouts

- **Status:** Accepted
- **Date:** 2026-11-17

## Context
In Live mode, a run makes two model calls (diagnosis, then report), and up to four with repair retries (SPEC section 6). Each call can take many seconds and its duration is unpredictable. The usual advice for slow model calls is to stream the answer or to run the work as a background job, so a request isn't held open.

This app is different from a typical web service in three ways:
- Streamlit runs each visitor's script in its own session. A long call blocks only that visitor's run, not a shared worker pool.
- Both calls return structured output that must be complete before it can be validated against the Pydantic schemas, so streaming partial tokens gives the visitor little.
- Background jobs would need a worker and a job store, which the free hosting tier doesn't offer and the spec rules out (no databases in v1).

## Decision
Model calls run synchronously inside the Streamlit run, behind a progress display, with the Analyze button disabled during the run (ROADMAP M6). Every call has a timeout set in `config.py`. Transient errors are retried in one layer only, by the provider SDK with an explicit `max_retries`, and the schema-repair retry stays separate. If stage 2 fails, the diagnosis from stage 1 is kept.

## Alternatives considered
- **Streaming tokens to the page:** little value when the output is a JSON object that is only usable once complete and validated.
- **Background jobs with status polling:** needs infrastructure beyond the hosting and the spec, for a run that a single visitor waits for anyway.

## Consequences
- The longest wait a visitor can see is bounded by the timeouts and the retry limits, so those values must be chosen together in `config.py`.
- Calls without a timeout or with stacked retries are treated as bugs.
- If runs regularly get too slow for a visitor to wait, or the hosting changes, this decision is revisited in a new ADR.
