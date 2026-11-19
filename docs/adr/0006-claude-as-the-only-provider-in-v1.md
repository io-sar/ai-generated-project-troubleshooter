# ADR 0006: Claude as the only provider in v1

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
The spec planned two model providers, Anthropic and OpenAI, behind one `LLMClient` protocol, so visitors could use either kind of key in Live mode (SPEC section 7).

The author pays for all development runs with their own API credit: the adapter recordings in M4, the five samples in M5 and the evals in M8, which run 3 times per case for each provider. Neither provider has a free API tier, so a second provider means a second credit purchase and roughly doubles the runs. The development budget is small.

The design already keeps a second provider cheap to add. Engines depend only on the `LLMClient` protocol, the provider SDKs are confined to `llm/` by an import contract, and the report schema is checked against both providers' structured-output rules.

## Decision
Claude is the only provider in v1. The OpenAI adapter, its model list and its factory branch are not built. The OpenAI half of the model list decision (#15) is deferred with it.

These stay in place, because they cost nothing and keep the door open:
- the `LLMClient` protocol and the `Provider` code
- the import contract that keeps `openai` out of every package but `llm/`
- the OpenAI rules in the schema fit test, so the report schema stays portable
- the wrong-provider-key check, since visitors may still paste an OpenAI key

## Alternatives considered
- **Both providers, as planned:** the widest reach for visitors, but double the development runs and a second credit purchase.
- **An OpenAI placeholder that raises "not built yet":** dead code, and the UI would have to hide a provider it can't use.

## Consequences
- Visitors with only an OpenAI key can't use Live mode in v1. The help text tells them a Claude API key is needed.
- The M4 to M8 runs, samples and evals need only Anthropic credit.
- Adding OpenAI later is one adapter with its tests, one `Provider` member, one `config.MODELS` entry and one factory branch. This ADR is then superseded.
- "OpenAI as a second provider" is listed under the roadmap's future ideas.
