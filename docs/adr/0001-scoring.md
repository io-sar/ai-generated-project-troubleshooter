# ADR 0001: Health and risk scoring

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decision issue:** [#14](https://github.com/io-sar/ai-generated-project-troubleshooter/issues/14)
- **Code:** [`domain/scoring.py`](../../src/troubleshooter/domain/scoring.py)

## Context
Each report rates a project on five health dimensions: schedule, scope, quality, risk control and stakeholder confidence. Each dimension has a score from 0 to 100, where higher is always healthier. The app shows a word label instead of the number:

| Label | Colour | Score |
|---|---|---|
| Good | Green | 70 and above |
| Problematic | Amber | 40 to 69 |
| At Risk | Red | under 40 |

The spec left three rules open:

1. How the five dimensions combine into one overall rating.
2. Which score a dimension takes when a person overrides its label. People pick a label, not a number, but the overall rating needs a number.
3. How a risk's score (likelihood × impact, from 1 to 25) suggests who the risk should be escalated to.

These rules decide what a reader sees first, so they need to be simple to explain and hard to misread.

## Decision

### 1. Overall rating: equal weights, with a red cap
The overall score is the plain average of the five dimension scores, rounded to a whole number. It uses the same bands as each dimension.

One rule sits on top: **the overall can't be Good while any dimension is At Risk.** In that case it shows Problematic.

*Example:* scores of 90, 90, 90, 90 and 20 average 76. On its own, 76 would show Good. Because one dimension is At Risk, the overall shows Problematic.

### 2. Label overrides: a fixed score near the middle of each band
| Label | Score used |
|---|---|
| Good | 85 |
| Problematic | 55 |
| At Risk | 15 |

### 3. Escalation: the common 5×5 risk matrix split
| Risk score | Suggested escalation level |
|---|---|
| 1–4 | Team |
| 5–9 | PM |
| 10–16 | Sponsor |
| 17–25 | Steering |

Only three combinations reach Steering: likelihood 4 with impact 5, likelihood 5 with impact 4, and 5 with 5. The level is a suggestion, and people can change it on any risk.

## Why

- **Equal weights:** a weighted average looks more precise than the input really is. Which dimension matters most depends on the project, and five equal parts are easy to explain to anyone reading the report.
- **The red cap:** a plain average can hide one failing dimension behind four healthy ones. A project whose quality is collapsing should never show a green overall. The cap fixes this with one rule, without giving up equal weights.
- **Override scores:** each value sits inside its own band, so an overridden label always reads back as the label that was chosen. Good and Problematic sit near the middle of their bands, so the effect of an override on the overall is predictable. At Risk is set low in its band on purpose: better safe than sorry. When someone judges a dimension to be At Risk, the overall should feel it. With four dimensions at 60 and one overridden to At Risk, the overall is 51 instead of 52 at the band's middle. The other labels aren't lowered, so the scoring stays cautious without being alarmist.
- **Escalation bands:** this split is the one most project and risk teams already use for a 5×5 matrix, so readers can check it against their own practice. Steering only sees risks that are both likely and severe.

## Alternatives considered

- **Overall:** a plain average without the cap was rejected because it can hide a red dimension. Higher weights on schedule and stakeholder confidence were rejected because the weights would be hard to justify across project types.
- **Override scores:** 85 / 55 / 20 puts each value at about the middle of its band, which is neutral rather than cautious. 85 / 55 / 25 and 80 / 55 / 25 are less cautious still. The band floors, 70 / 40 / 0, were rejected as too pessimistic, because they drag the overall down after any override, including a Good one.
- **Escalation:** escalating earlier (Steering from 15) was rejected because it sends too many risks to senior people. Escalating later (Steering only at 25) was rejected because it keeps severe risks too low.

## Consequences

- All the numbers live in one place, `domain/scoring.py`, and tests cover every band edge, so changing a rule is a deliberate, visible change.
- The overall rating and risk scores are always calculated, never stored, so they can't disagree with the rules.
- Because of the cap, the overall label can be lower than its own score suggests. "Under the hood" shows the numbers, so this stays visible and explainable.
- Changing any of these rules later means a new ADR that replaces this one.
