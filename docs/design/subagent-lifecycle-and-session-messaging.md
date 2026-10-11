# Subagent lifecycle and session messaging

Status: candidate implementation and qualification in progress, 2026-10-11.
The original source audit used core
`8feb486cb84a3c4587d9c424b69861e93925933b` on
`codex/agent-facing-async-tasks`. The branch now includes local lifecycle and
exact-session messaging controls. Live acceptance remains a separate gate.

## Candidate implementation

- `pause_agent(target)`, `resume_agent(target)` and `restart_agent(target, fresh=False)`
  use the existing Subagent registry and original placement owner. Pause persists
  an execution hold before stopping its model; resume keeps the handle. Running
  held runs reserve their admission slot; held queued runs cannot be admitted.
- `cancel_tasks` remains generic across all task kinds. A Subagent cancellation
  closes admission and settles its descendant owners before publishing completion.
- `message_agent(target=..., message=..., scope=..., user_intent=..., wake=False,
  reply_to=..., correlation_id=...)` accepts exact session IDs or task handles.
  The old `task_id` argument remains an alias. Sender-attributed mail is durable
  before acknowledgement and is collected at model iteration boundaries or an
  automatic idle wake. A hold prevents both paths from consuming pending results.
- A terminal recipient creates a linked successor without reparenting. Full
  retained messages have new IDs and references to their original message IDs;
  fresh mode omits history. Current parent restrictions compose with retained
  recipient policy. Restart retries against one old handle reuse its successor.
- A retained successor may read a known terminal task result from its own prior
  run lineage with `get_task_result`. Registry links, recipient identity and
  workspace must agree. This does not enumerate historical tasks, grant task
  control, expose live work or consume the predecessor's completion mailbox.
  Fresh-context runs, deleted sources and unrelated peer sessions retain their
  ordinary result scope.
- Memory search and summary results include exact message targets after read-scope
  checks. Peer messaging additionally requires scoped intent; discovery does not
  grant pause, resume, restart or cancellation authority.
- The HTTP doors are `POST /v1/sessions/{sid}/agent-controls/{target}/{action}`
  and `POST /v1/sessions/{sid}/agent-messages`. UI and native tools call the same
  lifecycle and messaging owners. Task surfaces expose pause requested, paused,
  resume and confirmed restart separately from cancellation.
- Local holds cannot pause a remote model. Relay pause/retained-context restart
  and peer relay addressing are explicitly refused until the remote protocol
  supports their contract; existing owner-to-relay messaging is retained. Those
  routes remain unimplemented and unqualified, not silently simulated locally.

## Restart custody across successor chains

Every linked restart carries a bounded, validated briefing of accepted operation
identities and prior-run outcomes from the existing registry/session lineage.
This applies to retained and fresh context modes. The original assignment,
operation handles, provider/backend-session identities and prior messages remain
unchanged. Private workflow state and unbounded result content are excluded.
Missing/cyclic/conflicting lineage, ambiguous handles or oversized custody reject
the new launch rather than silently dropping accepted work. Validation precedes
the idempotency shortcut; a returned successor must retain the same owner, agent,
workspace and placement. Valid retries reuse the already accepted successor.

An empty current-scope task query does not mean no earlier operation was accepted.
The successor uses its explicit historical briefing to avoid replay. That
briefing grants no historical query, control or live-result access; fresh-context
result restrictions and existing retained terminal-result authorization remain.

## Human intervention and ownership

Human control never silently changes an agent's owned work. Authorized human
steering, pause, resume, cancellation, restart and child-session Stop are relayed
to the **actual immediate owner**, independently of which ancestor's UI issued
the command. A nested Shell or Download notifies its owning child; controlling
that child notifies its parent. Subagent cancellation/restart notices explicitly
identify the descendant cascade. Dismissal remains a display operation.

Notices use the existing durable agent mailbox and its regular next-model-call
boundary, idle wake, hold, batching and commit-to-run rules. They carry human
attribution, action, original handle, kind, assignment, target session, status
before the action and recorded outcome. A restart outcome includes the new handle
and predecessor link. A human request is saved before control execution; an
uncollected request is updated with its acknowledgement/error. If the model has
already received a long-running request, its outcome is queued as a linked
follow-up. Requested cancellation is never presented as physical settlement.

