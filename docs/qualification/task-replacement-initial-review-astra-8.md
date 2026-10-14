# Corrected initial implementation: independent Astra review

Reviewed core `9b0a91ecc4b6ea2be014dca3fa7f9de32d4f3c70`, GACT `f1b099cdf479a4e2516391a525efeba17799cd65`. Read-only source review; no runtime acceptance.

**R2 is a substantially better direction, but the current implementation is still a source-level no-go.**

I reviewed the [R2 plan](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md) against core `9b0a91ec` and GACT `f1b099cd`.

The simplification is real: native execution owns native work; the conversation engine owns assignments; Core records observations and mail; recipient-input commits acknowledge delivery. The old competing registries, wake policies and terminal writers have largely been removed. That addresses the overengineering more directly than putting another coordinator above them.

Five concrete issues remain:

1. **[P1] Ordinary Downloads reject their own operation.**
   [native_storage.py:257](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_storage.py:257) creates a queued transfer, then calls `validate_download()`. That validation rejects any queued/running transfer—including the one just created. Validate before reserving new work, or explicitly exclude the verified current operation while retaining overlap protection.

2. **[P1] Draft selection can consume unrelated feedback without processing it.**
   [variant_drafts.py:751](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/variant_drafts.py:751) commits the whole input batch before resolving the draft choice. If a choice and new human feedback arrive together, it returns the selected draft without invoking the agent on that feedback. The feedback is already acknowledged, so it cannot independently trigger another turn. Keep it pending or process it after selection; the same problem applies to dismissal.

3. **[P1] Native cancellation intent can outlive its only cancellation attempt.**
   [native_tools.py:546](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_tools.py:546) records cancellation, then sends one cancel RPC. If that RPC fails, reconnection resumes observation without retrying cancellation. Already-running Shell work can therefore continue while its assignment waits for cancellation settlement. Retain cancellation delivery as pending work against the original native identity.

4. **[P2] Provider reattachment is still a one-shot attempt.**
   [native_storage.py:192](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/native_storage.py:192) catches continuation setup failures and records uncertainty. A transient Core failure before submission does not retain the reattachment attempt—only the uncertainty write. Recovery can therefore finish while a surviving provider job remains unobserved. Retry safe, pre-submission reattachment failures while preserving the prohibition on repeating uncertain submissions.

5. **[P2] Restart calls a wait that expressly rejects this caller.**
   [conversations.py:712](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:712) waits using the assignment’s own session. Shared waits reject waiting on one’s own active assignment, so restart can immediately report uncertainty during ordinary cleanup. Use an internal settlement wait that preserves the model-facing self-wait guard.

Several earlier findings have been corrected in source: failed Core writes now schedule recovery; native observation reconnects; subtree cancellation retains its settlement listener; migration preserves withdrawals and subscription state; injection rechecks observation rights. Provider continuation now exists, but its recovery path remains incomplete.

**My recommendation: keep this architecture and fix these existing owner paths before qualification.** The remaining work needs focused failure scenarios, rather than more lifecycle abstractions.

This was read-only source review. I changed nothing and ran no tests, services or live acceptance; runtime readiness remains unverified.
