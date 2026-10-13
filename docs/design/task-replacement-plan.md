# Delete first, rebuild, qualify and release — revision R2

## 1. Objective, constraints and ownership

Target a Tasks release on October 14, America/Chicago. This is a target, not permission to bypass acceptance. If required gates remain failed or unavailable, publish no Tasks release: keep the currently released product unchanged, report the exact blocker, and continue on the isolated feature branch. Do not revive the old engine to meet the date.

Use codex/agent-facing-async-tasks in core and GACT, starting from core 5475042f / GACT 32044a38. Core owns runtime/tools/REST/persistence/prompts and website; GACT owns UI/API bindings and browser acceptance. Preserve the installed Desktop, auth, defaults, released pins and unrelated human work.

Delete the accumulated task integration before adding replacement production code. The removal commit is deliberately allowed to fail import/build/test collection. No stub implementations, parallel old/new execution, renamed mutable stores or runtime fallback.

Final responsibility table:
- FastMCP/Docket: ordinary Shell, Download and Indexing execution; independent Shell/storage roots.
- External MCP server: its own accepted execution.
- CLIO conversation engine: human-root and child model execution, context, finite assignment decisions.
- Existing confirmed Core hierarchy/writer: one common task observation/addressing representation, history, indexes and session mailboxes.
- Core recipient-input record: the sole durable delivery acknowledgement.
No common snapshot gets a universal transition table, workload scheduler or cross-owner reconciliation engine.

Relay's special task/placement/wait/message paths are removed. Relay subsequently connects as an ordinary MCP server. This release does not promise automatic conversion of old relay placement configuration or retained special relay lifecycle controls. Retain historical rows/identities and document unavailable visibility; do not add a relay-specific qualification gate. Generic task-capable/inline MCP behavior is qualified normally. Preserve unrelated networking/confinement facilities whose names happen to contain relay.

## 2. Before deletion, then the deliberate break

Commit two small documents before the removal commit: docs/design/task-replacement-plan.md (this reviewed contract plus removal manifest) and docs/qualification/task-replacement-acceptance.md (finite scenario ledger). The implementing agent owns them; Astra and Claude review them read-only. Each ledger row records scenario ID, required behavior, source/test lesson at committed revision, runtime/bridge prerequisites, evidence, expected outcome and pass/failed/blocked status. Removing a test cannot remove its required behavior.

Protected human files are docs/design/subagent-lifecycle-and-session-messaging.md and the untracked docs/design/agent-task-architecture-review-2026-10-12.md and docs/design/session-recall-and-long-term-memory.md. Never reset/stage/delete these. The six uncommitted test changes in mailbox_helpers.py, test_cron_tools.py, test_goal.py, test_spawn_nullable_arguments.py, test_spawn_runtime_s4.py and test_subagent_custody.py are agent-owned unfinished migrations; the human's delete-first instruction explicitly authorizes discarding them. Preserve any unexpected human changes discovered before deletion and stop only the affected destructive operation. Do not create archives/backups. Git recovery applies only to previously committed code, not discarded uncommitted edits.

Initial removal manifest (module identifiers refer to src/clio_agent):
| Remove as authority/driver | Remove its live policy/call sites |
| gact.agent_tasks.AgentTaskRegistry and its notification/consumption writers | registry state installation, mutable task maps, notify_pending/consumed_at/delegation_reported live delivery policy; retain data-only historical decoding |
| gact.mcp_task_store and tools.mcp_task_records mutable record stores | separate reserve/update/list/lease lifecycle; retain native identity requirements and legacy decoding |
| tools.native_task_host.NativeTaskHost's record/drive/settlement policy and gact.core_task_journal.CoreTaskJournal's native-row/cross-owner reconciliation | old native rows, owner orchestration, receipt-spin loops; retain useful native root configuration and confirmed Core/input-write algorithms |
| gact.question_tasks and task-specific authority/delivery in user_question_ledger | parallel Question task mirror, agent blocking/async delivery variants and Question-only consumption; preserve permission/external-input gate semantics |
| tools.mcp_tasks driving loops, tools.mcp_wait_ladder, tools.task_driver_lease, gact.task_mcp_owner and TaskSupervisor drivers | custom execution polling, lease renewal and alternate cancellation/settlement ladders; keep no generic old driver |
| gact.child_forward terminal writers/timers; assignment-status admission in turn_spawn; turn_spawn_executor pools | independent terminal publication, deadlines and per-depth whole-turn scheduling |
| gact.task_projection owner joins; task_completion_wake/loop_inbox policy; composed composer idle hooks and old acceptance/consumption guards | full-registry reconstruction, competing spawn/wake decisions and read-time migration |
| gact.task_relay_owner, relay_wiring, relay_expert_invoker/relay_invoker_runtime, special relay route/status/timeline and tools.relay_transport/console/CLI integration | placement registry, dedicated task observers, special waits/messages/install catalog entries and corresponding callbacks |

Expand this manifest from production callers before deleting: classify each affected schema/config key as removed internal state, retained public/workload contract or legacy decoder. Explicitly retain native backend/concurrency settings, existing child inference/fanout budgets, mailbox pending-only settings, permissions and confinement. Old driver deadline/lease settings are removed, not silently repurposed.

Delete architecture-bound tests/fixtures and their obsolete generated expectations. Keep independent tests of preserved algorithms (confinement, bytes/hashes, manifests, atomic publication, output bounds, cleanup); rewrite coupled cases as fresh public-behavior tests from the ledger. Do not retain old stores only to satisfy tests.

The removal commit includes a small static denylist guard for removed production symbols/imports/config/catalog entries; historical fixture text and explicitly listed pure compatibility aliases are exempt. Review the actual diff and search results, not line counts alone. Shipped public aliases may be rebuilt as delegates later; unfinished branch internals have no compatibility exemption.

Keep the deliberately broken commit local, with PRs draft. Do not merge/tag, dispatch publication workflows or update installed clients. Normal branch checks cannot be described as acceptance. Verified current publishing gates require tags or explicit release dispatch (Pages deploys main); the broken feature head must trigger neither. Use existing check commands only once the replacement restores a coherent runnable candidate.

Retain workload algorithms for confined process execution/output, approved providers and transfers, revisions/byte/hash accounting, folder enumeration, manifest publication and cleanup. There is no code archive; committed source history remains the comparison point. Astra/Claude verify removal completeness before rebuilding.

## 3. Rebuild: one record/mailbox and native execution

### Core representation, writers and migration

Use one typed TaskSnapshot for Shell, Download, Indexing, MCP, Session, Subagent and Question. Common fields: opaque public handle, original description/assignment and missing-legacy flag, immutable owner/human/delegation/assignment identity, invocation, backend reference, raw and effective status, activity, progress, timestamps, supported actions, cancellation request, connection freshness, settlement/recording state and result references. Domain-specific context/lineage, question/answer and storage metadata remain typed details/references, not independent generic task lifecycles.

Trusted request boundary writes submission context. Native SDK/CLIO-owned workers publish execution observations. The conversation engine alone decides assignment transitions; Question commands alone decide answer/cancel transitions. One confirmed Core writer records these and updates passive indexes. Model-input commits alone acknowledge notifications. No task snapshot routes execution or reconciles other owners.

