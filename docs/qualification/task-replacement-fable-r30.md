# Independent Claude Code Fable review R30

Core cf583134; GACT 30df56ed. Committed source, acceptance ledger and correction maps; neutral two-paragraph brief; read-only source review.

**Verdict.** The committed source is a faithful, coherent rebuild of the replacement architecture, and I would give it a source **GO on architecture**. I give it a **NO-GO for candidate freeze** on source alone, because of one unbounded-growth defect that undermines F03, one shutdown-path defect, and two narrower correctness issues listed below. I ran nothing: no tests, no guard, no services. Every ledger row that depends on execution remains unverified by this review.

## What the source does faithfully

- **One typed record.** `TaskSnapshot` covers all seven kinds with immutable identity and custody validation at `src/clio_agent/arc/task_types.py:134-261`. Migration and replay are the only callers of the historical decoder, and the guard enforces that at `scripts/check_task_replacement_removal.py:251-264`.
- **One confirmed writer, passive indexes.** `TaskHistory` writes content first, then the authoritative event, then the index (`task_history.py:191-236`). Replay rebuilds everything from events and repairs indexes (`task_history_projection.py:167-321`). Any writer failure holds new durable admission until a successful restore (`task_history.py:747-789`, `core_recovery.py:40-73`).
- **Sessions as addressable assignments.** `spawn` persists the child assignment and delegation mail before any child inference (`conversation_assignments.py:349-531`). Completion mints no successor; a later eligible arrival creates a linked one with the predecessor's fixed context (`conversations.py:290-307`, `conversation_assignments.py:86-185`). Restart refuses to launch on uncertain settlement (`conversation_controls.py:376-398`). The latest-assignment index never retargets a known handle (`task_history_projection.py:351-353`).
- **Cross-session observation and messaging.** Rights are tree lineage plus human grants only, rechecked at staging and again at commit (`task_access.py:73-96`, `session_mail.py:228-252`, `292-323`). Observe-only views redact description and output (`task_access.py:197-217`). Subscriptions need read plus observe and cannot consume the owner's notice (`task_operations.py:421-466`, `task_publication.py:52-63`). The delegation grant conveys only the reply channel (`conversation_assignments.py:476-492`).
- **Asynchronous Questions through the shared wait.** `ask_user` posts a durable handle and returns (`task_declarations.py:260-358`). `wait_tasks` and `get_task_result` collect through `_collected`, and the collection is acknowledged only by the recipient-input commit of the real tool observation (`task_declarations.py:53-76`, `agents/clio_react_record.py:664-702`, `session_mail.py:272-290`). Answer and expiry arbitrate under one lock (`questions.py:284-379`).
- **Recovery, SDK adapter, shutdown.** Pending-only backoff at 1, 2, 4 up to 30 seconds with no empty-queue worker (`core_recovery.py:63-102`). The adapter intercepts only `ClientCreateTaskResult`, shields adoption across cancellation, and never repeats `tools/call` (`tools/task_client.py:271-345`). Shutdown closes admission and awaits worker exit without a cutoff (`turn_runner.py:275-313`).
- **UI and prompts.** The cancel confirmation warns about descendants (`external/gact-tui/web/src/routes/runs-page.tsx:711`); the runtime prompt pack explains yield, wake and uncertainty (`prompt_packs/builtin/runtime/clio.runtime.tasks.md`).

## Findings

1. **Blocking, F03: every short built-in call writes a permanent submission record.** `builtin_boundary.py:143-170` records a `SubmissionContext` for each `query_tasks`, `wait_tasks`, `ask_user` or memory-tool call. `task_history.py:260-273` indexes it forever, replay reloads it (`task_history_projection.py:392-393`), and `_repair_indexes` rewrites it on every boot (`task_history_projection.py:307-311`). Inline MCP calls likewise create a full task row and submission per call (`external_tasks.py:337-383`). Startup replay and memory now grow with the lifetime count of tool calls, not with retained tasks. The ledger's F03 measurement covered retained tasks only. Either bound these records or measure replay under realistic tool-call volume before freeze.

2. **Blocking, shutdown: a lingering built-in invocation aborts the rest of close.** `builtin_boundary.py:103-108` raises if any invocation remains. `task_runtime.py:391-415` calls the exit stack without a `finally`, so that raise skips external-client close, recovery drain and the observation hook reset. `run_workflow` runs as one invocation for the whole workflow (`task_declarations.py:673-678`), so a long declared run is the likely trigger. This is an N15 regression risk; wrap the remaining close steps.

3. **Correctness: a segment that finishes after a context clear is silently dropped.** `conversation_assignments.py:209-210` returns early on an epoch mismatch, leaving activity at `busy` from `conversations.py:628` with no worker and discarding the model's output. `clear_model_context` requests a stop first (`conversation_assignments.py:69`), so the window is narrow, but the stale status is visible to the UI.

4. **Decide: Stop before the first commit is undone by any later arrival.** `conversations.py:257-274` flips `stopped_before_input_commit` items back to eligible whenever another eligible item appears, and the stopped message becomes the trigger text at line 278. A human who stops message A and sends B gets A re-run with B attached; a peer message or task result also revives A. R30 holds only veto and setup failures this way, so this may be intended, but it should be an explicit decision.

Non-blocking:

- **One process-wide lock around Core I/O.** `serialized()` and `_writing()` hold the same RLock during segment reads and appends (`task_history.py:143-155`, `748-756`). Every owner, wait loop and route contends on it, and `spawn` resolves blueprints under it (`conversation_assignments.py:427-431`). Q8 should measure this.
- **Residual polling.** `tool_dispatch.py:46-48` still polls thread liveness every 5 ms for each synchronous built-in, and `call_on_application` polls a future at 100 ms. R26 removed this only from `TurnRunner.run_sync`.
- **Small leaks.** `Conversations._control_holds` is never cleared (`conversation_controls.py:300, 341`); fanout semaphores accumulate per parent (`conversations.py:554`).
- **Subscriber rights assume the owner's human.** `task_publication.py:53-59` and `task_runtime.py:346-351` evaluate subscribers with the task owner's human id. Correct for today's single-human product, but it would silently widen tree rights in a multi-human deployment.
- **Migration runs fully on every boot** (`task_runtime.py:40`, `task_migration.py:68-78`), a second complete event pass on top of replay. Include it in the F03 startup measurement.
- **Unchecked session lookup** at `external_tasks.py:335-336` raises `AttributeError` instead of a typed error.
- **Maintainability.** `Conversations` is one owner split across four modules that mutate its private state through free functions. It is cohesive, but it reads as one large class.

## What I did not verify

I did not execute the 112 fresh test functions in `tests/test_arc`, the removal guard, lint, or types. I did not verify the pinned SDK private hooks (`_resolve_claimed_result`, `TransportOptions.session_class`) against the installed FastMCP 4.1.0. I reviewed only the first part of `hooks/turn_approval.py` and only the repository, schema and runs-page slices of GACT. The ledger itself records Q1 to Q9, R1 to R6, F03, CI and legacy test migration as outstanding; nothing here changes that.

**Recommendation.** Fix findings 1 and 2, decide finding 4, patch finding 3, then run the constructed checks and the live matrix. The architecture does not need another revision.
