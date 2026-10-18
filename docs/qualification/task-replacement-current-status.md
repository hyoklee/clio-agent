# Tasks replacement status — October 18 UTC

## Current state — October 18, 21:08 UTC

Initial implementation and initial test construction are complete. The remaining
work is regression/live bug repair, final integrated qualification and independent
review. Publication and daily Desktop installation remain separate.

| Milestone | Evidence |
| --- | --- |
| Initial implementation | Complete; subsequent defects remain repairs, not missing initial implementation. |
| Initial regression construction | Complete; new defect-specific regressions precede their execution. |
| Completed agent CI | `fcd8737cbfb43bdc2183e57bc355036b6fddd072`: 24 successful jobs, all twelve Python reports collected, zero failures/errors. Each interpreter has 12,992 passes and fifty exclusions. Exclusions are not passes. |
| Current repair | This commit excludes reserved task-body/output scopes from semantic-event replay and records GACT `c813c1b7d3064c5b6125dc21c9aec70117c78ca4`. Fresh combined-head CI/review and UI build remain required. |
| Live qualification | Scoped R210 actual-model/external recovery and desktop/phone interactions passed. The full Q1–Q9 matrix, migration/recovery obligations and all thirty final-candidate races remain unaccepted. |
| Release readiness | No-go until those required gates and independent reviews pass. |

