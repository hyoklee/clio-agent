# Independent Claude Code Fable review R35

Core 182cde82; GACT 41660185; marketplace 999fdafa. Committed source, acceptance ledger and correction maps; neutral two-paragraph brief; read-only source review.

I've finished reading the owners, the R35 seams, the GACT load-more path and the regressions. Writing up the verdicts and findings now.

## Verdicts

**Architecture: supported.** The committed source matches the R2 ownership split. `TaskHistory` is a passive writer with rebuildable indexes (`src/clio_agent/gact/task_history.py:60-110`), `Conversations` alone mints and settles assignments (`conversations.py`, `conversation_assignments.py:89-305`), `QuestionCommands` alone decides answer/cancel/expire (`questions.py:33-432`), `TaskOperations.cancel` delegates to the owning backend (`task_runtime.py:113-129`), `publish_task_notice` is the one notice path, and `SessionMail.commit` is the only acknowledgement (`session_mail.py:186-281`). `TurnRunner` is the only admission path and releases the session only after the worker thread exits (`turn_runner.py:98-171, 231-241`). The removal guard denylist is broad (`scripts/check_task_replacement_removal.py`), every removed module in the manifest is absent from `src/`, and I found no copied poller in the native/external owners; their `while True` loops are shield-retry patterns, not status polling (`native_work.py:100-168`). `ask_user` posts through the FastMCP built-in boundary and returns the handle immediately (`task_declarations.py:285-380`, `builtin_boundary.py:47-100`).

**Source: NO-GO for source readiness.** The two R35 corrections are implemented as described, but I found one liveness defect and several robustness gaps listed below. None restores an old owner.

**Qualification: not qualified.** Receipts show static checks only; R34/R35 behavior, final tuple types, F03, legacy test migration, exact-head CI and Q1–Q9/R1–R6 are unexecuted. The R35 receipt states this honestly (`docs/qualification/task-replacement-r35-construction-checks.json`).

## Source findings

- **SessionStart hooks run under the global Core writer lock (medium).** `spawn.create` holds `history.serialized(writing=True)` (`conversation_assignments.py:425`) while `create_child` calls `SessionStore.create`, which runs the lifecycle Core RPC, up to four `sessions.json` flushes, and `dispatch_session_start` (`sessions.py:431-489`). Hook adapters execute configured subprocesses with per-hook timeouts (`hooks/dispatcher.py:6`). A slow SessionStart hook therefore blocks every task read, wait, observe, mail write and Question answer in the process for its full duration. This is the R34 reuse design made worse by R35 adding the hook receipt inside the same critical section.

- **The creation receipt depends on an undocumented threading invariant (low-medium).** The lifecycle observer wraps its Core write in `schedule_off_loop` (`provenance_wiring.py:93`), which runs inline only when the calling thread has no running loop and otherwise dispatches to an executor and merely logs failures (`off_loop.py:97-111`). `SessionStore.create` marks `creation_lifecycle_confirmed=True` as soon as the observer returns (`sessions.py:441-448`). Today the trusted path always arrives via `asyncio.to_thread`, so it is inline, but nothing asserts this for `creation_digest` rows. A future loop-thread caller would confirm creation before, or despite failure of, the Core write. Suggest the observer refuse or force inline execution when `session.creation_digest` is set.

- **A `started` hook receipt is permanently dead (low, design gap).** `sessions.py:462-466` raises for that creation ID forever; no route, control or migration can record human inspection, and no doc mentions the state (grep in `docs/` finds nothing). The model's only escape is a new invocation, which leaves an orphan child row with no assignment. Consistent with "not replayed", but worth a documented operator path.

- **Full input scan on every child creation (low).** `_new_assignment` calls `history.recovery_input(parent.handle)` (`conversation_assignments.py:117`), which scans all committed inputs across sessions under the writer lock; its own docstring says "never during hot reads" (`task_history.py:345-361`). Relevant to F03.

- **Trigger inclusion is not enforced at commit (low).** `commit_input` writes the human head to context (`clio_react_record.py:381`) and relies on `stage(collected=(identity,))` to include it; `SessionMail.stage` can `break` on budget before reaching the trigger if an earlier-ordered item became eligible after admission (`session_mail.py:125-127`). Nothing asserts the trigger is in `staged.items`, so the head could enter context unacknowledged and be redelivered. Edge case; an assertion would close it.

- **Waits return immediately on pre-existing uncertainty (low-medium, design).** `task_operations.py:314-316` ends any wait when a member has `task_state_uncertain` or any `attention_episode`, even `return_when="all"`. An agent following the prompt's "continue waiting when that answer is required" will spin through immediate returns until the episode clears. This matches the plan's literal `wait_tasks` wording but not its "no endless receipt spin" intent. Returning early only when uncertainty changed since the wait began would keep both.

- **Pattern observation short-circuits on one unavailable member (low).** `read_observations` sets `any_settled=True` for every unauthorized handle on every page (`task_observations.py:68-77`), so `observe(pattern=...)` over a mixed list returns immediately each call (`task_operations.py:461-471`).

- **Child reuse still rewrites approval mode (low).** On reuse, `spawn.create` re-applies `approval_mode="ask"` whenever `approval_profile` is given (`conversation_assignments.py:487-490`), contrary to R35's "human edits are preserved".

- **Legacy tests still import retired owners.** A narrow grep finds 13 test modules (18 imports) of removed modules; the ledger counts 39. These fail at collection and block Z02, as already recorded.

Intersession messaging and shared controls otherwise hold up: peer mail re-authorizes the sender at staging time (`session_mail.py:363-394`), subscriptions require read plus observe (`task_operations.py:518-571`), human grants are authenticated and revocation is monotonic (`routes/tasks.py:416-488`, `task_history.py:460-477`), and explicit collection commits through the same recipient-input record as automatic delivery (`session_mail.py:283-361`).

## GACT and regression quality

The load-more correction is correct and minimal. `loadMore` now calls `fetchNextPage({ throwOnError: true })` (`use-session-observability.ts:40-44`); `TaskPageContinuation` catches, renders a `role="alert"` and keeps loaded rows (`async-task-list.tsx:30-57`); the controls are forwarded unchanged through `use-workspace-data.ts:502,649`, `observability-dock.tsx:335,373`, `observability-work.tsx:98` and the evidence views. The same error may also appear in the dock's section state; harmless. Query and cancel decoding in `task-repository.ts` is strict and reports per-handle failures.

Regressions are real-Core and production-path tests, not doubles. `test_child_creation_recovery.py` covers five fault points times store reconstruction plus two hook-receipt faults, asserts exactly one `session.created` event and one hook call, and checks the wire hides receipts. `test_wait_disclosure_contracts.py` drives the actual tool declarations and `StepRecorder` across running/uncertain/completed and revocation. `test_question_collection_recovery.py` injects a crash between observation and input commit. The GACT hook test uses a real QueryClient with a rejected second page and a successful retry. Gaps: no case exercises the lifecycle observer from a loop thread, nothing covers two same-invocation spawns racing, and the removal guard has a single regression case (`tests/test_tools/test_task_removal_guard.py`).