Store bodies/results once, then reference them. Use the existing ClioCoreStore/process ARC semantic-event and context lanes with confirmed writer ordering (content first, authoritative record after; put_many is not a transaction). Core-backed latest-task/pending-recipient indexes are rebuildable projections. Use them for hot query/resolve/wait/mailbox reads; no repeated full-history/owner scans. No new database, LSM or checkpoint framework; measure startup replay before adding any optimization.

Fresh data-only startup migration reads old formats without invoking old owners. Preserve handles/aliases, stable session addresses, lineage, results, pending Questions/mail, subscriptions, proven recipient-input receipts and full provider/backend identities. Allocate deterministic persisted mappings only where a legacy record had no public handle; ambiguous aliases do not resolve. Preserve ambiguous legacy delivery as unknown rather than inventing an acknowledgement. Historical relay rows remain readable without execution support. Lost memory-backed local work is interrupted; unresolved persistent/external work stays uncertain/reconnectable. Migration never submits operations. Run twice and verify stable identities, no duplicate pending notices and no replay.

### Native MCP boundary

Pin FastMCP/fastmcp-tasks 4.0.0b5, MCP 2.0.0 and Docket 0.25.0 initially. Their source-level feasibility has been reviewed; this is not runtime acceptance. If a required integration contract fails its focused checks, report a blocker, not an old-engine fallback.

Register built-ins through FastMCP, including short non-background control tools. Shell/storage use independent native runtime roots, lifespans/queue identities and configurable worker concurrency 10 each. memory:// is default; expose existing persistent-backend configuration without promising exactly-once recovery.

Use normal Client.call_tool/call_tool_mcp for inline results and SDK pre-task input re-entry. A reduced TaskAwareClient overrides only acceptance resolution and local receipt parsing: intercept ClientCreateTaskResult, shield confirmed adoption across Stop, construct ToolTask(raise_on_error=False), retain an app-owned observer and return a distinctly typed local receipt. Only the local type bypasses backend output parsing; untrusted JSON cannot request this. Other claims/results delegate to SDK behavior.

One ToolTask.result() coroutine owns post-acceptance polling/input driving with no inherited whole-call deadline. A narrow ClientTransport wrapper preserves identity/auth/options/lifecycle and installs ObservedTaskSession via supported TransportOptions.session_class, composing an existing compatible session subclass or rejecting incompatibility before submission. Delegate send_request to super; record the SDK's tasks/get responses and add task-ID Mcp-Name through request-local adaptation. No monkey patch, extra status poller or copied task-driving loop.

The observer validates raw terminal payload against accepted tool/version/schema, not a later refreshed schema or coerced parsed output. Preserve raw failures/malformed output and record contract failure before any successful completion. Final validation is in the identity-bound observer, not the acceptance parser.

Elicitation is bound to immutable observer-local full backend/auth-scope/session/task identity and server input keys. Match known request identity/payload; never split hyphenated request IDs or use a shared mutable current-task property. Reject ambiguity or a reused key with changed content. Persist each typed answer before returning it. The session confirms canonical inputResponses before sending tasks/update; do not replay old JSON-RPC envelopes. If only some keys are answered, retain those answers and keep the rest pending; SDK ordering sends the set when ready. Lost update replies/reconnect return persisted answers without asking again.

Upgrade contract tests cover the supported transport hook and all relied-on pinned/private client/ToolTask callback/parser/request-ID behavior. Keep this dependency coupling in this one adapter.

### Acceptance, settlement and recovery

Persist public handle/context before submission: tool/digest/arguments, workspace, permissions, owner/assignment/invocation, attribution and explicit execution limits. Use a separate internal random reference hidden from model schema. CLIO-owned worker validation resolves it, checks revocations/descendant admission, binds native identity plus Docket execution/leg metadata and allocates a unique admission-incarnation receipt before effects. Native retry counters are not incarnation IDs. External servers receive no CLIO internal arguments.

Distinguish confirmed rejection, accepted recording-unconfirmed and acceptance-uncertain. Finish acceptance custody across Stop races. Never automatically repeat an uncertain tools/call.

Shell foreground/background share one native workload. Stop cancels foreground Shell and waits for physical cleanup; explicitly backgrounded tasks and Questions continue. Wait cancellation leaves members running. Explicit task cancellation overrides background mode for the selected task/subtree.

Cover validation, effect acquisition and cleanup with one boundary. Record effects-never-started separately from worker-never-started; distinguish cancellation withdrawal, cleanup still progressing and genuinely unknown settlement. Terminal/withdrawn records cannot be reopened by late entry; prior incarnation receipts cannot settle another attempt. External acknowledgement is not proof of cleanup.

Unknown acceptance/visibility/settlement produces one actionable attention episode, not success or an endless receipt spin. wait_tasks returns task_state_uncertain and pending handles, without a terminal timestamp or collection acknowledgement for that handle. Known cleanup still progressing continues waiting. Attention IDs include recipient/handle/episode; final-outcome IDs are distinct. Owner/subscriber receipts are separate; repeated uncertainty/progress cannot repeatedly wake an agent or consume eventual final delivery.

Recover/reconnect ToolTask on the verified original backend/auth identity and captured acceptance/schema; never submit again. Reattach surviving Globus/provider jobs by original IDs without a transfer scheduler or duplicate job. Close old observation registrations so transport recovery can actually restart observation.

Application lifespan runs one pending-only recovery coroutine: first provisional observation/lost visibility schedules existing RPC health probes at 1,2,4,...30-second capped backoff. Keep entries until owner-local flush/reattachment succeeds; probe success alone clears nothing. Stop the coroutine when no pending recovery remains; check pending recovery at startup/readiness. Journal does not orchestrate owners. Recover interrupted active model segments with fixed context and uncertainty; dormant/yielded/watchers do not wake merely because service restarted.

Core outage rejects new undurable submissions/messages. Trusted pause/cancel of verified live work still acts and reports recording-unconfirmed; volatile evidence cannot promise crash recovery. On recovery reconcile observations/notices and release only the matching holds.

Shutdown closes admission, cancels/withdraws owned local native executions and awaits actual settlement/worker retirement before leaving lifespans/Core. Show unresolved state; only explicit human process force-close can end it with uncertainty. Remove inherited automatic drain cutoffs. Surviving external jobs are not declared dead merely because local observation stops.

## 4. Rebuild: assignments, controls, input and UI

Preserve query_tasks(kind,status,handle,tool,agent,active_only,cursor,limit=50,scope=tree), observe_tasks(tasks,cursor,pattern,timeout_s,notify), wait_tasks(tasks,return_when=all,timeout_s), cancel_tasks(tasks), get_task_result(handle). One/list inputs and query handles work for every control. Preserve shipped aliases as pure delegates for one cycle, without old state or policy.

