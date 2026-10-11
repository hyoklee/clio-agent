# Agent-facing Tasks: use cases and acceptance

This is the consolidated review of the async Tasks implementation and its
Subagent lifecycle extension. Implementation, focused checks, source CI and
actual-model acceptance are separate columns of evidence. An older successful
run does not become a live pass for a later commit.

## Behavior under review

| Use case | Implemented behavior | Acceptance evidence and limits |
| --- | --- | --- |
| Start long work and continue | MCP, Subagent, Download, Indexing and explicitly backgrounded Shell calls return durable handles. Submission failure returns an error. | Actual-model overlap was recorded for all five kinds on earlier integrated commits. Final-state route qualification remains incomplete. |
| Find work again | `query_tasks` exposes descriptions, kinds, status, supported actions and handles; filters and pagination operate after owner authorization. | Focused identity/collision/scope/cursor cases; actual-model query in the retained mixed and lifecycle runs. A child cannot enumerate siblings or ancestors. |
| Peek without collecting | `observe_tasks` reads incremental output/progress; an optional pattern waits for output or settlement. | Actual-model mixed observation and live Shell progress; observation does not consume completion. |
| Wait for mixed work | `wait_tasks` accepts one or several handles and any/all; no timeout means an explicit unbounded wait. Expiry or Stop ends only the waiter. | Retained mixed-task model cycles and focused partial-failure/timeout cases. Invalid members do not cancel other work. |
| Receive results while busy | Durable completion is injected at the next safe model iteration, after tool execution, rather than after the entire user exchange. | Retained busy-delivery model cycles, committed-context and delivery-race cases. Background observation creates no extra model tool calls. |
| Receive results while idle or stopped | Completion schedules a system-event turn. Stop ends the current model/waiter, while accepted tasks continue and can wake it later. | Retained idle-wake and Stop model cycles. This supersedes the original plan's idle-only queue behavior. A deliberately paused Subagent remains held. |
| Avoid duplicate completion | Explicit collection and automatic delivery share the same delivery guard. Queries and observation never consume it. Later explicit result reads remain available. | Focused collection/notification/veto/overflow races and retained model duplicate checks. Only an owner consumes its completion mailbox. |
| Cancel any task | `cancel_tasks` routes to the actual owner. Cancellation-request state stays distinct from terminal state. | Retained physical Shell/subtree and storage cleanup receipts. A transport refusal is an error, not successful cancellation. |
| Pause a Subagent | Persist an execution hold, stop its model, retain context and handle. Accepted background work continues and results/mail accumulate. | Actual-model lifecycle runs plus actual-service UI event-stream checks. Relay pause is explicitly unsupported. |
| Resume a Subagent | Release the hold and resume the same handle/context; deliver retained mail and results. | Actual-model same-handle lifecycle cycles and held-mail assertions. |
| Restart a Subagent | Settle an active run and its descendant owners, then create one linked successor. Retained context preserves provenance; fresh context omits copied history. Accepted operations are never replayed. | Retained full lifecycle runs and physical owner receipts. Latest Claude runs exposed a fresh-result-read omission after copied first-person history; those failures remain failures. |
| Message a busy/idle agent | Persist attributed mail, inject at the next iteration if busy, or wake if idle. A hold retains mail. | Actual-model busy/idle peer cases and focused durable mailbox/commit cases. Sender messages are not human authority. |
| Address a finished agent | Address its exact session/handle; use its valid successor chain or create a linked successor, preserving the original parent. | Retained model completed addressing and cancelled/failed addressing through existing successor chains. The latter does not establish first-message continuation from every terminal state. |
| Discover another session | Memory search/summary/context reads return permitted context and an exact message target. Read permission does not grant lifecycle control. Peer messages require scoped intent. | Actual-model scoped peer discovery/messaging and focused denial/identity checks. Relay peer addressing is explicitly unsupported. |
| Recover after disconnect | HTTP MCP reconnects by its complete persisted identity; local Shell and interrupted storage work are not replayed. | Retained HTTP recovery and lifecycle service-interruption receipts. Wider transport and platform recovery remains incomplete. |
| Control tasks from the UI | Shared task surfaces display description/status/progress and supported actions. Cancellation/restart require a task-specific confirmation; dismissal is distinct. | Actual-service desktop and phone browser gates on retained runs, including five pause/resume event-stream cycles. Fixture screenshots alone are insufficient. |

