# Agent-facing Tasks: use cases and acceptance

This is the consolidated review of the async Tasks implementation and its
Subagent lifecycle extension. Implementation, focused checks, source CI and
actual-model acceptance are separate columns of evidence. An older successful
run does not become a live pass for a later commit.

## Current readiness, October 12

Fresh cross-workflow execution is recorded in
[`session-workflow-tasks-2026-10-12.md`](session-workflow-tasks-2026-10-12.md).
Five actual Codex/Luna cycles passed on `26749f2d` using distinct blueprints and
root sessions, including independent subscriptions, busy/idle messaging, mixed
waits, failure wakes, Stop independence and denied peer cancellation. Their
disposable services, native Core allocations, processes and session records were
removed after verification. The production UI also passed one fresh actual-model
desktop/phone cycle on `0c5bf0db`, including pause, resume, confirmation dismissal,
subtree cancellation and physical settlement. Runtime CI passed all 19 jobs on
`c369ec9f`; later commits through `ce65f72c` do not change `src/` or `sdk/`.
Five fresh sequential Codex/Luna Subagent lifecycle cycles also passed on
`dce7c508`: held execution with background work continuing, queued mail, resume,
linked retained/fresh restart with explicit result reads, no operation replay,
and cancellation with physical descendant settlement. Their complete disposable
run state and process owners were removed. Claude and the separate parent
human-intervention family remain under qualification.

The older external receipts and archives named below were deleted during the
human-requested disk cleanup. They describe historical results and are no longer
available as retained evidence. Current acceptance must use fresh executions.

## Historical qualification before disk cleanup

Before cleanup, runtime `fa294aff` had actual Codex/Luna acceptance for MCP,
Download and Indexing human-control notification. Actual Codex/Luna
parents received the human cancellation notice in five complete cycles for each
kind. MCP used the real FastMCP conformance backend through the production CLIO
bridge. Each backend received one cancellation and no answer. Download owners
settled their physical cleanup; Indexing retained the previous 96,194-entry
manifest. The parents received their intervention identities and terminal
outcomes automatically, and later turns received no duplicate.

The deleted historical receipts were `mcp-input-ten221.json`, `storage-coverage111.json` and
`indexing-retention-fifteen208.json` in the external qualification directory.
The historical read-only audit `status-audit246/relay-status-audit246.json`
reconciled seven native gate verdicts, custody and source-tree equivalence. That
deleted audit is not current retained proof or a new model execution.
Core production and live-controller trees at `8ac5cf9a` are identical to the
qualified runtime. The historical UI receipt is
`task-ui-progressive-disclosure-2026-10-12.md`.

Human-control relay means notifying a task's parent about a human action. It is
separate from running a subagent on a remote CLIO relay.

The historical Linux model matrix covered all five kinds, independent work after acceptance,
query/observe/mixed waits, queued successes and failures, automatic idle wakes,
Stop independence, human cancellation, subagent lifecycle and session messaging,
input/reconnect and isolated service recovery. Its 91 reported passed gates included
different numbers of repetitions. Fourteen original failed attempts and four
unexecuted attempts were recorded alongside successful follow-ups. These counts
are historical, not fresh qualification after the records were deleted.

## Current blockers

Full readiness is still incomplete:

- Protected Windows native/Core and confinement routes remain blocked and
  unverified under the existing rejected-launch boundaries. Earlier native runs
  exited with `0xC0000374` (heap corruption) and `0xC0000005` (access violation).
  Those observations do not establish disk pressure as their cause. The later
  automatic-review launch/confinement rejections prohibit retrying or bypassing
  those particular actions; no fresh Windows native launch is claimed here.
- Distinct local/remote inference routes lack fresh qualified provider evidence.
  Default localhost LM Studio/Ollama endpoints were not listening on Windows or
  homelab in the current probe; an alternative endpoint/profile is requested.
