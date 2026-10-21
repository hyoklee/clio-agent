**R2 is a better architecture, but I would not approve the current implementation yet.** I reviewed [task-replacement-plan.md](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md) against core `057b93bd`.

The simplification is real: the old task registry, supervisor, custom MCP driving loops, forwarded-child lifecycle writers, and competing wake paths are removed. The proposed ownership is clearer: native systems execute work; Core records observations and mail; the conversation engine owns assignments and model admission. I would keep that design.

Three implementation findings need attention:

1. **[P1] MCP App messages call a removed API parameter.**
   [mcp_app_routes.py:213](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/mcp_app_routes.py:213) passes `internal_model_text`, but [accept_message_async:615](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/message_submission.py:615) no longer accepts it. These messages fail before acceptance. Fixing this must also preserve the app’s model context; simply deleting the argument would lose it.

2. **[P1] Messages arriving during a turn can lose their attachments while being acknowledged as delivered.**
   [turn.py:748](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn.py:748) places text and metadata in the mailbox, without the typed message parts. [session_mail.py:82](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:82) renders that payload as JSON. Only the turn’s initial human message receives the enriched, typed replacement in [clio_react_record.py:424](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:424). Later arrivals can therefore commit without their image payloads or enriched reference content. The same accepted input needs to reach the model whether it arrives while idle, busy, or recovering.

3. **[P2] Goal dependencies accept aliases but subsequently cannot resolve them.**
   [conversations.py:348](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:348) authorizes through alias resolution, then stores the original strings. Later dependency checks use canonical-only snapshot lookups. A valid historical alias can leave the goal waiting indefinitely; an alias also bypasses the direct self-dependency check. Store the resolved handles before checking and recording dependencies.

My main recommendation is to **finish the existing boundaries rather than add more machinery**. These defects need ordinary integration fixes within the current owners. Tighten the existing attachment/input acceptance cases to cover busy arrivals, multiple queued inputs, MCP App context, and recovery.

This was a read-only source review. I ran no tests or services; the fresh Q1–Q9/R1–R6 runtime acceptance remains outstanding.

On your earlier question: **compaction summarizes older chat context when the conversation approaches its context limit.** That is why checking the actual files remains important after a long conversation. [Official documentation](https://learn.chatgpt.com/docs/changelog#new-in-codex-cli)
