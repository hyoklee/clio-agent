# Independent Claude Code Fable review R34

Core 47380c05; GACT 07745d5b; marketplace 999fdafa. Committed source, acceptance ledger and correction maps; neutral two-paragraph brief; read-only source review.

Memory saving is not possible here: no write tool is exposed in this read-only session, so I am skipping it and delivering the review.

# Independent review: CLIO task replacement, R34 candidate

Reviewed core `47380c05`, GACT `07745d5b`, marketplace `999fdafa` against the R2 plan and acceptance ledger. Read-only. No tests, services or models were run.

## Verdicts

| Area | Verdict | Summary |
| --- | --- | --- |
| Architecture | **Accept** | Matches the R2 contract. One typed snapshot, one Core writer, passive indexes, owner-separated transitions, Questions through shared controls, no driver or scheduler restored. |
| Source | **Not release-ready, no blocker found in the R34 corrections** | All six R34 corrections are implemented where the map says. Two medium semantic defects and several low issues remain. |
| Qualification | **Blocked, honestly reported** | R34 behavior cases unexecuted, final type checks not on the committed head, TypeScript pending, Q1–Q9 and R1–R6 untouched. |

## Architecture

The committed sources implement the ownership split the plan requires.

- **One representation.** `TaskSnapshot` in `src/clio_agent/arc/task_types.py:134` covers all seven kinds, with immutable identity and custody checks in `validate_identity` and `validate_custody`. Missing legacy descriptions stay explicit.
- **One writer.** `TaskHistory` in `src/clio_agent/gact/task_history.py:60` is the only Core writer. Content is written before references, index writes follow the semantic event, and a failed write raises the recovery hold rather than rolling anything back. Indexes are rebuilt from history in `task_history_projection.restore`.
- **Owners decide transitions.** The conversation engine alone settles assignments (`conversation_assignments._finish_segment`), `QuestionCommands` alone answers or cancels Questions, native and external owners publish observations, and `TaskOperations` only reads, waits, subscribes and delegates cancellation to the owner.
- **Delivery acknowledgement is single.** `SessionMail.commit` at `session_mail.py:186` records the sole `RecipientInput`. Query and observe return `collect=False` results that never acknowledge. Explicit collection and automatic delivery share that boundary through `StepRecorder.commit_input`.
- **Removal.** The guard in `scripts/check_task_replacement_removal.py` denies every module in the plan inventory, retired symbols, state attributes and configuration keys, with no compatibility exemption. The only historical exemption is the `user_questions` string in `task_migration.py`, and `tests/test_tools/test_task_removal_guard.py` proves attribute use is still rejected. Shipped aliases in `task_declarations.build_task_compatibility_tools` are pure delegates.

Two architectural notes, neither a defect against the plan:

- Every retained task, mail item and recipient input lives in process memory after replay. The plan permits full-history replay pending the F03 measurement, but there is no bound on index growth for long-lived installs.
- `TaskAccess.rights` takes the writer lock on each call and is invoked per candidate row inside query and observe loops. Contention is unmeasured.

## Source findings

**R34 corrections verified in code**

| Correction | Location | Regression |
| --- | --- | --- |
| Typed disclosure denial no longer fails the assignment | `agents/clio_react_record.py:427`, `:621` | `tests/test_arc/test_conversation_disclosure_survival.py` runs the real runner and owner |
| Wait keeps per-member read/observe requirements | `task_operations.py:60`, `task_declarations.py:428` | `tests/test_arc/test_wait_disclosure_contracts.py`, twelve cases |
| Runs no longer calls a partial workflow completed | `external/gact-tui/web/src/routes/runs-page.tsx:223` | recorded and historical cases in the runs contract test |
| Compatibility pages keep cursors, pending Questions selected before paging | `routes/tasks.py:242`, `:330`; `packages/core/src/v3/session-observability-repository.ts:239` | `tests/test_arc/test_task_projection_pages.py`, `task-projection-pages.test.ts`, `task-page-continuation.test.tsx` |
| Failed child creation reuses the session address | `conversation_assignments.py:424`, `sessions.py:376`, `task_runtime.py:134` | `tests/test_arc/test_child_creation_recovery.py`, four fault points |
| Question guidance separates Question and assignment outcomes | `factorio-flat/.../references/task-lifecycle.md:19` | `marketplace/tests/test_native_orchestration_prompt_contract.py:35` |

**Medium**

- **A Stop before input commit is undone by any later eligible arrival.** `conversations.py:270` releases every input held as `stopped_before_input_commit` whenever another eligible item exists, including a background task result or peer message. The same item is offered for explicit retry by `session_input.capture_retry_input`. So a human who pressed Stop can see that message run later without acting, which contradicts the plan's rule that other wake signals cannot retry a held input. Release should require a human or composer arrival, or the explicit retry path only.
- **`wait_tasks(return_when="any")` returns on an error row.** `task_operations.py:315` treats `task_unavailable` and `cannot_wait_for_own_active_assignment` outcomes as satisfying "any", so a list with one bad handle returns immediately with every real member still pending and `timed_out: False`. The prompt tells models invalid members do not affect others, but a model will read this as settlement. Error rows should not count toward the any-condition.

**Low**

- The SessionStart hook is never dispatched for a trusted child whose lifecycle observation failed once. `sessions.py:428` keeps the session and re-raises, and the reuse path returns before the hook. The test at `test_child_creation_recovery.py:106` encodes this as expected.
- `run_workflow` passes its result through `_collected`, which drops observe metadata for pending handles and step task IDs. Own-tree rights make this harmless today.
- GACT Work and Observability load only active tasks at `web/src/hooks/use-session-observability.ts:35`. Terminal children that are not in live transcript entities disappear after reload and exist only in Runs. This may be intended compaction but it is not stated anywhere.
- Cosmetic: duplicate `TASK_CALL` import in `task_declarations.py:179`, local `logging` import in `conversations.py:140`.

Checked and found correct: tree scoping never grants ancestor or sibling rights; exact-handle grants do not reach successors; subscriptions require read and observe and cannot consume owner delivery; attention and final notices have distinct identities; Question expiry and answers arbitrate under the writer lock; restart refuses to launch on uncertain settlement; `TurnRunner` releases the slot only after physical worker exit.

## Qualification

The ledger and the R34 construction receipt are accurate about what was not done.

- No R34 behavioral case has executed. The twenty-six R33 passes in `task-replacement-r33-component-checks.json` are against core `24e7dfbb`, not this head.
- The receipt states Linux Mypy passed nine files before the final trusted-session retention change, so the committed head has no complete type check. TypeScript is recorded as pending.
- F03, exact-head CI, legacy test migration, Q1–Q9, R1–R6, migration idempotence and all live families remain blocked. Nothing here authorizes a release.

The regressions themselves are of good quality. They use real Core, the production owners and the actual runner, inject faults at write boundaries, and assert non-disclosure by content rather than by status codes.

## What to do next

1. Decide the Stop-release semantics and adjust `conversations.py:270` with a regression that a task result alone does not re-admit a stopped human input.
2. Exclude error rows from the any-wait condition and add a mixed-member case to `test_wait_disclosure_contracts.py`.
3. Run the constructed R34 cases and the full type checks on `47380c05` before renewing the source reviews.