Both current and compatibility HTTP controls are covered, along with accepted
user feedback sent directly to a child, queued-message promotion and human Stop
from HTTP/A2UI. Replayed accepted messages retain one notification identity.
Agent-initiated controls continue to return their ordinary tool observations;
they do not impersonate a human intervention. Target authorization remains ahead
of relay, and a notice neither transfers permissions nor instructs the parent
to automatically undo a human control or replay accepted work.

## Current checkpoint

The consolidated implementation and use-case review is
[Agent-facing Tasks: use cases and acceptance](../qualification/agent-facing-tasks-use-cases.md).
The human-control relay checkpoint in that review records the new owner notices,
focused cases and five actual Codex/Luna plus five Claude/Haiku cycles. Busy
iteration delivery, idle wakes, cancellation settlement and linked restart are
checked against real Shell/Subagent owners. Human intervention qualification is
tracked separately from the wider lifecycle/workload matrix and its remaining
platform/transport gates.

Full qualification remains incomplete. The earlier core `2960d197` clarifies successor
briefing: copied first-person history describes earlier runs, fresh checks must
be performed in the successor, and newly delivered mail must be processed within
the recipient's permissions. Five focused cases and scoped checks passed.

The prior `ccc105eb` Codex run passed five lifecycle cycles, peer/recovery/UI and
active/fresh restart, but failed new terminal-mail handling through a successor
chain. Its committed context included the mail; that proves staging, not a
successful model response. The Claude run on `2960d197` reached a fresh successor
result read, then failed a later spawn request during its first cycle. Zero
complete cycles are claimed for that attempt. Both failures remain recorded.
Codex on `2960d197` passed five complete lifecycle cycles and busy/idle peer
messaging. Recovery setup then failed: the parent model called an unbounded
`wait_tasks` on its accepted child instead of ending after spawning. The unchanged
150-second operator gate expired before service interruption, so current-runtime
recovery, UI and additional terminal/active/fresh gates were not executed. This
does not demonstrate a broken wait. All 12 recorded Shell owners and its private
Core owner are absent. Exact-runtime CI `38111929557` passed all 19 jobs.
CI `38110734518` on `ccc105eb` passed all 19 jobs; its executed
test skips remain exclusions. Current machine-readable status is retained in
`mcp-agent-tasks/lifecycle-qualification-current.json`.

## Retained verification history

The candidate has 55 focused lifecycle parameter cases, six existing messaging
compatibility cases and three unchanged transcript golden cases qualified
individually and sequentially with one worker. Nine catalog/route/commit
contracts and the metadata-race/hook-defer checks also pass. Claude protocol
checks add 16 JSON-envelope and 14 XML/legacy-format executions, including the
production provider bridge and agent loop. Focused cases have zero skips.
Scoped Ruff/format, changed-runtime Pyright (zero errors/warnings) and unchanged
guards pass. UI controls have three focused component and two transport cases,
scoped checks and both production builds. These checks do not replace models.

The complete actual Claude/Haiku run on core `e7e67bb4` and GACT `63149f88`
passed five lifecycle cycles: immediate handles and independent parent work,
accepted Shell completion while the child is held, retained mail, same-handle
resume, completed/cancelled retained-context restart without replay, and generic
subtree cancellation after physical process settlement. Peer discovery and
busy/idle messaging, service interruption/recovery, and real-service browser
controls at 1280px and 390px also passed. The UI ran five additional pause/resume
cycles on the actual event stream, with honest pause states, confirmation and
dismissal behavior, no page/HTTP errors and no viewport overflow. Additional
model checks passed terminal completed addressing, cancelled/failed addresses
through existing successor chains, active restart after physical subtree
settlement and fresh-context restart without replay. All 14 Shell owners and its
private Core owner are absent. This remains evidence for `e7e67bb4`, rather than
acceptance of later runtime changes. The earlier complete Codex `ca7506fa` run
also retains its original identity. The full Codex/Luna run at `a8a5c9fc`
subsequently passed the same five lifecycle cycles, peer messaging, recovery,
actual-service desktop/phone controls and additional terminal/active/fresh
checks. Its 14 Shell owners and private Core owner are absent. Recovery required
an explicit second message asking the child to wait on its already accepted
Shell handle; the operation was not replayed and no deadline changed. This is
recorded as a second wait mission, not first-assignment adherence.