- Fresh Codex SSE runs reproduce rejection at the unchanged 65,536-byte line
  bound: 65,658 bytes on `df285214`, then 65,796 and 65,849 bytes on `aa8ec28e`.
  The second observer captured the exact rejected frames' hashes and shapes:
  valid JSON `response.completed` events containing tool schemas, instructions
  and usage metadata. The separate whole-event bound is 1 MiB. No parser budget
  was changed, frames discarded or operation resubmitted to make this pass.
  `session-workflows-sse-current.json` and `subagent-sse-current.json` on homelab
  retain bounded verdicts; both failed attempts cleaned up their complete run
  directories and process owners. Ordinary SSE passes do not close this failure.

Remote relay execution is outside the current qualification scope, as directed
by the human. Its future migration to ordinary MCP Tasks is separate work;
missing relay pause/restart/peer support is not a current completion blocker.

CI passed 19 jobs on `c369ec9f`. The 66
excluded Python cases per interpreter, one flake-check exclusion and native
permission-card exclusion remain unverified. Advanced-develop conflict
integration, merge, release and installation are separate unfinished actions.

## Continued qualification on October 11

### Fresh-context replay found by actual Codex execution

On frozen `abe59c8ea2c73861e7c7eb236591202aa29eee22`, five Codex human-control
cycles passed. Its next active/fresh gate passed the active restart, including
physical cancellation settlement and retained successor completion, then failed
the first fresh-context cycle. The fresh successor received the full predecessor
custody and cancelled Shell outcome but submitted the original command again and
waited on the new handle. The unchanged 150-second settlement check failed.
This failure is retained in `codex-fresh38-public-diagnosis.json` and the ended
public snapshot `remaining-continue22-24-final25-public.zip` (276 members, CRC and
all 275 exported-file hashes verified). Owners and Core/cache custody settled.

The candidate briefing now quotes/labels the original assignment as historical
and reiterates afterward that fresh resets copied transcript only. Newly
delivered messages remain separate. Custody, recipient permissions, immutable
outcomes and admission controls are unchanged. The trace establishes the replay,
not its internal cause; the original imperative assignment's framing was a
plausible ambiguity. No global command-deduplication or timeout heuristic was
added. Focused prompt/custody contracts support this change; actual-model replay,
lifecycle and peer-message gates must be repeated on the corrected source.
Earlier-source model passes and CI are not promoted to the correction.

### Restart custody and expiry publication correction

On `b5efc8b8`, Claude's active/fresh family passed two complete cycles, then the
third fresh successor replayed the original Shell operation. Its persisted
briefing contained no accepted-operation identities because only the immediate
predecessor's current task projection was read. The starts file records two
launches. The model and backend evidence establish a real custody failure; the
unchanged 150-second gate remains failed. Separately, all five complete lifecycle
cycles passed on that earlier source. Neither result replaces the other.

The correction validates and follows existing successor lineage, preserving
accepted public handles and bounded prior outcomes in the explicit briefing.
It preserves current task scopes and fresh/retained result-access boundaries.
Invalid or oversized custody rejects admission before a successor is launched.
No provider timeout, general repetition rule or command deduplication is added.

Exact-head CI `38165995538` also found an expiry ordering race: a question could
report `expired` before its root session left `waiting_user`. The existing
first-wins transition now persists the owner's release before publishing expiry.
A persistence gate reproduces the original race without changing its deadline
or weakening the assertion. Losing claims and owner-persistence errors keep the
original question intact.

Three initial regressions failed with actual assertions before correction. Six
additional cases reproduced an idempotency shortcut bypass for self/long cycles
and conflicting successor identities. Validation now precedes that shortcut,
while valid fresh/retained retries still reuse one accepted successor. All
43 selected cases then passed individually and sequentially with one worker
and zero skips. They cover custody chains, backend-session identity/handle
collisions, invalid/oversized lineage, private-output bounds, existing result
ACLs, first-wins question transitions and the original CI expiry case. Two
pre-existing nullable-loop diagnostics were also reproduced on the unchanged
previous source. A local-variable rename corrects them; concise attribution
documentation keeps the transition module within the unchanged 800-line guard.
Parsed execution is identical after those name/doc-only normalizations. Nine
affected expiry, answer-race and recovery cases pass on the final file hashes,
with zero skips. Original 43-case hashes remain retained separately. Scoped
Ruff/format/Pyright and eight unchanged repository guards pass. Both focused
owners and caches have completed recovery custody and retirement; the pytest
runtime root is absent before the next admission.