Authorization precedes lookup disclosure/counts/filter/pagination and is rechecked at injection/control. Tree scope includes the stable session, predecessor work and descendants; child agents get no ancestor/sibling rights automatically. Authorized peers require human/configuration Core grants; intent grants nothing. Keep separate read/observe/message/control rights. Observe-only exposes safe status/progress; descriptions, answers and output require read. Subscriptions require read+observe and cannot consume owner delivery.

Query/observe never acknowledge completion; explicit collection and automatic delivery share recipient-input commitment. Waits default unbounded, zero snapshots and positive expiry stops only the waiter. Mixed failures never cancel others. Use indexed revisions/event conditions with atomic snapshot/register/recheck and cancellation/revocation wakeups, not 250-ms whole-projection loops. Recover old cursors from Core history; keep existing output bounds/references.

Stable session/history/mailbox survives finite assignments. Human root and child use one conversation engine. Yield, steering, task wakes, recovery and pause/resume keep the active assignment. Default response yields while owned work/dependencies/input remain; otherwise completes. Explicit completion may leave background work running. Completion alone mints no successor. Eligible later work or explicit restart creates a linked assignment; historical handles never retarget. Restart requires known necessary cancellation settlement or returns uncertainty without launching. References fixed Core context/checkpoints and operation observations, never copied transcripts/replay. Successors retain predecessor-work rights within the stable session subject to revocation.

Session-exclusive ownership spans a model turn, including waits. Inference permits cover model calls only and are released before tools/waits. Existing child per-depth/fanout values limit reserved/in-flight child inference; roots retain existing provider budgets. No new default active-session cap.

One session-owned synchronous worker exists only while a synchronous turn is active. Replace whole-turn/default/per-depth pool dependence. Convert long blocking queue/lock waits in Codex direct and Claude stream/session bridges to asynchronous waits or session-owned execution; shared default executor must not be occupied by unbounded queue.get/lock.acquire. It may serve finite I/O, not a resource needed by blocked parents to launch children/peers. Async paths retain async execution.

Stop shows stopping while cooperative cancellation/interruptible waits unwind. Session ownership releases only after actual worker exit, even if its asyncio waiter is cancelled. New input stays Core-pending during stopping; no second worker/model turn may start. Await worker retirement without blocking application loop or consuming another bounded executor. Uncancellable unresolved work remains visibly stopping until retirement or explicit human process force-close. Dormant/yielded assignments have no worker. Measure thread/memory growth; do not hide it by restoring assignment-status caps.

Pause holds model execution and lets background work continue. Resume releases it. Explicit agent cancellation closes descendant admission first, then cancels all active inherited/delegated work, including background Shell/downloads; already-terminal outcomes remain historical. Cancelling an individual task affects only that task. Human steering/pause/resume/cancel/restart records intent/effect and derives an attributed parent mailbox notice independent of peer capacity. Restart does not bypass unsettled cancellation.

TurnRunner alone reserves/admit model execution for feedback, task results, peer mail, composer, goals, loops/schedules, hooks, spotter/A2UI and approvals. Producers persist typed mailbox items and signal, never spawn/install idle policy. Busy arrivals enter next model iteration; idle/post-Stop eligible arrivals wake; explicit pause/input veto gates retain arrivals. Goal waiting gates only its declared dependency notices, never human feedback/Question answers. Preserve independently disabled goals/loops/schedules and paused future-composer queue. Closing-turn arrivals enter next iteration or subsequent admission.

Each stable session has one Core mailbox with full history. max_pending_messages=0/unset is unlimited; positive settings count undelivered peer messages including staged inputs. Human feedback/controls and accepted task results are exempt. Context batches are bounded without limiting retention. Overflow/vetoed arrivals stay visibly pending; no attempted-batch consumption/spinning.

One authoritative recipient-input record contains assignment/iteration, fixed context boundary and included notification IDs/content refs. Confirm it before calling the model. Before commit, interruption leaves input pending; after commit, recovery reconstructs it even if the model never ran. A crash after model invocation may cause external model execution to repeat; promise recoverable input delivery, not exactly-once model effects. Explicit result observations use this same recipient-specific boundary. Task owner/subscriber final/attention notices use one common publication path; progress alone creates no mailbox wake.

ask_user posts a durable Question handle immediately through a short FastMCP control; no Docket worker. Shared wait collects an answer; Stop leaves open; explicit cancel dismisses. Question UI/routes project/delegate to the same Core record. Permission and external-input gates retain safeguards, not alternate agent ask modes.

Complete minimal human session-grant/revoke UI using existing authenticated control. Assignment-scoped grant additions are excluded; do not expand historical exact grants to successors. Two actual independent declared workflow executions use existing runner and provenance root/step/session links only, no workflow engine. Qualify discovery, messages/replies, observe/wait/subscriptions and denied control.

GACT uses compact Work/Observability/Run rows, progressive disclosure, honest stopping/pending cancellation/lost visibility and identifying cancel confirmation with descendant warning. UI and agent controls call the same operations. Update capable root/child prompts (including relevant marketplace agents), task-capable tool descriptions and website using actual replacement-service screenshots.

## 5. Construction, finite acceptance and release

Critical path:
0. Commit reviewed plan/removal manifest and acceptance ledger.
1. Delete old authorities/callers/architecture-bound tests; locally commit deliberate break; independent removal review.
2. Rebuild shared Core/mailbox/input boundary and Question; native MCP/Shell/storage; assignments/admission; UI/prompts, in that order with no old authority restored.
3. Once coherent, run fresh focused behavior tests and scoped lint/format/types/guards; push draft candidate. Review actual implementation/removal map with Astra/Claude.
4. Integrate current target changes and finalize GACT; record its resulting commit in core. Freeze core/GACT/dependency/schema/runtime tuple before exact-head CI and final integrated acceptance.
5. Candidate go/no-go, then release procedure/tags/publication/asset verification. A later pointer/merge/dependency change requires recorded impact and applicable requalification; never publish a tuple created after the checks.

Fresh tests use public contracts and real production implementations; doubles stay in tests. Each is individual/sequential with one worker. Preserve assertions, resource budgets and meaningful algorithm regressions; no broad repeated suites during implementation. Required CI/checks and acceptance must pass; skipped/unavailable required gates block completion.

Finite live families:
| ID | Runtime/bridge | Completion condition and retained evidence |
| Q1 | Codex/Luna, all seven kinds | handle exists before completion and model does independent work; Question=input_required; Session accepted before inference; optional inline MCP valid inline result |
| Q2 | Codex/Luna, mixed kinds | progress/cursors, observe/pattern, any/all/expired waits, honest failures/uncertainty and continuing pending members |
| Q3 | Codex/Luna plus distinct Claude bridge | busy-next-iteration, idle/post-Stop, pause, goal/Question and owner/peer delivery; child Questions and mixed Question/Shell/Subagent |
| Q4 | Codex/Luna plus Claude child/control paths | child yield/download/wake under one handle; pause/resume/cancel/restart, inherited work, human parent notices and actual subtree settlement |
| Q5 | independent sessions and two declared workflow runs | authorized discovery/messages/replies/observe/waits/subscriptions; read/observe/control separation, denial and revocation before injection |
| Q6 | actual external MCP and provider integration | status-only progress, same-key input validation, partial answers/lost-update reply, reconnect and verified surviving provider-job reattachment |
| Q7 | isolated real Core/native service | Core outage idle recovery, migration twice, input-commit crash windows, side-effect-before-result-loss, deliberate inspection/retry and attention-then-final delivery |
| Q8 | native roots and conversation engine | saturated Shell with storage starting independently; inference capacity one parent/child/grandchild and same-depth peers; constrained default executor; Stop/new input cannot overlap old worker; resource retirement |
| Q9 | actual production service and GACT | desktop/phone rows/disclosure/Question answering/grants/cancel controls with no errors/containment failures and physical outcomes |