Source CI on `a8a5c9fc` failed one Python 3.13 shard: Stop arriving during durable
MCP acceptance was retained, then ignored by the app-less transparent-wait path.
A gated regression reproduced that race. `ad51cd45` finishes accepted custody
and propagates Stop before starting another foreground wait. Four focused
regressions pass, including actual backend cancellation/reconnect and responsive
waits, without changing five-second bounds or cancelling backend work. Scoped
checks and five guards pass. The Claude `ad51cd45` attempt completed three full
cycles, then failed the fourth successor's required new `get_task_result` call:
the model reused its copied historical result and made no new tool call. No
authorization error or replay was observed. Its seven Shell owners and private
Core owner are absent, and the failed verdict is retained. `18fdc127` clarifies
the live mission's new-run result read and in-flight recovery wait. Its non-text
execution/oracle AST and production runtime tree are unchanged. The subsequent
Haiku attempt ended with formatting rather than the requested message call;
the Sonnet diagnostic returned unfenced JSON without submitting a tool call.
Both failed verdicts are retained. `ccc105eb` clarifies Claude's text-tool framing
only in the qualification agents; runtime and lifecycle oracles are unchanged.
Its Haiku attempt passed two full cycles, then failed the third successor's
required fresh result-read gate. Five Shell owners and its private Core are
absent. No final-head lifecycle pass is claimed. Runtime CI `38109538473` on
`ad51cd45` and `ccc105eb` passed all 19 jobs. These CI receipts do not establish
complete live qualification.

The runtime is an isolated Python 3.14.6/Core 2.3.1 candidate. This does not
qualify the installed runtime or the protected Windows native/confinement gates.
Final source CI is recorded independently; the existing 66 skipped tests per
interpreter remain exclusions, not acceptance passes. Relay pause, retained
restart and peer addressing remain explicitly unsupported; wider provider,
platform and earlier transport gates are not claimed complete.

Failed attempts retain their original outcomes. Codex `110d9425`, `e7e67bb4`,
`4017a0b7` and `b554879c` passed five controls and peer messaging but exceeded
the unchanged 30-second shutdown deadline; their UI gates were not executed.
Two real-socket regressions reproduced listener threads remaining blocked after
close. Five focused cases pass after shutdown-before-close, but the complete
`b554879c` workload still failed application shutdown, so that listener bug is
not claimed as the complete cause. A serving-lifespan diagnostic then captured
the shutdown owner waiting in sequential Codex conversation-socket closes.
Two deterministic owner-loop regressions reproduce this serialization and a
close failure skipping other owners. Both pass after concurrent close under
one existing five-second socket bound. Scoped checks and unchanged guards pass;
the complete `a8a5c9fc` run above includes actual-model service recovery on that fix.
The short `2d3ca338` diagnostic completed one cycle, then failed because the
successor reported retained data without the required `get_task_result` call.
The strict assertion remains unchanged. A zero-control-cycle `a54b0e63`
diagnostic passed peer messaging and isolated recovery; it is not a full matrix.

The first Claude run on `7ca356e3` exposed
retained-context reconstruction stranding a cancellation result after streamed
text. Four regressions reproduced before correction; six checks now pass,
including the exact failed transcript's original call/result identities and
strict rejection of missing results. Claude `65361111` passed three cycles
before bare JSON call metadata was misclassified as a final answer. Claude
`20830ab9` passed two before an XML call container caused the same silent ending.
Neither malformed response submitted an operation. Both formats now receive
bounded protocol-error feedback and require a subsequent correctly fenced model
call; JSON/XML examples and ordinary data are never executed. Each failure has
preserved transcripts, source identity and absent-owner evidence.

Other retained corrections include authorization of known historical results,
ambiguous lineage aliases, missing pause-state wire projections and concurrent
session-metadata serialization. The completion-notify regression checks durable
intent before releasing the real consumer, then actual collection and duplicate
suppression; no production delivery change was made for that test. The first
browser attempt's missing private executable PATH and earlier coordinator
delegation were qualification failures, not claimed acceptance. No timeout,
worker, assertion or guard budget was weakened. Detailed source identities,
verdicts, public custody hashes and failed attempts remain under the release
recovery `mcp-agent-tasks` evidence directory.

## Original audit before implementation

