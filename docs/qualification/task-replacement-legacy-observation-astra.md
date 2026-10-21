**Approve the epoch migration and reference handoff. A row limit alone is insufficient: shared pagination and pattern waiting need the following guarantees in this slice.** No old SSE curator, index, or driver needs restoring.

1. **Make the observation migration explicit.**
   `cursor=1` starts the Core observation epoch with `legacy_history_unavailable`. Numeric resumes greater than 1 without provenance return `legacy_observation_history_unavailable`, without resetting. Returned string cursors resume Core observation. Declare the integer/string schema and document that `limit` now counts changed task rows, not historical SSE events. This is an honest migration boundary, not identical event-stream compatibility.

2. **Do not advance past undisclosed data.**
   Keep the previous position for every row omitted by `row_limit`, and return `has_more`. Also preserve continuation within truncated output: the current implementation advances `outputs[handle]` to the newest chunk even when older chunks were omitted. Row pagination alone does not fix that. Use continuation data in the existing opaque cursor, with aggregate output bounds—no separate mutable cursor store. [Current output traversal](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:349)

3. **Drain available pages before waiting for another event.**
   Otherwise, with `limit=1`, a match already present in the second task can remain stranded behind the first task indefinitely. Put that progression inside shared `observe`, not the adapter. A successful pattern match must identify authorized evidence returned in that response. Currently the regex searches the entire serialized task row, so a matching assignment description or metadata can satisfy it without matching new output. [Current pattern waiter](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:290)

4. **Keep `include_state` truthful.**
   It controls the available typed workflow-state projection, subject to read rights. Do not present an ordinary `TaskSnapshot` status as recovered workflow state. Missing historical state should be explicitly unavailable.

**The proposed `input_task_ids` preparation is the correct boundary**, with these requirements:

- Validate all references before creating that child; a failed fanout member does not prevent valid siblings.
- Pin the exact result references and provenance, and include them in invocation-consistency checks. Reusing an invocation with different evidence must fail.
- Recheck authorization before committing the child input.
- Preserve bounded rendering, explicit partial markers, and recovery from the committed references.
- Ensure the child can retrieve omitted attachment content through an authorized content path. A reference that requires forbidden sibling-task access is not a usable handoff. Do not solve that by granting sibling rights.

Shared single/fanout preparation, blueprint resolution, retained `spawns`, local placement, and explicit relay rejection are approved.

The focused checks should cover: a match beyond the first page; output exceeding the character bound; resume without a new producer event; metadata-only false matches; stale numeric cursors; and handoff revocation or changed evidence before commitment.

This is an implementation-boundary decision, not runtime acceptance.
