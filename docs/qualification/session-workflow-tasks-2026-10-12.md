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

Fresh SSE diagnosis on `aa8ec28e` captured valid `response.completed` JSON lines
of 65,796 and 65,849 bytes rejected by the vendor parser's 65,536-byte line
limit. They include tool definitions, instructions and usage metadata. The
separate event ceiling is 1 MiB. Qualification instrumentation records only
sizes, hashes and field names, delegates to the unchanged parser and removes
its scratch file with the run. No size limit, timeout or assertion was relaxed.

The first fresh subagent lifecycle run on `aa8ec28e` passed three complete
cycles, then failed the fourth successor's required fresh result-read gate.
The first fresh Claude workflow run passed one cycle and failed the second
peer-cancellation invocation gate. Neither family is counted as a five-cycle
pass. All owners, scratch and private authentication copies settled and were
removed. The next controller records bounded failure context before deleting
transcripts, so a missing model action can be distinguished from a failed tool.

The nullable SDK acknowledgement correction passed its actual CLI session-reuse
regression and SDK live-SSE event-order test individually on `dce7c508`, one
worker, zero skips. These are client integration checks, not live model or
Windows native acceptance. Pytest removed its own disposable allocation tree;
subsequent ownership inspection confirmed it absent.

Runtime CI [38282435588](https://github.com/iowarp/clio-agent/actions/runs/38282435588)
completed all 19 jobs successfully on `c369ec9f`. Later harness/documentation
commits through `0c5bf0db` do not change `src/` or `sdk/`. The 66 excluded cases
per interpreter remain exclusions.

## Fresh production UI interaction

On `0c5bf0db`, actual Codex/Luna created parent `sess_ccc3936c438a`, Subagent
`task_267f1b7af446` and descendant Shell
`task_43d0b8272f90454eaf5455f7ff85f4f5`. GACT `96e592f9`'s production build was
copied with all 521 file hashes matching (manifest SHA-256
`890fdb9138ef258792f7f200605f4dc4f81114a8cabf15b13f3560eb394cdf28`).

Actual browser controls passed desktop 1280×900 and phone 390×844: assignment
disclosure and child navigation action, pause while Shell remained running,
phone resume, cancellation confirmation dismissal, and confirmed cancellation
of both Subagent and descendant Shell. No page errors or horizontal overflow
occurred. Images were visually inspected. The parent woke with attributed human
intervention feedback. This is one fresh UI cycle, not five repetitions.

The harness verified the physical worker (PID 3981951, birth 1791826694.77)
absent, exactly one launch and no successful completion marker. The service,
isolated Core allocation, complete session tree, temporary production bundle and
temporary detached source checkout are absent. The bounded verdict is
`task-ui-current.json` on homelab. Automatic approval review rejected the combined
local browser-folder removal/SSH-tunnel termination command as `blocked by policy`;
it did not run. Those two local residuals are recorded as manual-only in the
operational ledger and were not retried through another method.

The preceding overlapping batch is not a five-cycle pass: Claude workflows
completed two cycles before an initialization timeout; Codex lifecycle completed
four; human-control notification completed three. During that batch the eight-CPU
host reached load above 170 and became temporarily unreachable. One isolated Core
daemon also reported SIGSEGV (`-11`); its cause is not established. Every batch
owner and scratch root settled and was removed. Further families run sequentially.

## Fresh sequential Subagent lifecycle

All five complete Codex/Luna WebSocket lifecycle cycles passed on `dce7c508`.
The parent received the Subagent handle while its descendant Shell was running.
Pausing held model execution and incoming mail while the Shell continued;
observation and an immediate wait reported the held run honestly. Resume
delivered the retained assignment nonce and queued message once. Retained and
fresh successor runs used new linked handles, explicitly read the previous
result and did not replay the accepted Shell operation. Separate cancellation
settled the actual process subtree before reporting cancellation.

The bounded verdict is `subagent-codex-current.json` on homelab, including
invocation IDs, each run's handles and the cancelled worker PID/birth identity.
The fifth cycle used parent `sess_ce2502e3b96f`, child `sess_6d3f1124c377`,
original run `task_6d3f1124c377`, successor `task_0f309154d440` and Shell
`task_4b4b1f52a49b4310898de2e1fe3e2c9a`. Its cancelled worker PID 4034065,
birth 1791827894.43, was absent. All five physical starts files showed one
launch. The service exited zero; Core, captured descendants, listener and the
entire disposable run directory were absent. This fresh five-cycle pass
supersedes the partial Codex lifecycle attempts above without relabeling them.