### Retained five-kind model receipts

These original verdicts were reread and SHA256-matched during this review. Their
passes retain their original commits and do not qualify the current runtime.
Paths are relative to the release-recovery `mcp-agent-tasks` evidence directory.

| Kind / route | Original core | Receipt |
| --- | --- | --- |
| Shell / SSE | `4dc4b1c1` | `integrated-4dc4-shell-lifecycle-1/verdict.json` |
| Subagent / SSE | `4dc4b1c1` | `integrated-4dc4-subagent-mixed-1/verdict.json` |
| Indexing | `4dc4b1c1` | `integrated-4dc4-indexing-refresh-1/verdict.json` |
| Download | `959e2238` | `integrated-959e-download-root-1/verdict.json` |
| MCP / HTTP | `2cdd6b3d` | `integrated-2cdd-http-overlap-2/verdict.json` |

Copy/hash review: `historical-five-kind-overlap-custody.json`. Custody validation
is not a fresh model execution or a replacement for final-state repetition.

## Ownership and execution review

The session task projection adapts existing Subagent records, MCP task records
and storage operations. The application supervisor owns drivers and transports
independently of turn executors; it is not a second execution registry. Public
handles and full owner identity are persisted before acceptance. MCP keys retain
server, session and backend-task identity, while legacy IDs resolve only when
unambiguous.

Shell supervision waits for its owned process tree and output readers before
publishing settlement. Explicit execution limits remain; an inherited whole-call
wait does not limit accepted background work. Shutdown interrupts and settles
owned local commands rather than reattaching by PID or replaying commands.

Downloads retain the approved transfer path, selected paths, source/revision
identity and byte/hash accounting. Staging cleanup precedes terminal publication.
Indexing enumerates off-loop with cooperative cancellation; the complete
manifest, source pointer and successful operation are committed together. Failed,
cancelled or interrupted indexing preserves the previous published manifest.

Subagent cancellation closes descendant admission before requesting owner
cancellation and waits for pending submissions and descendant settlement. Pause
does not use that cascade. Retained restart does not copy holds, cancellation,
admission closure or mailbox ownership into the new run. Historical result access
requires a valid same-recipient lineage and does not consume predecessor mail.

## Concrete long-running workflows

- **Local conversion or analysis:** explicitly background Shell, retain the
  returned handle, inspect incremental output while doing other work, and collect
  or receive its result. The recorded workload is a real Python process, not GPU
  image conversion; a GPU workflow needs its own device/output acceptance.
- **Independent consultations:** spawn several Subagent tasks, observe their
  progress, use an any-wait to begin processing available results, then an all-wait
  for the remaining evidence. Pause preserves a consultation and its accepted
  work; cancel settles its descendant owners; restart creates a new run identity.
- **Download then analyse:** a Download handle tracks approved transfer custody,
  real bytes/hashes and cleanup. Analysis must depend on the stored successful
  outcome, rather than assuming acceptance means files are ready.
- **Connect then browse:** an Indexing handle tracks manifest construction. The
  previous manifest remains authoritative until atomic publication succeeds.
- **Five cluster jobs then iterate:** this is a useful goal-driven workflow, but
  a background `sbatch` command's completion is only submission completion.
  Generic Shell supervision does not thereby own or cancel the remote Slurm job.
  Scheduler job IDs, status, output custody and cancellation require a real
  scheduler owner or an MCP server that exposes those jobs as tasks. No dedicated
  Slurm task adapter or five-job scientific iteration is claimed here. Existing
  cluster-operator/Jarvis guidance distinguishes relay dispatch handles from
  `pipeline_id`/`execution_id` workload status and artifact retrieval. A terminal
  dispatch must not be reported as a terminal scientific execution.

Busy delivery means the next eligible model iteration after the current tool
execution returns. It does not promise interruption of a tool in progress. An
explicit unbounded wait is a commitment to its selected tasks until settlement
or Stop; incoming mail remains durable for the next eligible iteration.

