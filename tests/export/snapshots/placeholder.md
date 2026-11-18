# Placeholder\: CRM migration running late

Report type: **Placeholder, not a real run**

Generated: 2026\-01\-02 03\:04 UTC

## Scenario

We are moving our customer support team from an on\-premise CRM to a cloud service\. Cutover was planned for 1 March and has already moved twice\. A trial data load found that 12% of customer records fail validation, mostly duplicate contacts and missing country codes\. The only database administrator who knows the old schema has handed in their notice and leaves in five weeks\. The support manager says agents haven't been trained yet and is worried about the busy season starting in May\. The sponsor still expects the old system to be switched off by the end of April to avoid another licence renewal\.

### Key points

- Cutover has slipped twice and the licence deadline is fixed\.
- Data quality blocks the migration\.
- The only person who knows the old schema is leaving\.
- Agents are untrained ahead of the busy season\.

## Health dashboard

Overall: **Problematic**

| Dimension | Status | Rationale |
|---|---|---|
| Schedule | At Risk | Cutover has slipped twice and the end\-of\-April deadline is close\. |
| Scope | Problematic | Scope is stable\: the same CRM features are being moved\. |
| Quality | Problematic | 12% of records fail validation in the trial load\. |
| Risk control | Problematic | Risks are known but have no owners or dates yet\. |
| Stakeholder confidence | At Risk | The sponsor's date and the support manager's concerns pull in opposite directions, and nobody has decided between them\. |

## Risk register

| ID | Risk | Likelihood | Impact | Score | Owner | Mitigation | Escalation | Signals |
|---|---|---|---|---|---|---|---|---|
| R1 | Schema knowledge is lost when the database administrator leaves\. | 4 | 5 | 20 | IT manager | Pair a second engineer with the administrator and record the schema mapping\. | Steering | S3 |
| R2 | Bad records stop the final data load\. | 4 | 4 | 16 | Data lead | Clean duplicates and country codes before the next trial load\. | Sponsor | S2 |
| R3 | Untrained agents slow down support in the busy season\. | 3 | 3 | 9 | Support manager | Run training sessions in the two weeks before cutover\. | PM | S4 |
| R4 | The licence deadline forces cutover before the data and agents are ready\. | 4 | 4 | 16 | Sponsor | Ask the vendor for a month\-by\-month licence extension before the decision meeting\. | Sponsor | S5, S4 |

## Recovery plan

The three sprints are sequenced for the best fix and use of resources\.

### Sprint 1, weeks 1–2\: Stabilize

Protect the knowledge and data the migration depends on\.

| Action | Owner | Success signal |
|---|---|---|
| Start a knowledge handover from the database administrator\. | IT manager | A second engineer can explain every mapped table\. |
| Classify all failing records by cause\. | Data lead | Every failing record has a known cause\. |

### Sprint 2, weeks 3–4\: Recover

Get the data and the people ready for cutover\.

| Action | Owner | Success signal |
|---|---|---|
| Fix duplicates and missing country codes, then rerun the trial load\. | Data lead | Under 1% of records fail validation\. |
| Train all agents on the new CRM\. | Support manager | Every agent completes training\. |

### Sprint 3, weeks 5–6\: Sustain

Cut over safely and keep support running\.

| Action | Owner | Success signal |
|---|---|---|
| Cut over with a tested rollback plan\. | Project manager | Support runs on the new CRM with no lost tickets\. |

## Stakeholder updates

### Executive

The CRM migration will miss the end\-of\-April switch\-off\. Data quality and untrained agents make an April cutover unsafe in the busy season\. We recommend extending the licence by two months and cutting over in June\. Decision needed at the next steering meeting\.

### Delivery team

Our focus for the next two weeks is the schema handover and sorting failing records by cause\. New feature requests are on hold until cutover\.

### Customer

We are moving our support system to a new platform\. You may see a short change in how we contact you, and we will tell you before it happens\.

## Decision memo

**Context**

The old CRM licence ends in April, but data quality and training mean a safe cutover before then is unlikely\.

| Option | Trade\-offs |
|---|---|
| Keep the April date | Avoids a licence renewal, but risks bad data and untrained agents at the start of the busy season\. |
| Extend the licence by two months | Costs a renewal, but allows clean data and trained agents before cutover\. |

**Recommendation**

Extend the licence by two months and cut over in June\.

**Success metrics**

- Under 1% of records fail validation\.
- All agents trained before cutover\.

## RACI matrix

| Activity | IT manager | Database administrator | Project manager | Data lead | Data analyst | Support manager | Sponsor | Check |
|---|---|---|---|---|---|---|---|---|
| Schema handover | A | R | I |  |  |  |  |  |
| Data cleaning |  |  |  | A | R | C |  |  |
| Cutover decision |  |  | R |  |  | C | A |  |

## What I changed

*Placeholder note, written by Claude to test the layout. The notes on real samples are the author's own.*

- **Added risk R4** for the fixed licence deadline. The draft named it in the decision memo but never put it in the risk register.
- **Raised R2's likelihood from 3 to 4.** One record in eight failing validation is not a medium-likelihood problem.
- **Lowered stakeholder confidence to At Risk.** The sponsor and the support manager want different things, and that conflict is the real blocker.
- **Rewrote the executive update** to lead with the decision needed, not the history.
- **Gave data cleaning a Responsible role** in the RACI. The draft had an owner but nobody doing the work.