These are focused checks, not new live-model acceptance. The affected five-cycle
model families, pending workload/UI routes and exact new-source CI must pass
before qualification can advance. Protected native/transport/platform gates
remain unverified and full qualification remains incomplete.


### Qualification resource custody

Stopped qualification runtimes were allowed to accumulate. Owned cleanup retired
136 old Core allocation files, accounting for 55,984,308,224 allocated bytes by
file metadata, and 48 stopped sandbox caches containing 7,628,639,115 logical
bytes. Recovery archives were verified locally by CRC and every member's SHA256;
original PID/birth absence and source hashes were checked before retirement.
Transcripts, configuration, captures and failed verdicts remain retained. These
totals are not a measured change in volume free space.

Subsequent qualification admission requires the preceding gate's actual owner
settlement, Core recovery custody and cache recovery/retirement acknowledgement,
including after a failed gate. A live negative check refused premature admission
and created no new runtime. The first cache audit after the resumed browser check
also correctly refused while a proof-scoped process still existed. No next gate
was admitted; a later read-only audit found the process absent. Incomplete owner
records and earlier prohibited roots remain excluded rather than guessed at.
Receipts are retained under `mcp-agent-tasks/cleanup-completed21.json` and
`live-cache-custody21/` in the release-recovery directory.

### Current continuation: confined MCP transport directory

The `41ebfe5c` continuation passed five Codex human-control cycles, five
active/fresh restart cycles, five busy/idle peer-message cycles, five MCP HTTP
reconnect cycles, five human Indexing cancellations and five graceful Indexing
interruption/recovery cycles. The actual-service UI controls also passed. These
receipts remain tied to that source. Its stdio case failed before acceptance:
the real model reported that `web_fetch` was absent from its tool catalog.

Inspection found the active Codex fence selecting an absent first state grant
as `-C`, although the explicitly supplied workspace existed. The regression
reproduced that directory mismatch using the production transport and fence
composer. Commit `e4b14af5` passes the intended directory through both stdio
construction paths without adding or reordering permission grants. Three new
regressions and twelve existing transport contracts pass individually and
sequentially, with zero skips. An existing Windows simulation needed its actual
FastMCP import before changing `sys.platform`; its type assertion is stronger.
Scoped Ruff/format/Pyright and all eight unchanged repository guards pass.

All five actual Codex stdio interruption cycles passed on `e4b14af5` after the
fixture placed its state inside the existing workspace grant. Each requires
an immediate handle, independent model work, actual backend process settlement,
preserved task identity after service interruption, an honest interrupted result
and one automatic wake without resubmission. The original outside-workspace
fixture denial remains a setup failure; confinement grants were not broadened.

A further regression reproduced double resolution of a relative workspace:
the launcher changed directory, then its confinement command interpreted that
relative path again. Commit `27e82e3b` normalizes the declared directory before
validation, artifact-root construction and confinement. All four directory cases
pass individually/sequentially with zero exclusions; scoped Ruff/format/Pyright
and all eight unchanged guards pass. Continuation 17 passed five stdio
interruption cycles, five Claude busy/idle peer cycles and five Codex
terminal-recipient successor cycles on this commit. Claude lifecycle passed
three complete cycles, then failed cycle four: the exact restart instruction
reached the actual SDK request, but the model ended with 58 characters of
`reasoning_effort` markup and no restart invocation. The request did not contain
that tag. Its cause remains unestablished; cycle five was not executed.
The original failed cycle, public reply and private SDK record are retained.

Code inspection then found that normalizing `cwd=""` accidentally accepted a
previously invalid explicit directory. An actual assertion failure reproduced
the regression; `9f8ae56f` preserves empty-directory rejection while retaining
valid relative-directory normalization. Six focused cases pass individually and
sequentially with zero exclusions; scoped Ruff/format/Pyright and eight unchanged
guards pass. Continuation 18 freezes this commit and runs the remaining matrix,
continuing independent families after a failure. Earlier passes remain tied to
their original commits.