Record actual runtime/platform/bridge/models, source IDs, handles, invocations, timestamps, transcripts and backend/filesystem/process outcomes. Use Codex/Luna for shared behavior and Claude where its bridge differs, not a Cartesian product. Verify real bytes/hashes/manifests/output. Include >1,000 retained messages, pending-only/staged backpressure, bounded hot-read work and legacy missing descriptions.

Repeat these six races five times each on the final candidate: R1 Stop/acceptance; R2 late-start/cancel; R3 busy-to-idle arrival; R4 collection/automatic delivery; R5 recipient-input commit recovery; R6 subtree cancellation/admission. Record a matrix row per repeat. Also explicitly gate migration idempotence and uncertainty-then-final delivery.

Harness deadlines only: preflight native/real-Core cases allow 120 seconds per case; model scenarios 600 seconds; capacity/recovery families 900 seconds. They are diagnostics, never product deadlines. On expiry mark failed/blocked with current evidence, stop the model turn, explicitly cancel owned work and await settlement. Unknown custody blocks subsequent launches; no forced settlement/kill of unrelated processes. Respect every existing prohibited/manual-only launch/removal boundary. Provider capacity/auth/prerequisite failures are blocked gates, not reasons to patch task code. Freeze scope; a new authority/driver need returns to architecture review.

Preflight availability and permitted isolated Windows/Linux/source routes before deleting; no product qualification launches during this planning review. Old native/probe evidence cannot accept the replacement. Do not keep retrying an unavailable route or pretend a fixture qualifies it.

The implementing agent owns ledger updates and cleanup. Before each test family register owned processes/ports/data; afterward settle/remove disposable state including owned planning-review cache (no credentials copied), retaining bounded receipts and selected documentation media. No bulky duplicate exports, code archives, obsolete worktrees/environments or installed-state changes. Previously rejected/manual-only paths remain untouched.

Publication is a separate gated stage after candidate review. Resolve next version/channel, branch direction and tags using the repository release procedure before publishing; preserve the reviewed GACT/core pair. October 14 gets a go/no-go at candidate freeze and immediately before tag/publication. If gates do not pass, keep current release unchanged and report exact outstanding rows; no weakened tests, skipped acceptance or old-engine fallback.


## Committed-revision removal inventory

Inventory source: core `5475042feda49c1354f9f88b19051cb53d7fa740`; GACT `32044a387472b1495f60a24c862c6b9e4292abc3`. The following are complete module removals. Production imports/callers were enumerated with Python AST, including function-local imports. Caller locations below identify the old bindings to remove, not compatibility permissions. A removal guard must reject these module imports and their authority symbols in production.

