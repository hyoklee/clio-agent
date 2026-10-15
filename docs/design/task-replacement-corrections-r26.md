# R26: tighten the existing replacement boundaries

This packet addresses the independent Astra R24 and Claude Code Fable R25
source reviews. Astra's adjudication distinguishes demonstrated defects from
review overstatements. It does not approve the corrections below. R2 remains
the contract; no new execution owner, scheduler, database or lifecycle machine
is introduced.

| Finding | Replacement or correction | Removed behavior | Fresh proof still required |
| --- | --- | --- | --- |
| GACT calls a missing alias and interprets task activity differently | Singular and list agent aliases use the same service projection; GACT reuses its operational run-state decoder | Duplicate UI state table | Route authorization/status cases, desktop/phone service review |
| Synchronous turns poll thread liveness every 5 ms | Await the worker's result notification, then check actual final thread retirement | Full-turn liveness polling | Real-thread held-body and held-teardown cases |
| Owners reach into history's private maps and lock | Named immutable reads and serialized confirmed-write operations on the existing writer | Private history access in production callers; redundant forwarding methods | Retained behavior, outage and delivery races |
| CLIO state vocabularies are unconstrained | Typed owner-observation fields validated at the writer; raw backend status stays open | Unvalidated model-copy writes | Invalid live observations must fail before effects; historical unknown vocabulary remains readable |
| Exact/active queries enumerate retained history first | Seed from existing exact/kind/active indexes and authorize through target lineage | Broad candidate reconstruction for narrow queries | F03 read-work and replay measurements beyond 1,000 retained entries |
| Health ping can indefinitely block pending recovery | Configurable positive finite health-only timeout; readiness failures re-arm the same writer hold | Unbounded ping; final readiness outside recovery protection; impossible stdio reconnect retries | Health, outage/readiness and eventual reconciliation cases |
| Legacy assignment loses fresh-context identity | Preserve epoch/cutoff in initial migration; repair prior empty epochs idempotently | Empty-field-presence shortcut | Migration twice, fixed-context recovery |
| Catalog blueprint identity differs from resolved executable root | Capture the resolved primary agent in turn context | Incorrect primary/root comparison | Actual root/variant restoration cases |
| Historical nonlocal conversation could be admitted locally | Preserve data and refuse execution/control where this engine cannot own settlement | Silent conversion of historical placement into local execution | Data-only migration, admission/control refusal; no special relay route or qualification added |
| Partial native startup can retain an entered root | Validate client settings before entry and unwind through the existing owner shutdown | Partial-start resource leak | Faulted-start custody/cleanup case |

Production construction and static checking are separate from acceptance.
Behavioral cases are being constructed together before execution, as requested.
Both independent reviewers must assess the committed candidate. Q1–Q9, R1–R6,
required CI, migration and real-model evidence remain mandatory; old evidence
does not qualify this correction packet.
