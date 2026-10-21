**Approved as a batching policy**, with these constraints:

- Allow one oversized, indivisible human input **only when it is the sole newly rendered mailbox item**. Count the initial `_mail_head` too; it must not become a separate exemption. Leave all remaining human and automatic mail pending.
- Never truncate base64 or partially acknowledge a message.
- Keep explicit collection acknowledgements independent when their content is already represented by a durable tool observation. That content still counts toward request-level limits.
- Preserve final revision, withdrawal, eligibility, and authorization checks before commitment.

Reuse [check_block_bytes and check_total_bytes](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/providers/native_attachment_bounds.py:121). The aggregate bound applies to **the complete request’s attachments**, including retained history—not merely the newly admitted item. Existing provider consumers include [Codex wire validation](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/providers/codex/wire_validation.py:13).

Those are media-byte bounds, not proof that the complete prompt fits the model’s context window. Preserve existing context-limit handling and describe this accurately as a notification-batching exception.

This resolves my policy objection; implementation and runtime verification remain outstanding.