| Removed module beneath `src/clio_agent` | Production caller files at the committed revision |
| --- | --- |
| `gact/agent_tasks.py` | `gact/action_cards.py`, `gact/agent_messaging.py`, `gact/agent_targets.py`, `gact/agent_task_admission.py`, `gact/app.py`, `gact/assignment_history.py`, `gact/background_exit.py`, `gact/child_forward.py`, `gact/human_task_intervention.py`, `gact/live_handle.py`, `gact/relay_timeline.py`, `gact/run_registry.py`, `gact/session_run_tasks.py`, `gact/spotter_arm_review.py`, `gact/spotter_watcher.py`, `gact/subagent_lifecycle.py`, `gact/subagent_restart.py`, `gact/task_fold.py`, `gact/task_subagent_owner.py`, `gact/turn_spawn.py`, `gact/turn_spawn_failures.py`, `gact/workflows.py`, `gact/workflow_step_watch.py`, `gact/agents/invoker.py`, `gact/agents/native_presenters.py`, `gact/agents/native_presenters_tasks.py`, `gact/agents/relay_expert_invoker.py`, `gact/agents/spawn_runtime.py`, `gact/agents/tool_instrumentation.py`, `gact/provenance/child_projection.py`, `gact/routes/async_processes.py`, `gact/routes/messages.py` |
| `gact/agent_task_admission.py` | `gact/turn_spawn.py` |
| `gact/agent_task_recovery.py` | `gact/agent_tasks.py` |
| `gact/agent_task_notifications.py` | `gact/enrichment.py` |
| `gact/assignment_history.py` | `gact/agent_targets.py`, `gact/agent_tasks.py`, `gact/core_task_journal.py`, `gact/human_task_intervention.py`, `gact/message_admission.py`, `gact/server_boot.py`, `gact/session_run_tasks.py`, `gact/spawn_context.py`, `gact/subagent_lifecycle.py`, `gact/subagent_restart.py`, `gact/task_subagent_owner.py`, `gact/turn_runner.py`, `gact/turn_state.py`, `gact/routes/session_cancellation.py` |
| `gact/agent_mailbox.py` | `gact/agent_initialization.py`, `gact/agent_message_transport.py`, `gact/agent_messaging.py`, `gact/agent_session_messaging.py`, `gact/composer_runtime.py`, `gact/core_task_journal.py`, `gact/elicitation_forwarding.py`, `gact/goal.py`, `gact/human_task_intervention.py`, `gact/live_handle.py`, `gact/loop_inbox.py`, `gact/message_admission.py`, `gact/plan_exit_resolution.py`, `gact/scheduler_runtime.py`, `gact/session_run_tasks.py`, `gact/spotter_clearance.py`, `gact/spotter_watcher.py`, `gact/subagent_lifecycle.py`, `gact/subagent_restart.py`, `gact/turn.py`, `gact/turn_runner.py`, `gact/turn_start_offloop.py`, `gact/user_question_resume.py`, `gact/a2ui_actions/delivery.py`, `gact/hooks/defer.py`, `gact/hooks/stop_loop.py`, `gact/routes/documents.py`, `gact/routes/messages.py`, `gact/routes/message_intents.py` |
| `gact/async_user_question.py` | `gact/ask_user_tool.py`, `gact/user_question_ledger.py` |
| `gact/child_forward.py` | `gact/elicitation_forwarding.py` |
| `gact/core_task_journal.py` | `gact/agent_initialization.py`, `gact/agent_mailbox.py`, `gact/agent_tasks.py`, `gact/assignment_history.py`, `gact/composer_runtime.py`, `gact/human_task_intervention.py`, `gact/mcp_task_store.py`, `gact/message_admission.py`, `gact/question_tasks.py`, `gact/server_boot.py`, `gact/session_run_tasks.py`, `gact/task_completion_wake.py`, `gact/task_controls.py`, `gact/task_delivery.py`, `gact/task_permissions.py`, `gact/task_subscriptions.py`, `gact/turn_runner.py`, `gact/turn_spawn.py`, `gact/user_question_ledger.py`, `tools/native_task_host.py` |
| `gact/human_task_intervention.py` | `gact/agent_session_messaging.py`, `gact/message_admission.py`, `gact/task_controls.py`, `gact/routes/agent_lifecycle.py`, `gact/routes/agent_tasks.py`, `gact/routes/session_cancellation.py` |
| `gact/loop_inbox.py` | `gact/app.py`, `gact/composer_runtime.py`, `gact/goal_control.py` |
| `gact/mcp_task_events.py` | `gact/app.py` |
| `gact/mcp_task_store.py` | `gact/agent_targets.py`, `gact/run_registry.py`, `gact/server_boot.py`, `gact/sessions.py`, `gact/session_run_tasks.py`, `gact/task_backend_identity.py`, `gact/task_projection.py`, `gact/task_recovery.py`, `gact/task_relay_owner.py`, `gact/task_supervisor.py`, `tools/mcp_task_records.py`, `tools/task_submission.py`, `gact/routes/async_processes.py`, `gact/routes/interactions.py` |
| `gact/question_tasks.py` | `gact/task_projection.py`, `gact/task_supervisor.py` |
| `gact/session_run_tasks.py` | `gact/agent_targets.py`, `gact/agent_task_recovery.py`, `gact/composer_runtime.py`, `gact/core_task_journal.py`, `gact/message_admission.py`, `gact/part_atom_minter.py`, `gact/subagent_restart.py`, `gact/task_recovery.py`, `gact/turn_runner.py`, `gact/turn_spawn.py`, `gact/turn_start_offloop.py`, `gact/agents/clio_react_submit.py` |
| `gact/subagent_lifecycle.py` | `gact/agent_lifecycle_tools.py`, `gact/agent_mailbox.py`, `gact/agent_session_messaging.py`, `gact/composer_runtime.py`, `gact/human_task_intervention.py`, `gact/message_admission.py`, `gact/session_run_tasks.py`, `gact/subagent_restart.py`, `gact/task_projection.py`, `gact/turn.py`, `gact/turn_runner.py`, `gact/turn_spawn.py`, `gact/routes/agent_lifecycle.py` |
| `gact/subagent_restart.py` | `gact/agent_lifecycle_tools.py`, `gact/turn_spawn.py`, `gact/routes/agent_lifecycle.py` |
| `gact/task_backend_identity.py` | `gact/relay_timeline.py`, `gact/run_registry.py`, `gact/task_projection.py`, `gact/task_recovery.py`, `gact/task_relay_owner.py`, `gact/agents/relay_invoker_runtime.py`, `gact/routes/async_processes.py` |
| `gact/task_completion_wake.py` | `gact/agent_initialization.py`, `gact/agent_mailbox.py`, `gact/agent_tasks.py`, `gact/server_boot.py`, `gact/task_delivery.py`, `gact/task_subscriptions.py`, `gact/user_question_ledger.py`, `gact/user_question_resume.py`, `tools/native_task_host.py` |
| `gact/task_context_frame.py` | `gact/agent_mailbox.py` |
| `gact/task_controls.py` | `gact/task_delivery.py`, `gact/task_tools.py`, `gact/agents/agent_task_output_digest.py`, `gact/agents/observe_runtime.py`, `gact/agents/spawn_runtime.py`, `gact/routes/async_processes.py`, `gact/routes/connected_storage.py`, `gact/routes/session_questions.py` |
| `gact/task_delivery.py` | `gact/agent_mailbox.py`, `gact/core_task_journal.py`, `gact/mcp_task_events.py`, `gact/session_run_tasks.py`, `gact/task_controls.py`, `gact/task_notifications.py` |
| `gact/task_fold.py` | `gact/child_forward.py`, `gact/session_run_tasks.py`, `gact/turn_spawn.py`, `gact/agents/relay_expert_invoker.py` |
| `gact/task_input_owner.py` | `gact/task_mcp_owner.py` |
| `gact/task_input_questions.py` | `gact/elicitation_bridge.py`, `gact/task_recovery.py`, `gact/task_supervisor.py`, `gact/user_question_ledger.py` |
| `gact/task_mcp_owner.py` | `tools/mcp_task_extension.py` |
| `gact/task_notifications.py` | `gact/enrichment.py` |
| `gact/task_permissions.py` | `gact/agent_targets.py`, `gact/question_tasks.py`, `gact/task_controls.py`, `gact/task_projection.py`, `gact/task_subscriptions.py`, `gact/routes/agent_lifecycle.py` |
| `gact/task_projection.py` | `gact/core_task_journal.py`, `gact/goal_wait.py`, `gact/run_registry.py`, `gact/session_run_tasks.py`, `gact/task_controls.py`, `gact/task_delivery.py`, `gact/task_fold.py`, `gact/task_recovery.py`, `gact/task_relay_owner.py`, `gact/task_subagent_owner.py`, `gact/task_submission_custody.py`, `gact/task_subscriptions.py`, `gact/task_supervisor.py`, `gact/task_wait_presentation.py`, `gact/agents/agent_task_output_digest.py`, `gact/agents/observe_runtime.py`, `gact/agents/spawn_runtime.py`, `gact/routes/async_processes.py` |
| `gact/task_recovery.py` | `gact/server_boot.py`, `gact/task_mcp_owner.py` |
| `gact/task_recovery_client.py` | `gact/task_recovery.py` |
| `gact/task_relay_owner.py` | `gact/task_recovery.py`, `gact/task_supervisor.py`, `gact/agents/relay_expert_invoker.py` |
| `gact/task_subagent_owner.py` | `gact/task_relay_owner.py`, `gact/turn_spawn.py` |
| `gact/task_submission_custody.py` | `gact/session_run_tasks.py`, `gact/task_fold.py`, `gact/task_mcp_owner.py`, `tools/task_submission.py`, `gact/agents/invoker.py`, `gact/agents/relay_expert_invoker.py` |
| `gact/task_subscriptions.py` | `gact/agent_tasks.py`, `gact/mcp_task_events.py`, `gact/task_controls.py`, `gact/task_delivery.py`, `gact/task_recovery.py`, `tools/native_task_host.py` |
| `gact/task_supervisor.py` | `gact/server_boot.py`, `gact/task_controls.py`, `gact/task_mcp_owner.py`, `gact/task_recovery.py`, `gact/task_relay_owner.py`, `gact/task_subagent_owner.py`, `gact/task_submission_custody.py`, `tools/task_submission.py` |
| `gact/task_tools.py` | `gact/agents/auto_tools.py`, `gact/storage/download_tool.py` |
| `gact/turn_spawn.py` | `gact/agent_elicitation_answer_turn.py`, `gact/agent_elicitation_dispatch.py`, `gact/agent_messaging.py`, `gact/app.py`, `gact/child_forward.py`, `gact/spawn_context.py`, `gact/spotter_watcher.py`, `gact/subagent_restart.py`, `gact/task_fold.py`, `gact/task_supervisor.py`, `gact/turn_forward.py`, `gact/turn_runner.py`, `gact/agents/blueprint_commission.py`, `gact/agents/invoker.py`, `gact/agents/module_variants.py`, `gact/agents/relay_expert_invoker.py`, `gact/agents/skill_spawn_effect.py`, `gact/agents/spawn_placement.py` |
| `gact/turn_spawn_executor.py` | `gact/turn_spawn.py` |
| `gact/run_registry.py` | `gact/routes/agent_tasks.py` |
| `gact/agent_targets.py` | `gact/agent_lifecycle_tools.py`, `gact/agent_session_messaging.py`, `gact/memory_tools.py`, `gact/routes/agent_lifecycle.py` |
| `gact/agent_messaging.py` | `gact/agent_session_messaging.py`, `gact/agents/spawn_runtime_declarations.py`, `gact/routes/agent_tasks.py` |
| `gact/agent_session_messaging.py` | `gact/agent_messaging.py`, `gact/routes/agent_lifecycle.py` |
| `gact/agent_message_transport.py` | `gact/agents/invoker.py`, `gact/agents/relay_expert_invoker.py` |
| `gact/relay_wiring.py` | `gact/session_host_agent.py`, `gact/turn_forward.py`, `gact/routes/providers.py`, `gact/routes/relay.py` |
| `gact/relay_status.py` | `gact/routes/relay.py`, `gact/routes/system.py` |
| `gact/relay_timeline.py` | `gact/live_handle.py`, `gact/agents/relay_invoker_runtime.py`, `gact/routes/agent_tasks.py` |
| `gact/agents/relay_expert_invoker.py` | `gact/relay_wiring.py` |
| `gact/agents/relay_invoker_runtime.py` | `gact/task_backend_identity.py`, `gact/agents/relay_expert_invoker.py` |
| `gact/routes/agent_tasks.py` | `gact/app.py` |
| `gact/routes/async_processes.py` | `gact/app.py`, `gact/task_projection.py`, `gact/routes/interactions.py` |
| `gact/routes/relay.py` | `gact/app.py` |
| `tools/mcp_tasks.py` | `gact/task_input_owner.py`, `gact/task_mcp_owner.py`, `gact/task_recovery.py`, `tools/mcp_task_extension.py`, `tools/mcp_wait_ladder.py`, `tools/relay_transport.py`, `tools/task_observers.py` |
| `tools/mcp_task_records.py` | `gact/elicitation_correlation.py`, `gact/mcp_task_events.py`, `gact/mcp_task_store.py`, `gact/run_registry.py`, `gact/server_boot.py`, `gact/task_backend_identity.py`, `gact/task_input_owner.py`, `gact/task_input_questions.py`, `gact/task_mcp_owner.py`, `gact/task_projection.py`, `gact/task_recovery.py`, `gact/task_supervisor.py`, `tools/jarvis_jobs.py`, `tools/mcp_handlers.py`, `tools/mcp_tasks.py`, `tools/mcp_task_extension.py`, `tools/mcp_task_lease.py`, `tools/mcp_wait_ladder.py`, `tools/relay_console.py`, `tools/relay_console_stream.py`, `tools/relay_factory.py`, `tools/relay_transport.py`, `tools/task_driver_lease.py`, `tools/task_observers.py`, `gact/agents/relay_invoker_runtime.py`, `gact/routes/async_processes.py`, `gact/routes/interactions.py`, `gact/routes/system.py` |
| `tools/mcp_task_lease.py` | `tools/mcp_task_records.py` |
| `tools/mcp_task_extension.py` | `gact/task_recovery.py`, `tools/mcp_extension_registry.py`, `tools/relay_transport.py`, `tools/task_submission.py` |
| `tools/mcp_wait_ladder.py` | `tools/mcp_call_progress.py`, `tools/mcp_executor.py`, `tools/mcp_tasks.py`, `tools/task_observers.py` |
| `tools/task_driver_lease.py` | `tools/mcp_tasks.py` |
| `tools/task_observers.py` | `gact/task_mcp_owner.py`, `gact/task_recovery.py`, `tools/mcp_task_extension.py`, `tools/relay_transport.py` |
| `tools/task_submission.py` | `tools/mcp_executor.py` |
| `tools/native_task_host.py` | `gact/server_boot.py`, `tools/foreground_cancellation.py`, `tools/mcp_executor.py`, `tools/servers/storage_server.py`, `gact/agents/clio_react_record.py`, `gact/storage/connect_tool.py`, `gact/storage/download_tool.py` |
| `tools/native_task_tool.py` | `tools/native_task_host.py`, `tools/task_submission.py`, `tools/servers/shell_server.py`, `tools/servers/storage_server.py` |
| `tools/mcp_call_progress.py` | `tools/task_submission.py` |
| `tools/relay_transport.py` | `gact/relay_wiring.py`, `tools/jarvis_jobs.py`, `tools/jarvis_result_contract.py`, `tools/relay_artifact_fetch.py`, `tools/relay_console.py`, `tools/relay_console_stream.py`, `tools/relay_factory.py`, `tools/remote_mcp.py`, `gact/agents/relay_invoker_runtime.py` |
| `tools/relay_factory.py` | `gact/relay_status.py`, `gact/relay_wiring.py`, `tools/relay_transport.py`, `gact/routes/relay.py` |
| `tools/relay_contract.py` | `tools/relay_transport.py` |
| `tools/relay_console_stream.py` | `tools/relay_console.py`, `tools/relay_transport.py` |
| `tools/relay_console.py` | `tools/relay_console_stream.py`, `tools/relay_transport.py` |
| `tools/relay_cli_runner.py` | `tools/relay_factory.py`, `tools/relay_install_jobs.py`, `tools/relay_install_surface.py` |
| `tools/relay_artifact_fetch.py` | `tools/remote_mcp.py` |
| `tools/relay_install_jobs.py` | `tools/relay_factory.py`, `tools/relay_install_surface.py` |
| `tools/relay_install_surface.py` | `tools/gateway.py`, `tools/relay_factory.py` |