## Prompt and bridge review

`clio.runtime.tasks` is canonical shared runtime guidance for capable root and
child agents. It explains immediate handles, iteration delivery, idle wakes,
Stop, mixed controls and the distinct Subagent lifecycle. Background Shell,
Connect and Download tool descriptions state their acceptance behavior. MCP
task-capable tool descriptions are derived from declared task support across
the generic builder and blueprint reload/catalog routes; ordinary MCP tools are
not relabelled as task tools.

The marketplace feature snapshot `3d11b27` corrects two stale Factorio references
that confused human-input waiting with explicit pause/resume. It explains shared
controls, generic cancellation, descendant settlement and linked restart. Shared
runtime guidance remains canonical rather than duplicated into every specialist.
Model-pin, skill-literal and Factorio blueprint checks passed. This source review
does not establish live acceptance for every marketplace agent or provider bridge.

## Claude formatting recovery: what was demonstrated

The retained failing response followed a wait that returned in approximately
0.255 seconds. The model then emitted 7,106 HTML line-break tags without another
tool invocation. The wait observation had reached the SDK; the cause of the
subsequent generation remains unestablished. No prompt/bridge/model ablation has
established a root cause.

The current tool-capable Claude guard detects 256 leading `<br>` tags, allowing
whitespace, case differences and stream chunk boundaries. Other text disables
this detector for that reply. It is neither an elapsed-time threshold nor a
general repetition metric; it does not limit legitimate slow local inference.
It can reject a legitimate reply deliberately containing that many raw tags,
and it does not detect a loop that begins after ordinary text. The current
stream is closed and the existing malformed-call path supplies corrective
feedback at the next iteration. Accepted tasks continue. This detector does not
itself impose a total retry bound across model iterations.

The five retained recovery exercises deliberately requested 300 tags and
explicitly instructed the model how to continue after protocol feedback. They
demonstrate cooperative recovery plumbing, not spontaneous recovery from the
original failure, general provider acceptance or a root-cause diagnosis.

## Current completion gate

Runtime checkpoint: core `2960d197`, GACT `63149f88`, Python 3.14.6/Core 2.3.1.
Five focused successor-context cases passed individually with zero skips;
Ruff/format/Pyright and five unchanged guards passed. The preceding exact commit
`ccc105eb` passed CI's 19 jobs, with 12,477 passed and 66 excluded Python 3.14
tests. Exact-runtime CI `38111929557` on `2960d197` passed all 19 jobs.

Two newly retained failures prevent promoting older model passes: Codex on
`ccc105eb` omitted a new terminal-address message despite committed context
inclusion; Claude on `2960d197` failed a later spawn request during its first
cycle after successfully exercising a fresh successor result read. That partial
Claude cycle is not counted complete. Codex on `2960d197` passed five lifecycle
cycles and busy/idle peer messaging, then failed recovery setup: its parent model
chose an unbounded wait on the accepted child instead of ending after spawning.
The unchanged 150-second operator gate expired before service interruption.
Recovery/UI/terminal/extra checks on this runtime were therefore not executed.
The wait itself is not demonstrated broken. All 12 Shell owners and the private
Core owner are absent. The briefing clarification is not a proven complete cause
or fix for the separate earlier failures.

Full qualification is **incomplete**. The current exact source/runtime/UI and
per-provider verdicts are recorded in
`mcp-agent-tasks/lifecycle-qualification-current.json` in the release-recovery
evidence directory. The detailed ledger retains original failed attempts and
source identities. Final-source checks must be updated after relevant changes.

Protected Windows native/Core crashes, confinement rejections and the oversized
SSE route remain unverified; none is bypassed for qualification. Relay pause,
retained restart and peer addressing are explicitly unsupported. Wider provider,
platform, MCP input/reconnect and workload recovery repetition gates require
their own receipts. Executed test skips are exclusions, never acceptance passes.

The isolated Python 3.14/Core 2.3.1 candidate is separate from the installed
Desktop runtime. Merge, release, installation, host authentication, defaults and
released pins remain separate actions.
