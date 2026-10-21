**Approved as a data-access boundary.** Reusing `get_task_result` for a snapshot already committed to the child’s input avoids another reader tool or task-rights mechanism.

Make these details binding:

1. **A pin alone is insufficient.** Verify that the exact pin was included in a confirmed recipient-input record for this child session. Recheck the parent’s ownership/read authorization at that commitment. Successors may inherit the same references and original commitment proof within that stable session; other descendants and peers do not inherit them.

2. **Keep normal results and shared evidence distinguishable.** Return a host-produced discriminator such as `result_kind="shared_evidence"`. Its status, owner and terminal time describe the captured snapshot—not the source’s current state. Leave `TaskAccess` and query/observe/wait/message/control authorization unchanged. Only the authorization-resolution failure permits checking pins; content corruption or storage failures must not trigger fallback.

3. **Bind pagination to the selected read mode and snapshot.** Include recipient, source handle, exact pin/reference identity, digest, serialization version and offset. Once pagination starts, subsequent pages must not switch to the current result because permissions or source metadata changed. Handoff instructions should supply the pinned continuation cursor. Treat cursors as addresses, never authorization: validate the committed pin on every page.

4. **Make pages reconstructable.** Use deterministic JSON serialization and explicit chunk/offset/continuation fields. Do not imply that each fragment is independently parseable JSON. Preserve existing unpaginated behavior for results that fit.

5. **Exclude evidence reads from source completion collection.** The host-produced discriminator must bypass both source-notice publication and notification-ID collection. Never infer this from fields inside the stored evidence. Record the read as an ordinary tool observation in the child’s context.

That last distinction is essential: today `_collected` treats any terminal result handle as collectible and reauthorizes it against the source task. [Current collection boundary](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:53)

Once committed, this is retained shared content. Revoking a separate sibling-task grant must not silently change the pinned bytes; it still removes ordinary task access.

The focused checks should cover uncommitted/forged pins, cross-session cursors, successor recovery, permission changes between pages, source changes, exact reconstruction, and **zero source completion acknowledgements**.

No architectural objection remains to this approach. Implementation and runtime verification remain outstanding.