### Partial removals and retained boundaries

| Existing boundary | Delete | Retain or rebuild only under the reviewed owner |
| --- | --- | --- |
| `gact/turn_runner.py`, `turn_forward.py`, `turn.py`, `turn_start_offloop.py` | Idle-hook composition, task-specific attempted batches, competing admission and shutdown cutoffs; whole-turn pooled execution | Session-exclusive turn lifetime; confirmed recipient-input algorithm; engine callbacks and unrelated tracing |
| `gact/user_question_ledger.py`, `user_question_pause.py`, `user_question_resume.py` | Task mirrors, async/blocking agent ask variants, task wake/consumption and read-time migration | Human permission/external-input safeguards; Question/answer payload contract |
| `tools/task_receipt.py` | Old-store `record_invalid_result` writer and old extension claim policy | Local receipt type principle; strict raw-schema validation without external reference retrieval; narrow SDK adapter rebuilt after deletion |
| `tools/mcp_executor.py`, `mcp_runtime.py`, `mcp_handlers.py`, `mcp_task_routing.py` | Old extension/lease/wait-ladder integration and per-call execution ownership | Negotiated capability routing, transport/authentication, permission boundary and bounded output algorithms |
| `gact/storage/service.py`, `store.py`, `indexing.py`, `transfers.py`, `tools/servers/storage_server.py` | Storage-owned background scheduling, generic task row mirrors, recovery that interrupts surviving provider jobs, native-host dispatch/receipt adapters | Approved providers/revisions/selected paths; bytes/hashes; complete-manifest atomic publication; transfer cleanup and original provider job identities |
| `tools/servers/shell_server.py` | Native-host dispatch and generic task receipt policy | Confined process execution, explicit execution timeout, incremental output/spill bounds and process-tree cleanup |
| App/session initialization and REST route installation | Registry/store/supervisor installation, relay/task route imports and obsolete hooks | Unrelated product APIs; bindings rebuilt to one task representation and verified owner commands |
| `tools/definitions.py`, gateway/catalog/CLI and relay-related agent configuration | Special relay placement/install/job tools, wait/messages, status/timeline callbacks | Ordinary configured MCP servers and unrelated network proxy/confinement relay facilities |

