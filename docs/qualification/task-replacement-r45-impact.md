# R45: corrections from live execution and independent review

Initial implementation is present. Tests provide regression assurance; actual
models using production implementations provide qualification. Neither a source
review nor a passing test is recorded as live acceptance.

R44 ran on Windows with private Core, FastMCP roots and writable state inside the
D qualification repository. Codex/Luna actually received running Shell, Subagent,
Indexing and Download handles and performed other work. Questions woke idle and
explicitly stopped sessions without another human chat message. An actual
Download kept transferring after Stop; explicit human cancellation then settled
cleanup and reached the parent through its normal mailbox. A deliberately new,
narrower Download verified the published payload's bytes and SHA256. The bounded
receipt is `task-replacement-r44-live.json`.

These are partial live demonstrations, not final Q1–Q9/R1–R6 acceptance. Initial
model refusals and the earlier activation/IPC failures remain failures. External
task-capable MCP/input/reconnect, Claude differences, workflows, all five-repeat
races, migration and integrated UI still require fresh evidence. Core semantic
search indexing is unrelated to connected-folder manifest enumeration.

R44's graceful shutdown failed: acknowledged plain Questions repeatedly deferred
healthy display projections; recovery readiness restored them and created a
cycle. No task remained active. Read-only inspection identified the two exact
pending updates. The already-closing disposable service's readiness callback was
detached for cleanup; its pending updates then drained and the service exited.
No records were dropped, no process force-closed, and this intervention does not
pass the original shutdown gate. `task-replacement-r44-shutdown.json` records it.

R45 corrects three paths in existing owners:

- Confirm Core mail before transcript projection. Missing selected accepted input
  is projected through the existing transcript writer before execution and on
  idempotent REST replay. Replays preserve the original receipt and assignment;
  they never silently target a successor.
- Signal the same TurnRunner after confirmed subtree cancellation settlement,
  including deferred/repeated settlement, so previously vetoed arrivals recheck.
- Apply healthy display projections directly from the input writer; defer only
  failed projections. Closing admission detaches readiness while owner recovery
  drains. No second coordinator, receipt spin or drain cutoff is introduced.

Astra's promotion fault and Fable's cancellation-arrival defect are accepted.
Fable's suggested blueprint busy race was rejected after Astra checked the
single-loop reservation boundary: no await separates its precheck and reserve.
No speculative synchronization is added for it.

Fresh public/Core regression cases are constructed for these failure boundaries.
They remain unexecuted until separately recorded. R45 still needs scoped checks,
independent source review and affected actual-model requalification, especially
Question idle/Stop delivery followed by unassisted service shutdown.

Cleanup of the exact R44 disposable family and short IPC directory was rejected
by automatic approval review as "blocked by policy". The command did not run;
both exact directories are human-manual-only. Their removal will never be
retried or bypassed. Process/private-listener absence was proved before the
attempt. No free-space recovery or root-absence claim is made.
