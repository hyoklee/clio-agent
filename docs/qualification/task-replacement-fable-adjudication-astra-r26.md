# Astra adjudication of the independent Fable review

Frozen source: core `14cd98be` / GACT `ce993164`. Read-only source review; the current corrections were not accepted by this report.

**Fable’s “not release-ready” verdict is justified. Its case for another architectural replacement is not.** I checked frozen core `14cd98be` and GACT `ce993164` against R2. The ownership split remains defensible; the implementation needs concrete corrections and tighter boundaries.

The consequential findings are:

- **Recovery can block unrelated repairs.** [CoreRecovery awaits callbacks serially](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/core_recovery.py:72), while [native reconnection awaits an unbounded ping](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:565). The installed SDK matches the pinned versions and supplies no default request deadline here. Bound transport health checks while preserving accepted work and actual cleanup.
- **The indexing criticism has substance.** Persisted indexes are written and checked during repair, but hot reads use reconstructed memory projections. More concretely, [query constructs the whole authorized candidate set before applying an exact handle or active filter](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:87); [authorization also constructs the retained task tree](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_access.py:31). That undermines the bounded-read requirement. Fix those paths and demonstrate F03 before adding storage machinery.
- **The GACT integration defects are real.** The action-card client calls the removed singular task route, and the compatibility list [returns raw activity values](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/tasks.py:232) that its decoder does not recognize. These need one consistent public projection.
- **The 5 ms thread polling is real.** [TurnRunner polls throughout each synchronous turn](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn_runner.py:196). Replace that with completion notification while retaining proof that the thread actually retired.

Two structural cleanups are warranted. First, owners should use explicit history operations instead of reaching broadly into private dictionaries and locks. Second, [CLIO-owned status/activity/settlement fields need defined vocabularies](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/arc/task_types.py:106) and validation at the write boundary. Raw backend status can remain open-ended. Neither change requires a universal lifecycle machine.

Several Fable claims need correction:

- The acceptance ledger **exists**; its omission was a review-packaging error.
- Startup replay and one pending recovery coroutine are explicitly permitted by R2.
- Reconnect callbacks **do return `True`** when observation becomes fresh, work terminates, or resources close. There is a narrower problem: [lost stdio connections repeatedly retry a path that explicitly cannot reconnect](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/external_tasks.py:549).
- Replacing a callback under the same key is not, by itself, proof of lost required evidence. Latest-observation coalescing can be correct; distinct decisions must remain separately retained.
- Shared locking does not establish multiple authorities. The writer also enforces durability ordering and record invariants.
- “No schema at all” and “split purely to spread line counts” overstate what the source establishes.

**Keep the architecture, but require these boundary and hot-path corrections before approval.** My previous migration/context-epoch, startup-recovery, and primary-agent context-restoration findings also remain applicable to this frozen commit. I have not assessed the patches currently being made in the worktree or claimed runtime qualification; this review was read-only.