The removal commit intentionally has no compatibility aliases. Only confirmed shipped public names may later be rebuilt as stateless delegates; branch-internal imports have no exemption. Delete coupled tests/fixtures, but preserve independent workload tests even when their old fixture must later be replaced. No required behavior is removed from the acceptance ledger.

### Schema and configuration classification

| Family | Classification | Treatment |
| --- | --- | --- |
| `agent_tasks`, `mcp_tasks`, native task rows, Question mirrors and notification consumption flags in session metadata | Historical decoding only | Fresh startup migration reads them once, preserves proven IDs/history and writes deterministic mappings; never reinstall a mutable owner |
| `notify_pending`, `consumed_at`, `delegation_reported`, leases, wait-ladder deadlines and forwarded-child timer state | Removed internal state (historical values may be decoded as evidence) | No production transition/delivery/admission policy may use these fields; unknown historical delivery is not an acknowledgement |
| `agents.child_forward_deadline_s` / `CLIO_CHILD_FORWARD_DEADLINE_S`, task driver lease/deadline settings | Removed internal configuration | Delete active reads/defaults/generated references, rather than repurposing them |
| `relay.*` special integration keys and placement/catalog state | Removed active configuration; historical decoding only for retained rows | No automatic conversion, special runtime or relay-specific acceptance |
| `agent_tasks.max_concurrent` / `CLIO_MAX_CONCURRENT_AGENT_TASKS`, existing child depth/fanout budgets | Retained public inference budget | Apply at child model-call admission, never as an active-session/whole-turn thread cap |
| Native backend/concurrency settings, default concurrency 10 for each independent root | Retained public native configuration | FastMCP/Docket owns capacity; `memory://` remains default |
| `gact.mailbox.max_pending_messages` | Retained public contract | 0/unset unlimited; positive values count only undelivered peer messages, including staged inputs |
| Shell/output/resource/transfer bounds, provider identities, permissions and confinement | Retained workload/security contract | Preserve independent algorithm regressions; no weakened safeguards |
| Task/Question/session/control REST and tool schemas | Retained public behavior | Rebuild against typed `TaskSnapshot` and owner commands; histories retain original execution identities |

## Pre-deletion availability receipt

Read-only preflight on 2026-10-13 found the feature checkout and GACT at the required commits with only the three protected human design files and six authorized unfinished test migrations changed. Feature Python is 3.14.6; iowarp-core 2.3.1 and its binding are installed; FastMCP/fastmcp-tasks 4.0.0b5, MCP 2.0.0 and Docket 0.25.0 are available. Codex credentials exist and Claude credentials have an unexpired token; neither is a successful live-model acceptance result. Actual Claude Code is installed. Read-only SSH to homelab succeeds on Linux 5.10 with Python3; uv is absent from its default PATH, so isolated Linux runtime preparation remains a prerequisite.

No product/native qualification was launched in preflight. Prior automatic-review prohibitions still apply to their exact operations/paths. Local permitted source/native routes must be selected without retrying those prohibited launches. A route that cannot be made available within those boundaries remains blocked, never waived.


## Expanded deletion bindings

The caller audit additionally identified these dedicated wrappers as part of the same removed architecture:

- `src/clio_agent/gact/agent_lifecycle_tools.py`
- `src/clio_agent/gact/ask_user_tool.py`
- `src/clio_agent/gact/background_exit.py`
- `src/clio_agent/gact/goal_wait.py`
- `src/clio_agent/gact/live_handle.py`
- `src/clio_agent/gact/message_admission.py`
- `src/clio_agent/gact/user_question_ledger.py`
- `src/clio_agent/gact/user_question_resume.py`
- `src/clio_agent/gact/user_question_pause.py`
- `src/clio_agent/gact/agent_elicitation_answer_turn.py`
- `src/clio_agent/gact/agents/invoker.py`
- `src/clio_agent/gact/agents/observe_runtime.py`
- `src/clio_agent/gact/agents/spawn_placement.py`
- `src/clio_agent/gact/agents/spawn_runtime.py`
- `src/clio_agent/gact/agents/spawn_runtime_declarations.py`
- `src/clio_agent/gact/agents/skill_spawn_effect.py`
- `src/clio_agent/tools/jarvis_jobs.py`
- `src/clio_agent/tools/jarvis_result_contract.py`
- `src/clio_agent/tools/remote_mcp.py`
- `src/clio_agent/gact/routes/agent_lifecycle.py`
- `src/clio_agent/tools/servers/storage_server.py`

The partial-removal inventory includes the following old definitions. Their unrelated containing modules and workload algorithms are retained; missing replacement bindings are intentional in the removal commit.

