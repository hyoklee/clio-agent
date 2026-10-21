# R48: Core-first transcript recording

This packet addresses the R47 end-to-end source-review blocker. It is not accepted
review or live qualification. The task execution families remain native
FastMCP/Docket for ordinary workloads and the conversation engine for assignments.
No task registry, scheduler, execution driver, mailbox or admission policy is added.

## Replacement boundary

- Normal resident and durable transcript reads use Core with the optional JSON cache
  enabled or disabled. Reads do not import missing rows or replace a lane.
- Remove the runtime repair/backfill scheduler, its in-flight set, deferred whole-message
  writer and duplicate final-envelope writer. The existing minter records streaming seals;
  one completed-message writer confirms the final envelope.
- Append/extend/intentional replace confirm Core first. JSON errors are cache lag.
  Recording recovery re-seeds aggregates when a write reply was lost.
- Finalization constructs output once. A recording outage retains that immutable message
  and original owner identity through existing CoreRecovery and the conversation owner's
  recording hold. Retry never repeats inference, grounding, tools or finalization.
  Normal, failed-turn and plan-approval publication follows confirmed recording.
- Intentional clear/rewind changes a visibility identity in the existing generation pointer.
  Accepted-input splices preserve it. Stale volatile output cannot recreate removed content.
  No separate mutation store is introduced.
- Boot retains legacy JSON before reconciliation/cache updates, then reconciles interruptions
  and seeds metrics from Core. Concurrent asynchronous attach joins the existing boot.
  Task startup reuses the confirmed TaskHistory writer constructed during attachment.

## Legacy custody

Original JSON, duplicate occurrence order and deterministic occurrence identities are
retained once in Core with a content-first receipt. Exact canonical matches are identified.
Divergent/file-only variants have **unknown visibility and delivery**: a file may be an older
cache or a leftover after clear/delete. They cannot overwrite canonical output, recreate input,
acknowledge mail or start execution. Invalid JSON is retained with its parse error.

GET /v1/sessions/{sid}/legacy-transcript exposes preserved evidence through the existing
authenticated session API. Normal transcript reads do not use it. The completed import receipt
prevents stale files from being reimported after subsequent clears. Migration never submits work.
Legacy file-only visibility needs explicit review; this packet does not invent visibility proof.

## Assurance and qualification

Fresh cases cover read-only cold reload, lost final-envelope reply, cache failure, clear versus
volatile recording, duplicate/ambiguous legacy custody, migration twice and boot ordering.
Accepted-input cases assert that optional cache failure does not invalidate confirmed Core input.
Tests provide regression assurance. R44/R45 model evidence remains tied to its recorded tuple.

Shared native task semantics are one execution-path qualification, supplemented by workload
evidence: Shell process/output cleanup, Download bytes/hashes and Indexing manifest publication.
Subagent/Session and worker-free Question lifecycles retain distinct acceptance obligations.

Current targets are core develop 9965667afd6981194705b160ab22a3e0b09a5158 and GACT main
6ea4e15e4ac3b0160237810b2f11ed3d2311c6a0. Integration precedes candidate freeze,
independent whole-implementation review and fresh integrated acceptance. Required CI,
regression migration and remaining Q/R rows are not claimed complete.

Installed state, authentication, defaults, released branches/pins and protected human documents
are preserved. Generated checking state stays inside the D qualification repository. All exact
rejected-removal/manual-only boundaries remain; no blocked cleanup is retried or delegated.
