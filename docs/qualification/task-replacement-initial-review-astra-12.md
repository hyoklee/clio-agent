**NO-GO for initial source qualification** at core `f029d12b`, GACT `ce993164`, marketplace `9257bba`. Three actionable findings remain:

1. **[P1] Automatic queue promotion can start work after Stop.**
   [routes/mailbox.py:92](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/mailbox.py:92) rechecks the item and workspace after preflight, but not composer suspension. In a new session, Stop during preflight finds no assignment, pauses the composer queue, and returns without stopping the reserved runner ([session_cancellation.py:23](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/session_cancellation.py:23)). Promotion can then create the assignment and launch it. Recheck automatic-promotion eligibility before committing; Stop must also reach a reservation that has no assignment yet.

2. **[P2] Busy delivery rejects accepted evidence snapshots that idle delivery preserves.**
   [messaging.py:581](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/messaging.py:581) reruns admission authorization with strict revision enforcement. An accepted `context_frame` or other evidence reference whose state changes before the next iteration raises `context_ref_stale`, aborting input commitment. Idle delivery already handles this through the recorded-snapshot path in [context_reference_delivery.py:103](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/context_reference_delivery.py:103). Reuse that delivery behavior while retaining ownership/access checks.

3. **[P2] Typed rendering bypasses the mailbox’s batch bound.**
   [session_mail.py:83](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:83) budgets only ordinary text. [clio_react_record.py:429](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:429) subsequently replaces that bounded text with full enriched content and media, without rebudgeting. Several short queued messages with large attachments/references can therefore be acknowledged together and overflow the model input. Apply batching to the rendered input and leave excess messages pending.

The previous API-argument, dependency-alias, capability-composition, Question-event, and duplicate-route defects are corrected in source. Typed Core persistence, deletion/rollback withdrawal, and off-lock preparation are present; mailbox commit rechecks revisions, withdrawal, eligibility, and peer authorization. I traced the SDK hook through the installed FastMCP 4.1.0/MCP 2.0.0 source.

Claude11’s seven principal findings were checked. Its lower-priority text-only idempotency comparison remains unchanged at [message_submission.py:566](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/message_submission.py:566).

No edits, tests, imports, services, or runtime probes were performed. **Q1–Q9/R1–R6 acceptance remains separate and unverified.**
