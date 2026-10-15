Reviewed R36 at core `35a2aa0`, GACT `41660185`, marketplace `999fdafa`.

**Architecture: GO. Source: NO-GO for one remaining recovery defect. Qualification: pending.**

**[P2] Creation recovery searches only the first event chunk.**
[provenance_wiring.py:66](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/provenance_wiring.py:66) searches `arc.list_segments(session_id, "_events")`, which reads one scope. ARC rolls subsequent events into additional chunks.

R36 performs turn preparation before publishing `session.created`. With a small configured chunk size, that creation event lands in a later chunk. If publication succeeds but its reply is lost, initialization retry misses the durable event and publishes another, repeating semantic-event hooks and provenance fanout.

Use the existing chunk-aware event reader. Extend the recovery regression with a small chunk capacity, publication followed by a lost reply, and both same-process and reconstructed-store recovery. Count events across the complete lane and assert fanout occurs once. The [current assertion](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/tests/test_arc/test_child_startup_contracts.py:205) also reads only `_events`, so it does not cover this case.

The three previous findings are addressed **in source**:

- Startup runs on the existing session worker, outside the global task-writer lock. Admission and cancellation are checked around initialization.
- Timed workflows persist their prepared absolute deadline before child creation.
- Reusing a child preserves its human-edited approval mode while validating immutable creation settings.

The broader architecture remains consistent with R2:

| Area | Assessment |
|---|---|
| Stable sessions, finite assignments | Session identity survives yielding and recovery; later eligible work gets a linked assignment without retargeting historical handles. |
| Intersession/workflow messaging | Shared mail and explicit grants remain the delivery boundary. The new workflow recovery tests do **not** establish communication between two independent workflows; Q5 remains necessary. |
| Observation and waits | Shared reads/waits preserve independent member errors, permission checks, and ongoing work after waiter timeout or cancellation. |
| Async Questions | QuestionCommands retains decision ownership; asking returns a durable Question without occupying a native task worker. |
| Lifecycle and permissions | Startup uses the existing execution owner. Unconfirmed SessionStart effects remain explicit uncertainty, preventing automatic replay. |
| Removal and maintainability | The old AgentTaskRegistry/CoreTaskJournal/TaskSupervisor/NativeTaskHost production machinery remains removed. R36 adds no replacement scheduler or execution registry. |

The new regressions use meaningful production boundaries—Core, SessionStore, TurnRunner and recorder—with test-only model/hook faults. Their limits still matter: the concurrency case exercises reuse during active startup, rather than two simultaneous first submissions; these tests also do not establish provider, subprocess, or UI behavior.

For the concern about an overdone implementation, **I would keep this architecture and make the narrow correction above**. Global input-recovery scans and whole-session-file writes still need F03 measurements; there is no evidence here justifying another coordinator, cache, or recovery subsystem.

The recorded scoped lint/type/removal/size checks passed, but behavioral tests remain unexecuted. Legacy-test migration, F03, exact-head CI, and Q1–Q9/R1–R6 remain outstanding. I made no edits, ran no tests or services, and did not use the D qualification checkout.
