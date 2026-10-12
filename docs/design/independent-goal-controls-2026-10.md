# Independent goal, loop and schedule controls

The goal controller owns pursuit of an observable objective, not an iteration
counter or timer. Setting a goal starts work immediately. Each completed turn
receives an independent completion check and actionable next-step guidance.
An unmet objective continues; the agent can revise its plan and tools. Explicit
human limits and stops take precedence, while omitted limits are unlimited.

The judge receives bounded recent conversation/tool evidence and a retained,
bounded progress ledger. It cannot execute tools or alter workspace state. A
failed judge pauses the objective rather than continuing without a completion
check. A decision requiring human input parks it; ten identical final responses
stop stalled continuation. Completion is judged evidence, not proof of scientific
correctness.

Loops monitor changing state at intervals. Schedules run instructions at a
future instant or calendar occurrence. Both are independent of the goal: goal
completion never cancels monitoring, and a stopped loop never stops the goal.
All use the existing single-turn admission path and retained session state.

Automatic goal judgments, loop wakes, scheduled wakes and task completions are
recorded as typed harness injections with algorithm authorship. They resume the
existing assignment without impersonating another human prompt. Transcript
clients render them in sequence without a user header or user actions; exact
injected text remains available. Older envelopes are projected using their
reserved controller metadata, rather than interpreting arbitrary human text.

`wait_for` parks an active goal on owned durable task handles. Accepted work
is neither collected nor resubmitted by waiting. The existing task completion
mailbox delivers terminal results and resumes the owner. `all` retains partial
results until all selected tasks settle; `any` resumes after the first.
`wait_tasks` remains the blocking tool for waiting inside an active turn.

On backend restart, retained goals inspect task outcomes and workspace state
before replanning. A pending durable loop wake remains; an interrupted in-flight
loop stops explicitly. This is recovery of control state, not replay or rollback
of arbitrary external operations.

Fleet independently selects judges for goals, variants/refinement, and permission
risk, each inheriting the conversation model. Explicit selections resolve the
chosen provider's own configuration. Permission review classifies none/low/medium/high;
high and unavailable reviews escalate to the user. Existing denials and sandbox
boundaries remain authoritative.

## Research informing the implementation

- [Microsoft Magentic-One](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html)
  maintains task/progress ledgers, checks completion, and revises its plan when
  progress stalls. CLIO adopts explicit progress and next-step evaluation without
  making multi-agent delegation a prerequisite for a goal.
- [Anthropic's long-running harness guidance](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  emphasizes incremental progress, verification and durable handoff across context
  windows. CLIO retains judged progress and concrete output references.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  separates resumable execution state from transient model context. CLIO reuses
  its existing durable session, schedule and task stores, rather than adding a
  separate workflow database or claiming arbitrary tool calls are replay-safe.

These references informed design. CLIO's qualification uses its own production
routes, real model/tool calls and process restarts; it does not infer CLIO behavior
from another framework's capabilities.