New isolated Core/test runtimes and generated source inputs use the existing
user-owned `/data` volume. The original 512 MiB runtime capacity, reserve guards,
workload counts, bytes, deadlines and behavioral assertions remain unchanged.
The first empty-directory attempt failed capacity admission and is not counted
as the regression reproduction; the second was admitted and failed its expected
exception assertion. All three stopped focused Core archives have local
CRC/member/hash verification.

On `9f8ae56f`, five complete Claude lifecycle cycles and five cycles each of
Claude/Codex human controls, active/fresh restart, Codex lifecycle and Codex
busy/idle peer messaging pass. Five stdio interruption cycles also pass. The
real-service desktop/phone UI gate passes five pause/resume cycles, cancellation
and restart confirmation/dismissal, descendant settlement, linked restart and
viewport checks. All seven captured UI views were visually inspected. A later
review found a real defect in the settled restart view: the task registry retains
the original assignment, but the transcript omits its task field and displays
returned text under Assignment. The original functional result and visual review
are preserved; assignment-display acceptance is failed. Public network fields
and the actual captured pixels are retained in
`remaining18-ui-assignment-defect.json`. A production projection correction and
affected live requalification remain required.

Five long Shell success, five long Shell failure and five long Subagent
completion cycles pass on `9f8ae56f`. Accepted work continues after the model
ends, the actual result automatically wakes it, and a later turn receives no
duplicate result. All five success/failure Shell replies report the stored exit
status (0/7 respectively) and the exact random output nonce. Public model text
and backend receipts are retained separately from private SDK context.

The current Codex mixed-task attempt failed before its waits: the child accepted
its first Shell operation, then ended saying it would continue in a subsequent
turn. It did not submit the second requested operation. Its recorded model
requests contain the shared finish-independent-actions guidance and task controls.
A mission clarification explicitly distinguishes same-turn model iterations from
subsequent conversation turns. It preserves all 58 assertions, workloads,
deadlines and repetitions, and is prepared but unexecuted. This failure is
retained; it does not demonstrate a lost accepted operation. Independent Shell,
Subagent gates continued on the frozen source. The following recovery setup
was interrupted by an actual host `ENOSPC` write failure before it could produce
an acceptance verdict. It is resource-interrupted and unverified, rather than a
demonstrated model wait or recovery failure. Its exact API/Core owners are settled.
Eight stopped, owned prior Core stores were archived with CRC/all-member SHA
proof before their exact allocations were retired. Logs/configurations and
incomplete zero-byte metadata remain preserved; the latter's allocation was not
retired without its original owner receipt. No volume free-byte claim is made.
Continuation 18 has 514 locally verified public ZIP members/513 exported files
and 13 locally verified stopped-Core recovery archives. Two zero-byte checkpoint
files remain privately retained and are explicitly listed as incomplete exports.

The assignment projection correction carries the registry's original assignment
through live task events, started/terminal handoffs and snapshot links. Workflow
and tool spawns share that projection; legacy missing descriptions are explicit.
It does not replay work or change execution ownership. Seven of eight original
regression checks failed against the old source; the legacy question case already
passed. After correction, nine new checks and five existing contracts pass
individually/sequentially through the real owned Core runtime, zero exclusions.
Scoped Ruff/format/Pyright and all eight unchanged repository guards pass.
Continuation 19 on `2932deb8` passed five complete Codex lifecycle cycles and
five Claude busy/idle peer-message cycles. Those actual-model results retain that
source identity. Its terminal-recipient harness rejected a new nested evidence
destination before any model scenario; the unchanged helper's permitted direct
root is prepared for the recheck. Five fresh actual-service UI Assignment/Result
checks and the remaining mixed/recovery/storage/input matrix are still required.

Claude's next lifecycle attempt completed pause/resume and retained restart, then
failed cancellation setup in its first cycle. The explicit new assignment reached
the model, which returned a 1,056-character bare JSON `spawn_agent_task` object
with finish reason `stop`. No spawn invocation was observed. The text-tool parser
treated this shape as a final answer. Why the model chose that format remains
unestablished; this is not evidence of a time or repetition limit or lost queue
delivery. Its exact public response and original failure are retained in
`claude-bare-call19-diagnosis.json`; zero complete cycles are accepted for that gate.