| Operation | Current implementation |
| --- | --- |
| Inspect, observe, wait, result | Shared task tools accept Subagent handles, with conversation/descendant scope. |
| Cancel | `cancel_tasks` closes subtree admission and requests cancellation of the child and descendant tasks. Terminal publication waits for owners and cleanup. |
| Message a running child | `message_agent(task_id, message)` chooses the retained local or relay placement. Local messages enter the next safe iteration boundary; relay messages use the retained task input channel. |
| Message a completed child | Creates a new child task/session with the original briefing, previous output and new message. The old task remains terminal and a successor relation is emitted. This is not resuming the entire old provider conversation. |
| Message a failed/cancelled child | Refused as `task_unwakeable`. |
| Pause/resume | No dedicated model-facing or task UI lifecycle control found. Waiting for human input and waiting for background work are existing states, not explicit operator pause. |
| Restart | No explicit model-facing restart operation found. Completed-child messaging implements one restricted successor path. |
| Cross-session messaging | The tool takes a task ID, not a session ID from memory search. The shared messaging helper looks up the application-wide task registry without the caller-session authorization used by shared task controls. This is not a complete discovery/addressing/authorization contract. |

Sources: `gact/agent_messaging.py`, `gact/agent_message_transport.py`,
`gact/live_handle.py`, `gact/agent_tasks.py`, `gact/task_subagent_owner.py`,
`gact/task_projection.py`, `gact/turn_spawn.py` and
`gact/agents/spawn_runtime_declarations.py` under `src/clio_agent/`.

## Pause, Stop, cancel and restart

These meanings are distinct. The agreed default for Pause is a durable hold
until explicit resume or an explicitly waking owner message.

| Action | Agent execution | Accepted descendant tasks | Identity and notifications |
| --- | --- | --- | --- |
| Conversation Stop | Stops the current model turn and its waiter. | Continue. | Existing task completion can automatically wake the agent. |
| Pause subagent | Stops model execution cooperatively and holds future automatic model starts. | Continue; progress and results remain durable. | Same Subagent handle/session; nonterminal `paused` effective status. No completion notification for merely pausing. |
| Resume subagent | Clears the hold and continues using retained context and pending messages/results. | Continue. | Same handle/session; resumes once at an eligible boundary. |
| Cancel subagent | Ends this run and closes its subtree admission. | Explicit cancellation cascades through descendants, with cleanup before settlement. | Original handle settles `cancelled`; does not become active again. |
| Restart subagent | Starts a new linked run after the prior run has settled. | Never automatically replays or duplicates accepted operations. | New handle; old result/history immutable. Default context continuation, with an explicitly requested fresh mode. |

Pause is neither OS process suspension nor a promise that an ordinary foreground
RPC stops immediately. It must report `pause_requested` until the provider/turn
owner has stopped reaching further model/tool boundaries. Execution safeguards
for in-flight foreground work remain intact. Accepted background tasks must not
inherit the pause signal as task cancellation.

A paused Subagent remains active for queries and mixed waits. An unbounded wait
can remain pending until resume or cancellation. Its displayed supported actions
include resume, message, observe and cancel; generic MCP/Download/Indexing/Shell
tasks do not acquire subagent pause or restart semantics.

Restart defaults to continuing the retained assignment/context, rather than
blindly running the initial assignment again. The new run must know which work
already completed, failed or remains accepted. A fresh restart is an explicit
mode that preserves old evidence and still does not replay accepted operations
implicitly. If restart is requested while running, first settle the old run;
never allow overlapping replacements or reopen a cancelled subtree in place.

## Proposed model-facing controls

Keep shared `query_tasks`, `observe_tasks`, `wait_tasks`, `cancel_tasks` and
`get_task_result`. Add subagent-specific `pause_agent`, `resume_agent` and
`restart_agent`. Extend the existing `message_agent` instead of creating a second
message transport.

Targets must be explicit and unambiguous: a task handle for one run, or a session
ID for one conversation. Preserve the old `task_id` argument as a compatibility
alias. A session target resolves its current eligible run, or explicitly creates
a linked continuation when the previous run is terminal. An expert ID such as
`ndp` alone is insufficient because several instances may exist.

`message_agent` returns a durable message acknowledgement immediately, including
message ID, source/target sessions, target run handle, disposition and any
successor relation. Busy recipients see it before their next model iteration;
idle recipients wake without another human message. Paused recipients can receive
and retain messages; a declared `wake` option decides whether the message resumes
them. Terminal recipients create a linked continuation, including after failure
or cancellation, rather than modifying the old terminal result.

Messages retain sender identity and provenance. Peer-agent messages are agent
content, not human instructions or parent-authoritative steer. Preserve the
recipient's agent definition, workspace, model policy and permissions. Delivery
must not transfer the sender's capabilities or silently reparent the recipient.
Replies need explicit reply/correlation IDs; do not create an unconditional
automatic reply loop. Task completion continues to belong to its original owner;
peer messaging does not consume another conversation's completion mailbox.

