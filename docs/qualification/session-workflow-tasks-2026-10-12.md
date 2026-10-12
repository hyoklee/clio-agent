# Session Tasks across distinct workflows

Five real Codex/Luna cycles passed on core `26749f2d235217d79ed069fa70c3de3e2e44f742`.
The isolated Linux candidate used Python 3.14.6 and iowarp-core 2.3.1; this does
not change the installed product's runtime dependency. The provider was
`codex`, model `gpt-6-luna`, transport `websocket`.

The model-driven harness is `scripts/live_verification/session_workflow_tasks.py`.
Each cycle installs two distinct blueprints, `session-task-workflow-observer`
and `session-task-workflow-producer`, and creates separate root sessions. It
uses actual production tool dispatch, storage, process supervision and mailboxes.

| Gate | Observed result in every cycle |
| --- | --- |
| Acceptance | Producer receives a running Shell handle and waits; observer discovers the finite Session run and Shell through an authorized workspace query. |
| Parallel work | Observer reads a real sentinel file after observing the still-running mixed task set and an expired `any` wait. |
| Busy messaging | A message addressed by the Session run handle remains queued during the producer's waiter and reaches the next model iteration after release. |
| Independent delivery | Observer subscribes, ends its turn and automatically wakes for Session/Shell completion; the owner's notification remains independent. |
| Mixed results | Actual model performs `any` and `all` waits, collects stored outcomes and reports the invalid member without cancelling valid work. |
| Idle messaging | A completed run handle addresses the stable mailbox and wakes the recipient; the old finite run outcome remains unchanged. |
| Failure | A real process exits 7; the subscriber wakes and the actual model acknowledges the failed handle/status. |
| Stop | Human Stop interrupts the finite producer run while the accepted Shell remains running; later completion wakes both owner and observer. |
| Permission | Actual model attempts peer root cancellation and receives a denial; the peer's completed outcome remains intact. |
| Delivery/replay | Deterministic notice IDs are delivered once; subsequent reads do not duplicate them; physical starts files contain exactly one launch. |

The bounded current verdict is
`/home/jcernuda/.local/share/clio-qualification/agent-facing-async-tasks/session-workflows-current.json`
on homelab. It records source/runtime/model identities, handles, invocation IDs,
notice IDs and bounded actual assistant receipts. It is a verdict, not an archive
of session state. The first attempt failed because the harness expected HTTP 200
from Stop instead of its correct HTTP 204; that failure remains identified in the
verdict. The corrected five-cycle run passed.

Cleanup verified actual absence of the owned service, native Core, all captured
descendant processes, port 18862 and the entire run directory. No transcript,
Core allocation, credential copy or filesystem payload archive remains.

## Current limitations and continued checks

These passes qualify this concrete Codex WebSocket coordination route. They do
not qualify Claude, provider SSE, local/remote inference or Windows native Core.
Relay execution is explicitly outside this campaign's current scope.

CI on this source exposed handle-collision loss in task projection, outdated SDK
event ordering, uncategorized fresh Session identities in the equivalence harness
and a workflow progress test that included dispatch latency in its short window.
The collision reproduced before repair. Projection now deduplicates full backend
identity, allowing control and successor custody to reject ambiguous handles.
SDK acceptance verifies the durable handle before the running event. Equivalence
canonicalizes identities and semantic cursor boundaries with negative controls
for changed assignments, outcomes, aliases, references and cursor boundaries.
The progress test starts its unchanged two-second watch at actual child progress;
the real activity probe and the silent-child/sabotage checks remain in place.

Affected focused cases run individually/sequentially with one worker and zero
skips. Source CI and additional live routes must pass before full qualification
can be claimed. Original historical exclusions remain unverified.