Three actual regression assertions reproduce the parser gap. The correction
recognizes only a whole exact call object for a currently declared tool, returns
the existing bounded protocol-error observation and asks the model to submit the
complete fenced JSON list. It never executes malformed JSON. Ordinary JSON,
unknown-tool data, examples, extra fields and malformed arguments remain answers.
All 15 affected checks pass individually/sequentially on owned Core/Python 3.14,
zero exclusions; this includes corrected-call execution exactly once and the
legacy v3 expectation that failed three interpreter CI shards. Scoped
Ruff/format/Pyright and all eight unchanged guards pass. No execution deadline,
retry bound, task cancellation, owner or confinement change was introduced.
Both providers' final-source lifecycle races, the real-service UI and the
remaining matrix will run on the next frozen commit. Native checks alone do not
establish that live acceptance.

Exact-source CI on `e4b14af5` and `27e82e3b` passed all 19 jobs. The latter reports
12,519 passed and 66 excluded tests per interpreter, plus 153 passed and one
excluded flake case. CI on `9f8ae56f` finished with 18 successful jobs and one
failed Python 3.14 shard (`38139241350`). Its expiry test looked up a real timer
after that timer could already remove its registry entry. A test-only correction
retains the actual timer at construction, preserves the one-second deadline and
every terminal assertion, and adds timer/registry settlement assertions. Scoped
checks pass. The unchanged real callback deterministically reproduces the
original `KeyError`; the corrected case passes with both forced late lookup and
normal expiry. The no-deadline and dismissed-pick contracts also pass, all four
individually/sequentially on real Core with zero exclusions. None of these test
results replaces the live matrix.

In the preceding continuation, the
Codex recovery setup failed because the parent waited before interruption, and
the idle Indexing setup failed because the model omitted its required independent
checklist action. Neither attempt demonstrates recovery or idle delivery.
The next setup explicitly separates the parent coordinator from the child's
assignment, and uses the existing second-message mode to request independent
work while the accepted storage task remains running. Original failures and
unchanged acceptance assertions are retained.

Public evidence for continuation 13 has 274 verified ZIP members and 273
manifest-matched exported files; its 19 stopped private Core allocations have
verified recovery archives. Private originals remain on the isolated host.
Continuation 16 has 32 locally verified ZIP members and one verified stopped
Core archive. Continuation 17 has 177 locally verified public ZIP members and
four verified stopped Core archives. Further results are recorded in
`mcp-agent-tasks/remaining-continue22-18` and `qualification-ledger-current.md`.
Full qualification remains incomplete.

### Earlier source and transfer qualification

The `4ade8463` runtime has five additional complete Codex lifecycle cycles,
busy/idle peer messaging, active/fresh restart checks and a separate real service
interruption/recovery pass. Actual-service desktop and phone UI checks passed,
including five pause/resume cycles, cancellation confirmation and dismissal.
All 14 recorded Shell owners and both private Core owners are absent. Public
custody archives and browser receipts are retained under
`remaining-codex-lifecycle-4ade-1` and `remaining-codex-recovery-4ade-1` in the
release-recovery evidence directory.

Five actual-model Indexing runs passed with exact 48,098-entry manifests. A
48,000-small-file Download stress run returned its handle, performed independent
model work and remained responsive, but did not settle within the unchanged
600-second qualification deadline. Its subsequent diagnostic exception does not
replace that failure. Shutdown recorded interruption only after cleanup; no
manifest or staging tree remained and its owned API/Core processes are absent.
The failed run is retained as `remaining-storage-4ade-series-1/download-1`.