[Completed agent CI](https://github.com/iowarp/clio-agent/actions/runs/39163180395)
retained all existing assertions and limits. The 1,005-message retention case
passed on Python 3.12/3.13/3.14 in 111.705/81.823/50.541 seconds under the unchanged
180-second guard. The A2UI load case also passed on all three interpreters.
The twelve-report inventory is D `.pytest-runtime/static/ci-fcd8737c-complete.json`.
Its fifty exclusions include live-provider prerequisites and Windows-only cases;
they are not presented as executed or as full platform/provider qualification.

## Current fixes and evidence

R205/R206 measured actual Core writes while preserving all 1,005 messages and
replay assertions. Reserved task-body storage reduced working-context index writes
from 105,815,856 to 44,701 bytes. No backend, execution owner or production chunk
default was replaced. R207's 32-event chunk setting remains an operator experiment.

Claude's source review then identified that cold semantic replay still fetched
reserved task bodies and Shell output before discarding them. R212 reproduced
that defect. The correction uses ARC's existing canonical chunk grammar when
selecting semantic-event scopes; broad metadata exclusions remain unchanged.
R213 passed the real-Core cold replay case with 48 linked Shell outputs, twenty
pending messages, identical semantic events and explicit content reads:
one executed pass, zero skips. Scoped Ruff/format, Mypy and the removal guard pass.

R210's actual UI review found an unconfirmed visibility error repeated as progress
and again as a red failure. GACT 8eaea05f keeps useful numeric progress, shows
“Needs inspection,” and discloses the raw issue once in existing technical details.
R214 executed three new behavior cases successfully; other filtered test names
were not executed. Scoped lint/format and all six frontend guards passed.
The correct workspace TypeScript 6.0.3 check passed after correcting a new fixture's
non-nullable progress unit. An earlier root TypeScript 5.6 invocation was invalid
for this workspace; no production schema or compiler setting was weakened.

## Actual-model evidence — R210

Frozen source was agent fcd8737c / GACT 07cf095f, Python 3.14.6, DSPy 3.4.0,
FastMCP/fastmcp-tasks 4.1.0, MCP 2.0.0, pydocket 0.26.2 and iowarp-core 2.3.2.
Codex/Luna used the real direct SSE inference bridge. The external workload was
synthetic owned work on production FastMCP/SDK/CLIO implementations.

Session `sess_a01bbcc45575`, assignment
`task_3f7f22197bbb4918912d6229e275a9cb`, and external task
`task_369161b034094783aee65ae093c5ec3b` retained their original identities.
The model received a running handle, performed an independent filesystem read,
and yielded. Observation loss produced one attention episode and an idle wake.
Repeated failed observations caused no duplicate wake. Reconnection used the
original backend identity without resubmission. The original result then woke
the same assignment once and the model reported the verified 77-byte payload,
nonce, request tag and SHA256
`b21cfce748f6fc023ce9afd9632f80bc4224073d970c6fbade5a22ca0e781abe`.
There was one backend execution and one long-job submission.

Real desktop/390px-phone Work/disclosure, Runs and final-result interactions
passed with no connected-UI errors or viewport overflow. All six selected images
were visually inspected; the corrected GACT UI still needs real-service review. These technical qualification images do not complete the website media.
This family does not prove approved-provider jobs, partial input answers, every
task kind, the full UI matrix or the final race repetitions.

R210's owned API, external worker, proxy and browser exited normally; physical
external cleanup was confirmed. Original authentication and product source stayed
unchanged. Its isolated supported Core configuration used 32 MiB metadata,
measured at 33,554,432 bytes. Product defaults and execution limits were unchanged.
Bounded receipts, controllers and selected real images are in D
`.pytest-runtime/static/r210-*`. Actual SSE inference passed; no measured maximum
raw SSE-line size is claimed. The native-parser over-64-KiB contract also passed.

## Review, source and remaining work

Astra returned source GO for fcd8737c. Actual Claude Code/Fable returned source GO
for 99e7c13e and identified the cold-read cost addressed here. Source review missed
99e's invalid SDK import, subsequently repaired at fcd. Neither review qualifies
the current combined delta or substitutes for tests/live acceptance.

Astra returned source NO-GO for e0e011b4 / 8eaea05f: Runs compared raw progress
with a shortened diagnostic and failed to disclose complete structured/long text.
R218 reproduced the structured case, then passed both structured and long cases
individually/sequentially after preserving the original diagnostic separately
from its concise summary. Scoped lint/format, all six guards and workspace types
pass. New independent review is required. The first R217 Fable preflight exited
before launching its CLI because the copied access token was too near expiry;
a subsequent read-only check found refreshed original credentials. No model
review or authentication write is claimed for that failed preflight.
Local SSE receipts preceded final formatting; exact fcd CI and R210 provide the
later evidence. Request bounded independent review of this combined delta.

Remote develop `35fdd5fe0d85328093ac615909ae6edc2e3a9231` and GACT main
`f2b96308458d039d72391a88adb97166e72ef7ad` were freshly checked and are included.
The isolated runtime uses iowarp-core 2.3.2 through ARC's existing Core adapter.
The dependency lock hash remains
`04d97494089a6fdbdb28a105b7119bedaf4957f0984e3a17c3d3a88892b81508`.
Primary source/human work, released pins and installed Desktop remain preserved.

Next: rebuild the matching GACT UI; obtain fresh combined CI/Astra/Fable review;
execute the remaining Q1–Q9 campaigns and all thirty final races; update website
walkthroughs with reviewed replacement-service images. Freeze source/runtime/UI
within every family. See the acceptance ledger and live execution sheet for the
unchanged required behaviors and diagnostic limits.

## Owned data and cleanup

No product/model family is active. The October 18 no-follow inventory lists 171
known disposable paths / 28.91 GiB logical data, with zero read errors/overlaps.
Logical size is not a reclaimed-space promise. Seventy-six listed paths now
intersect prior automatic-review rejections and remain manual-only.

R195's two roots, R208's exact native metadata file and the R215 cleanup attempt
are recorded separately. R215's three exact targets were rejected before execution:
`.pytest-runtime/live/r208-external-recovery`,
`.pytest-runtime/live/r210-external-recovery`, and `.r210-live-tmp`.
No retry, bypass, delegation or parent removal. Earlier boundaries remain intact.
The latest audit found no process matching campaign paths and no campaign-port
listener; remaining disposable files are still present.

Current inventory/custody files are
`D:/Libraries/Documents/projects/clio-agent-task-qualification/TASKS-CLEANUP-LIST-2026-10-18.{md,csv,json}`
and `TASKS-CLEANUP-CUSTODY-2026-10-18.json`. R215's rejection receipt is
`.pytest-runtime/static/r215-disposal-rejection.json`. No archive was created.
Earlier owner cleanup recovered 4.72 GiB on C and 5.35 GiB on D, plus pnpm pruning;
those removed items are excluded from the remaining inventory.

Keep the protected human design documents, active source/runtime, canonical
product history, authentication/defaults/released pins and unrelated work.
Retain every prior rejected/manual-only boundary; no manual cleanup script or
retired service is executed. Historical dated status is available in Git;
required source/test lessons and acceptance rows remain in the ledger.
