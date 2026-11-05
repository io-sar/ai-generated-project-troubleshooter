# ai-generated-project-troubleshooter
A public web app where you can paste a troubled project scenario and instantly receive a delivery assessment, risk register, stakeholder update, recovery plan, and RACI. It lets you experiment directly with my PM judgment, AI prompting, automation, and product thinking.

## How this project is managed
This project is run with the same delivery methods the app teaches, and the records are public:

- **Plan:** the [spec](SPEC.md) sets the requirements and the [roadmap](ROADMAP.md) sets the milestones.
- **Tracking:** a public [GitHub Project board](https://github.com/users/io-sar/projects/5) shows the work, the risks and the decisions. Each milestone is broken into issues.
- **Risks:** each one is an issue with the same fields as the app's risk register: likelihood, impact, owner, mitigation and escalation level.
- **Decisions:** each one is an issue, and the ones that shape the architecture also get an ADR.
- **Reviews:** each milestone ends with a status update and a short retrospective.

The code is built with AI coding tools, and the delivery judgment is mine. This RACI shows the split:

| Activity | Author | Claude |
|---|---|---|
| Scope, priorities and decisions | A, R | C |
| Code and tests | A | R |
| Sample scenario text | A | R |
| Corrections to sample reports and "What I changed" notes | A, R | |
| Review of Greek UI text | A, R | |
| Status updates and retrospectives | A, R | C |

R is responsible, A is accountable, C is consulted.