Profiling a real 301-file transfer attributed 9.8 of 16.9 seconds to SQLite
commits and 3.5 seconds to file syncing. Progress persistence now publishes first
bytes immediately, then at the task observer's 0.2-second cadence, and flushes
exact bytes before cleanup. Cancellation still checks every chunk/file; hashes,
file syncing and cleanup-before-terminal publication are preserved. Four new
regressions cover success, cancellation, hash failure and an unavailable final
progress ledger. Existing API progress/cleanup, custody, conflict and selected
download checks also pass individually, without skipped cases. Scoped
Ruff/format/Pyright and the five existing guards pass.
The same 301 selected files and payload now finish in 7.4 seconds, with 0.97
seconds in SQLite commits and all 301 file-sync operations retained. This is
an owned production transfer profile, not an additional model acceptance pass.

Representative Download acceptance uses 6,000 selected small files plus a
64 MiB payload, checking every selected path and hash. The 48,000-file stress
failure remains separate and is not relabeled as a pass. Remaining model gates
continue on a newly frozen source; full qualification remains incomplete.

### Continued Claude protocol qualification

The next frozen `22d704e1` run passed four complete actual Claude mixed-task
cycles. Its fifth parent reply began `_tool_calls`, contained the requested
`spawn_agent_task` JSON and ended with a closing fence. The actual SDK record
confirms the malformed opener; the bridge treated it as a final answer, so no
child operation was accepted. The unchanged 180-second worker-start gate failed.
That attempt remains failed. A root cause for the model's spelling is not
established.

The text-tool parser now routes that exact whole-block shape through its existing
bounded protocol-error observation. It requires a call list for declared tools
and an unmatched closing fence. It executes no malformed call and introduces no
elapsed-time or general repetition rule. JSON data, unknown tool names, quoted
examples and blocks without the observed closing fence remain ordinary answers.
The reproduction failed before correction; eighteen focused cases then passed
individually and sequentially with zero skips. Scoped Ruff/format/Pyright and
eight existing guards passed. Formatting preserved the tested syntax trees.

Five Codex terminal-messaging cycles also passed on `22d704e1`, independently
creating successors for completed and cancelled recipients with immutable old
outcomes and no replay. Fresh Claude runs are being prepared on the parser
correction. The previous isolated credential snapshot fell below the unchanged
30-minute admission precondition; those later Claude cases executed no model
gate. A newer existing homelab credential has been copied into a new isolated,
refresh-disabled snapshot, with original host credential bytes unchanged.
Neither focused parser checks nor the earlier four cycles establish five-cycle
live recovery on the corrected source.

### Role boundaries and the next observed malformed reply

On `51202204`, actual Claude HTTP reconnect passed. One complete terminal-message
cycle and the completed-recipient portion of the second passed, but the second
parent then took its child's instruction to wait as its own instruction. Its
public response and actual unbounded `wait_tasks` invocation confirm that
behavior; the unchanged parent-settlement gate failed. Shared task guidance now
explicitly distinguishes the parent's instructions from the child's assignment.
The old compiled prompt failed the new regression. Ten actual request-building
contracts then passed individually, covering root/child providers, editable
overrides and every shipped ReAct agent pack.

Two complete mixed-task cycles passed on the same source. In the third, the
actual Haiku SDK response contained a promise to spawn between two `_tool_calls`
markers, with no executable call. No operation was accepted and the unchanged
worker-start gate failed. The model's reason for generating that text is unknown.
The parser correction treats only that entire unquoted broken wrapper as a
protocol error, using the existing bounded correction path. It neither invents
arguments nor executes prose. Quoted examples, partial markers and ordinary
answers remain answers. This is format validation, with no elapsed-time or
general repetition threshold. The precise reproduction failed on the old parser.
Twenty-five affected parser contracts then passed individually and sequentially,
with zero skips. Scoped Ruff/format/Pyright and all eight existing guards passed;
all tested source bytes match. A new frozen live matrix is being prepared. The
earlier failed model attempts remain failures.