## Find a session, read context, then address it

The existing memory tools are a useful foundation, but their names hide limits:

| Tool | Actual source and behavior |
| --- | --- |
| `memory_search_sessions` | Lexical term matching over retained transcript `text`, `thinking` and `error` parts, ranked by matched-term fraction and recency. Hits carry session/message/part IDs and bounded excerpts. It is not a search over generated session summaries or a semantic ARC index. |
| `memory_read_session_summary` | Generated on demand from session metadata, message counts and up to the last five messages, each excerpt capped at 360 characters. It also returns message IDs and rollback metadata. No summarizer model creates this value; it is not a whole-session narrative. |
| `memory_read_context_frame` | Reads one retained context-assembly record: model/agent identity, referenced messages/files/injections, inclusion decisions and token estimates. It returns up to 50 items. It is not a general reader for the contents of those referenced messages/files. |

`_record_context_frame` creates frames during turn preparation. The audited path
stores them in a bounded `app.state.context_frames` ledger initialized empty at
application startup. No durable frame restore path was found in this audit;
therefore do not promise historical frame availability after restart. Message
and session persistence are separate from this frame ledger.

Sources: `gact/memory_tools.py`, `gact/routes/memory.py`,
`gact/runtime/memory_search.py`, `gact/enrichment.py`, `gact/turn_start_offloop.py`,
`gact/runtime/retention.py` and `gact/app.py` under `src/clio_agent/`.

The current memory policy allows same-session reads, same-workspace reads with
user intent, and separately scoped global-workspace reads. Arbitrary other
workspaces remain denied. Global workspace is not a wildcard over all projects.
Search filters for agent/kind/status/time and cursor pagination are desirable
extensions; the current native search exposes query/scope/limit/user_intent only.

Keep memory retrieval and execution controls distinct. Add live session/run
identity and addressable target information to discovery results after scope
checks. A discovered session does not automatically grant pause/cancel/restart
authority. Owner/descendant controls retain their existing authority; authorized
peer messaging is a separate capability. Cross-workspace messaging needs explicit
policy, rather than assuming that knowing an ID grants access.

For deeper reading, follow provenance to bounded message/context ranges with
cursors. A real authored session summary, if added later, must include covered
message range, source references, creation time and freshness. Never present the
current last-five-message projection as that feature. Frame persistence, frame
listing/discovery and bounded content reads also need explicit contracts.

## Implementation seams and verification

1. Persist pause intent in the existing session/task owners before acknowledging.
   Stop provider iteration/waiters without calling subtree cancellation. Guard
   task-result wakes, residual-message promotion, question resumes, scheduled/goal
   starts and queued subagent admission against the hold. Preserve all pending
   delivery intents. Restore the hold after service restart.
2. Keep paused child completion callbacks nonterminal and rebind them on resume.
   Update shared projection/actions, slot admission and parent mixed waits.
   Do not free a slot while an old worker still runs; define paused idle admission
   independently from live worker capacity.
3. Extend the existing successor path for explicit restart and terminal messaging.
   Preserve full retained-context provenance, immutable old results and original
   accepted task identities. Serialize competing restart/message/cancel actions.
4. Introduce a shared target resolver and messaging policy used by both HTTP and
   native tools. Connect scoped memory discovery to exact session/run targets.
   Preserve local/relay owner routing and sender provenance.
5. Add matching UI actions and shared model guidance; keep dismissal distinct.
   Expose pause requested, paused, cancellation requested and terminal states
   honestly. Cancellation confirmation continues to identify descendant work.

Focused checks must cover pause-versus-completion/message/admission races,
restart persistence, mixed waits on paused children, idempotent commands,
unauthorized targets, cross-session sender attribution, terminal successors,
delivery guards and rollback/deleted context ranges. Run cases individually and
sequentially with one worker, then scoped checks and unchanged guards.

Live qualification requires actual parent/child models: pause a long child,
prove model iteration stops while its real task keeps running, complete work
during the hold, resume once with retained results, then separately cancel the
subtree and verify process/provider cleanup. Restart failed/cancelled/completed
runs with new handles and no replay. Find another real session through memory,
message it while busy and idle, and verify next-iteration/wake delivery, reply
identity, no duplicate and no silent reparenting. Include UI review and all
distinct local/relay/provider routes. Repeat affected lifecycle races five times.

This source audit is not a live model demonstration. Earlier async-task receipts
keep their original source identities and do not qualify these proposed controls.
