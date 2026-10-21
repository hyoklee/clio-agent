# Provider recovery architecture clarification

Read-only source decision from the existing Review task architecture plan chat. It does not accept the implementation or close acceptance row A6.

**Yes—a host-only native continuation is a valid solution.** It creates a new local execution leg for the **same verified provider job and public Download handle**. FastMCP/Docket still owns execution; the existing transfer algorithm owns provider interaction. No transfer scheduler is needed.

The smallest valid contract is:

1. **Require proven identity and custody.**  
   Reattachment requires the retained `native_job_id`, operation ID, original submission/context reference, owning principal, source/destination identity and approved paths. Revalidate current authorization. A saved `native_request` or provider submission ID without a verified job ID is insufficient for this automatic path.

2. **Make provider submission structurally unreachable.**  
   Extract a `poll_existing_job` operation that requires a nonempty job ID and cannot call `submit`. The current [`GlobusSource.poll()`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/storage/globus.py:240) explicitly falls back to submission. A caller-side check alone is weaker than separating that operation. Normal downloads can perform submission first, then use the same existing-job algorithm.

3. **Record the continuation through existing Core custody.**  
   Before its native call, persist an immutable continuation reference linking the public handle, provider operation/job, original context and new local runtime identity. Record the new SDK acceptance and incarnation using the existing mechanisms. Preserve the original submission and native identity in history; do not pretend the new native task is the old one. Keep this narrow to provider continuation rather than generally allowing a handle to adopt arbitrary native tasks.

4. **Permit only one unresolved local continuation.**  
   Prefer reconnection to the original SDK identity whenever it remains available. Create a replacement leg only after the previous local runtime/worker is confirmed gone—not merely unreachable. If the continuation’s `tools/call` reply is lost, retain acceptance uncertainty; reconnect its known identity or require inspection. Do not automatically issue another call. The existing recovery coroutine coordinates that attempt; the SDK’s `ToolTask.result()` remains its sole task driver.

5. **Treat finalization and cancellation as real effects.**  
   This is not merely an “observation” invocation: current `poll()` can cancel the provider job, materialize files and remove staging. Retain cancellation intent across recovery; cancellation permits only the narrow control/cleanup continuation, not renewed transfer or publication. Do not bypass ordinary admission checks globally.

6. **Require evidence before settling the public task.**  
   Provider success alone is insufficient. Verify local publication and cleanup, including whether the previous worker already performed them. Current [`materialize()`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/storage/transfers.py:94) allocates a new snapshot and changes directories, so blindly calling it again is not safe recovery. If the publication phase is ambiguous, retain uncertainty for inspection. A new leg’s cleanup receipt must not erase the old incarnation’s unknown obligations.

There is one necessary startup change: identify recoverable provider-backed work **before** the blanket memory-runtime interruption in [`native_tools.py`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:142). Keep that public task nonterminal while reconnecting. Do not terminalize it and subsequently reopen it.

**R2 needs an explicit, narrow clarification.** Its [recovery paragraph](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:88) requires provider reattachment but also says “never submit again.” A new local native invocation is technically a submission. Suggested clarification:

> After confirmed loss of a local native runtime, recovery may create a host-only native continuation for a verified existing provider job. The continuation retains the public task and original custody, records a new local execution identity, and cannot submit provider work. Its acceptance follows the ordinary uncertainty rules; unresolved local publication or cleanup remains uncertain.

That preserves the intended architecture. It does **not** authorize replay of an uncertain original download, require another registry, or require exactly-once execution.

This is an architecture decision only. A6 remains open until implementation and later qualification establish these boundaries. No files changed or checks/services launched.