The `51202204` CI run completed all 19 jobs successfully, with 12,507 passed and
66 excluded tests per interpreter. Its 153-pass/one-exclusion flake check is also
retained. Exclusions remain exclusions. Those results do not qualify the later
role-guidance and parser changes or replace the failed model gates.

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
| Restart a Subagent | Settle an active run and its descendant owners, then create one linked successor. Retained context preserves provenance; fresh context omits copied history. Accepted operations are never replayed. | Retained full lifecycle runs and physical owner receipts. Earlier Claude runs exposed a fresh-result-read omission after copied first-person history; those failures remain failures. |
| Message a busy/idle agent | Persist attributed mail, inject at the next iteration if busy, or wake if idle. A hold retains mail. | Actual-model busy/idle peer cases and focused durable mailbox/commit cases. Sender messages are not human authority. |
| Address a finished agent | Address its exact session/handle; use its valid successor chain or create a linked successor, preserving the original parent. | Retained model completed addressing and cancelled/failed addressing through existing successor chains. The latter does not establish first-message continuation from every terminal state. |
| Discover another session | Memory search/summary/context reads return permitted context and an exact message target. Read permission does not grant lifecycle control. Peer messages require scoped intent. | Actual-model scoped peer discovery/messaging and focused denial/identity checks. Relay peer addressing is explicitly unsupported. |
| Recover after disconnect | HTTP MCP reconnects by its complete persisted identity; local Shell and interrupted storage work are not replayed. | Retained HTTP recovery and lifecycle service-interruption receipts. Wider transport and platform recovery remains incomplete. |
| Control tasks from the UI | Shared task surfaces display description/status/progress and supported actions. Cancellation/restart require a task-specific confirmation; dismissal is distinct. | Actual-service desktop and phone browser gates on retained runs, including five pause/resume event-stream cycles. Fixture screenshots alone are insufficient. |
| Learn about human intervention | Human steering, Stop, pause/resume, cancellation and restart queue an attributed notice to the actual task owner. Busy owners receive it before their next model call; idle owners wake and held owners retain it. | The human-control relay checkpoint below separates focused contracts, model receipt, owner settlement and remaining route gaps. Agent-origin controls do not impersonate human actions. |

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

## Historical human-control relay checkpoint

Core `c4ee4299` adds notices through the existing durable mailbox. The live
controller in `1cc00989` checks intervention IDs supplied only to the parent model,
busy iteration delivery, idle wakes isolated from task completion, Stop/pause
independence, physical Shell and Subagent cancellation, linked restart without
replay, and a later turn
without duplicate collection. Core `4ade8463` changes only an existing watcher
test; production and live-controller trees are identical to `1cc00989`.

Eighteen new intervention cases, twelve affected existing cases and three
transcript golden cases pass individually/sequentially with zero skips. Scoped
Ruff/format/Pyright (zero errors/warnings) and five unchanged guards pass. The
watcher test previously assumed direct child discussion generated only one
model call. Its corrected contract requires the child discussion, the parent's
notice turn and one normal standing-watcher check, with exact session identities
and a delivered human notice. The original failure was reproduced and retained.

Five actual Codex/Luna cycles on `1cc00989` and five Claude/Haiku SDK cycles on
`4ade8463` pass on isolated Python 3.14.6/Core 2.3.1. Every cycle requires the
parent to report random intervention IDs supplied only through its mailbox,
while accepted work is still running. Physical worker identities and all twenty
durable Shell supervisors are absent after the runs, as are both private Core
owners. Source fingerprints remain unchanged throughout each run. The initial
`c4ee4299` attempt remains failed: its restart reply acknowledged the human
action and new handle but omitted the ID required by the receipt check. Only
qualification reporting instructions changed for the subsequent five-cycle run;
no assertion or runtime budget was relaxed.

Exact-source CI `38115363030` on `4ade8463` passes all 19 jobs. Python 3.14
reports 12,495 passed and 66 skipped; the skips remain exclusions. Later
documentation commits leave the production and live-controller trees unchanged.

At this earlier checkpoint, source, model receipts and CI were recorded in
`mcp-agent-tasks/human-intervention-status-current.json`. The live human-control
cycles exercise real Shell and Subagent owners; MCP, Download and Indexing
cancellation relay then had focused coverage only. The October 12 readiness
section above supersedes that three-route evidence gap with actual-model
receipts. This historical checkpoint does not qualify every workload, platform
or transport in the wider Tasks matrix.

## Earlier complete-lifecycle checkpoint

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