- `gact/server_boot.py`: `reconcile_connected_storage`, `shutdown_connected_storage`, `shutdown_tasks`, `start_task_hosts`
- `gact/turn_forward.py`: `_forward_executor`, `_run_turn_setup_off_loop`, `_run_module`, `forward_turn`
- `gact/turn_runner.py`: `TurnRunner.set_idle_hook`, `TurnRunner.idle_hook`, `TurnRunner.drain`, `install_turn_runner`, `_admit_pending_inputs`, `drain_app_turns`
- `gact/composer_runtime.py`: `_install_composer_idle_hook`, `recover_pending_feedback`
- `gact/agent_initialization.py`: `refuse_parked_inputs`
- `gact/elicitation_correlation.py`: `invocation_with_request_correlation`
- `gact/elicitation_forwarding.py`: `relay_forwarded_cancel`, `deliver_forwarded_answer`
- `gact/enrichment.py`: `_notify_block`
- `gact/goal.py`: `_enqueue_goal_redrive`
- `gact/goal_control.py`: `launch_pending_goal`, `maintain_goal_controls`
- `gact/spotter_watcher.py`: `_live_watcher_tasks`
- `tools/foreground_cancellation.py`: `call_limits`
- `tools/mcp_executor.py`: `AsyncMCPToolExecutor.call_tool_result`
- `tools/mcp_extension_registry.py`: `_build_tasks`
- `tools/task_receipt.py`: `record_invalid_result`
- `tools/gateway.py`: `list_relay_tool_definitions`, `list_jarvis_tool_definitions`
- `gact/agents/agent_task_output_digest.py`: `get_agent_task_output_impl`
- `gact/routes/interactions.py`: `_agent_answer_task_projection`
- `gact/storage/download_tool.py`: `connected_data_download`, `build_connected_data_download_tool`
- `gact/storage/connect_tool.py`: `connected_data_connect`
- `gact/action_cards.py`: `_calling_task`
- `gact/context_references.py`: `_resolve_agent_run`
- `gact/context_reference_search.py`: `_agent_run_results`
- `gact/session_descendants.py`: `descendant_walk`, `purge_session_tasks`
- `gact/turn_reasoning.py`: `_parent_turn_reasoning`
- `gact/workflow_step_watch.py`: `watch_step`
- `tools/task_call_context.py`: `require_admission`
- `gact/agents/agent_task_input_refs.py`: `resolve_input_task_evidence`
- `gact/agents/native_presenters_tasks.py`: `_child_session`, `_child_name`
- `gact/agents/spawn_events.py`: `emit_spawn_started`
- `gact/artifacts/versions.py`: `_workspace_single_writer`
- `gact/artifacts/wire.py`: `append_turn_child_resource_links`
- `gact/provenance/child_projection.py`: `_task_index`
- `gact/routes/interaction_surface_projection.py`: `_task_id_for_owner`
- `gact/protocol/v3/event.py`: `_task_path`
- `gact/agents/clio_react_record.py`: `StepRecorder.commit_input`, `StepRecorder.carry_over`
- `tools/builtin_control_host.py`: `builtin_control_bridge`

The static guard runs independently of product imports. A passing guard proves its retired import/symbol/state/config denylist only. It does not prove every remaining policy/caller is removed: the independent removal reviews must inspect actual code and diffs before rebuilding. Product compilation/collection and old public bindings are deliberately not repaired in this commit. No replacement authority, stub or fallback is installed.

Independent algorithm tests retained include `test_shell_server`, `test_shell_output_spill`, `test_shell_workspace_state`, `test_connected_storage_boundary`, `test_connected_storage_adapters`, `test_source_transfer_async_lifecycle`, `test_transfer_progress_persistence` and all sandbox/confinement suites. Old coupled fixtures may require fresh public-contract setup after rebuilding; this is not permission to discard their underlying behaviors.

## Removal-review corrections

The first review's source remains69b19afd; the following are removal corrections, not replacement runtime implementation.

- Deleted the JSON-backed MessageIntentStore and its steer claim/consumption paths. Future-message payload contracts remain data-only; queue behavior must be rebuilt over Core (M07), rather than preserved as another canonical store.
- Deleted the mutable Question map installation, old blocking/async fields, alternate queue answers, forwarded mirrors and dictionary-driven input/admission helpers. Permission/external-input validation and payload types remain; their required arbitration/routing behavior is explicit in P02/P03. The data-only mcp_task_input interaction marker is retained because it describes an external request, not another execution lifecycle.
- Deleted default-executor queue/lock wait calls in the Codex and Claude bridges, without replacing them before this review gate. Their production provider implementations remain; async bridging is required under A05/Q8.
- Restored StepRecorder.carry_over verbatim from5475042f. It is independent general context restoration; its existing recovery tests remain. It does not copy successor transcripts.
- Removed old TurnRunner policy, settlement callback scaffolding and cutoff; retained admission error/value contracts for the fresh conversation owner. Removed residual task-store installation/deletion callbacks and obsolete client claims/accepted-handle maps.
- Preserved actual provider polling inside execute_transfer. This is the actual Globus transfer algorithm executed by a native worker, not a generic Task poller. Deleted blanket SourceStore.recover and its call, the native_request admission hold and generic task mirror fields (task_handle/owner_session_id/invocation_id); the provider-specific native_request payload is retained.
- Preserved ordinary MCP configuration cache invalidation, now named mcp_configuration_revision. Its source refresh path also serves ordinary configured MCP updates. Removed special relay factories/capability projection and federation-only diagnostics.
- Expanded the guard to retired module paths, definitions, relative imports, old store/Question/admission bindings, provider default-pool waits and obsolete configuration expectations. No source alias/fallback exemption was added.
- Deleted additional dedicated relay/invoker/spawn/wait suites and generated fixtures. Retained independent digest/artifact/security tests; coupled setup is not a license to drop their behavior.

Native configuration contract: gact.tasks.{shell,storage}.{url,queue,concurrency} maps to CLIO_TASKS_{SHELL,STORAGE}_{URL,QUEUE,CONCURRENCY}. Default concurrency10 each; memory URLmemory://. Default memory queue clio-<root>-<incarnation>; persistent queue clio-<root>. Explicit queue overrides remain unchanged. No queue identity is reconstructed from a PID.

Removal guard regression cases were added. The first normal pytest invocation failed in the global Core setup because its long Windows IPC path would not bind. The fixture's existing CLIO_TEST_RUNTIME_ROOT=C:/ct-r2 setting let Core start on the next invocation; that case then failed before its test body on the intentionally removed watch_step binding. Neither attempt is a guard-test pass or Tasks acceptance. Both owned run directories were removed by fixture teardown; the old failed daemon and pytest PIDs are absent. No fixture/timeout/guard was disabled.

Standalone removal guard passes. Scoped Ruff check/format pass. Source remains intentionally broken and local; both reviewers must check this corrected removal before rebuilding. The c1 review cache remains manual-only after automatic-review rejection; no retry or absence claim.

The corrected removal also deletes the obsolete loop-inbox buffer, Question-retention and JSON future-message-cap settings and generated descriptions. The new Core pending-only mailbox contract remains unlimited by default. Configuration-note dictionary syntax is checked independently; no broken metadata is required for the deliberate runtime break.

Second-review corrections preserve the Globus native_request payload and its preallocated provider submission ID, restore only plain off-loop first-agent construction, and delete message-deletion/dual-storage cancellation policy. Removed additional imports-only forwarding/Question/intent route shells and the old agent-elicitation dispatch owner; retain pure reply/schema/permission algorithms. Removed old submit/yield policy rather than silently discarding assignment_disposition. The replacement must rebuild that public contract through the conversation owner.

Local-transfer interruption is an explicit migration/native-recovery requirement in W01/N12. SourceStore.recover is not restored as a second task-recovery authority. The typed server_shutdown reason remains a data contract, without a drain loop or hidden cutoff. Historical PendingSteer states remain decoding data only. The second review's c2 cache is manual-only after automatic-review rejection; its command did not run.

Additional retired modules: gact.elicitation_forwarding, gact.routes.session_questions, gact.routes.message_intents, gact.agent_elicitation_dispatch. Their public Question/future-composer/agent-audience requirements remain in P03/A08/M07 and will use the one Core mailbox/conversation engine. No new runtime owner or compatibility fallback was introduced.
