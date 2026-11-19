# ADR 0005: Human edit markers live on the report

- **Status:** Accepted
- **Date:** 2026-11-18

## Context
In M3, visitors can edit the risk register and the RACI matrix and override health labels on a report's final version (SPEC section 3, story 6). Each changed item must be marked "human-adjusted" in the app and in both exports, and a health override can carry an optional note beside the AI rationale. Later, Live-mode regeneration must keep human-adjusted rows unchanged (story 7).

The export may import only `domain` and `i18n`, and every engine returns one `Report`, so the report view and export never branch on mode. Wherever the markers are kept, the export has to be able to read them.

## Decision
The markers are fields on the report models themselves:

- `Risk`, `RaciRow` and `DimensionHealth` get `human_adjusted`, which is false by default.
- `DimensionHealth` also gets an optional `note`. Only health dimensions have an AI rationale for a note to sit beside.

The fields are hidden from the JSON Schema with Pydantic's `SkipJsonSchema`, so the schema sent to the LLM doesn't offer them. Only `ui/state.py` sets them, as it does for every other change to a report.

## Alternatives considered
- **A separate record of edits, kept next to the report:** the export and, later, regeneration would each need a second input and code to match edits to rows by ID. That adds code to every consumer and can get out of step when rows are added or deleted.
- **A wrapper model around `Report`:** the same matching problem, and a second report-like type that the "one report schema" rule is meant to avoid.

## Consequences
- The export and regeneration read markers straight from the report, with no matching code.
- Sample files and recorded drafts load unchanged, because the fields have defaults.
- A test checks that the LLM output schemas never contain the marker fields.
- The schema hides the fields, but Pydantic still accepts them in input. Strict structured output keeps the model to the schema, but the M4 pipeline must still reject a model response that sets them, so the AI can't mark its own output as human-adjusted.
