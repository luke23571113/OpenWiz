# The three roads

Triage sorts work by risk first, then size. Read the proposed scope and what
would ship before picking a road.

| Road | Use it when | What Jake approves |
| --- | --- | --- |
| Big | Work needs design choices, multiple independently owned tickets or a dependency graph. Also use it for every always-big case below. | Grill the work, confirm the spec direction, then ask for one yes to the plan graph before any ticket starts. |
| One-card | One ordinary change fits in one ticket with a clear set of owned paths, acceptance criteria and proof. | The ticket itself is the plan. Ask for one yes to that exact card. |
| Batch | Every edit is mechanical and can be listed before asking. Each edit follows an established rule without changing behavior or requiring a design choice. | One card lists the location and change for every edit, with acceptance criteria and proof for the batch. Ask for one yes to the whole list. |

Always take the **big** road for live work, a release, publishing, a security
change, a contract another repository relies on, or any uncertainty about the
classification or whether every batch edit is mechanical. Apply this to the
whole proposal. One always-big item sends the whole card to the big road.

Every road needs exactly one affirmative approval from Jake for the exact plan
that ships. On the big road the spec confirmation settles direction and the
plan-graph approval is the go for the work. On either short road, save the yes
privately, read it back and record its pointer on the resolved decision. Silence,
a message delivery receipt or an approval for different wording cannot start or
ship the work. If the approved card changes, supersede it and take the current
card through the sort and approval again.

Use `one_card_plan` or `batch_plan` from
[the decisions contract](../../contracts/decisions.v1.md#short-road-plans).
Plan-graph checks the saved form before handoff. Keep the existing approval,
review, CI and merge rules.
