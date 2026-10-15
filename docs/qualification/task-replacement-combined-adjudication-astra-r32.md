**R32 is the right correction pass. I would approve its direction with the clarifications below added before implementation.** The existing candidate remains NO-GO.

1. **Make reservation retirement the complete boundary.**

   The callback must be attached before [`TurnRunner` can discard an admitted coroutine](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/turn_runner.py:113). Cover no worker started, cancellation during the initial activity write, normal execution, and finalization.

   Run reconciliation once per exact reservation, after physical retirement and before release. Remove the superseded body-local writer. If recording fails, merely enqueueing recovery is insufficient: the affected input must remain inadmissible until reconciliation confirms. The callback must not await another operation that itself waits for this reservation’s release.

2. **Specify Stop/retry ordering and implement the promised resume behavior.**

   The lifetime decision is correct: Stop preserves input; a trusted retry replaces its exact uncommitted source; ordinary continuation preserves accepted order.

   However, [`_admit`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:266) currently releases stopped inputs **before** staging applies retry supersession. Simply adding `stopped_before_input_commit` to the allowed reasons will still deliver both copies: release changes the original’s state and revision before supersession checks it.

   Apply trusted supersession before ordinary hold release. Also cover retry accepted **during stopping**, before retirement has written the hold.

   Define “later arrival” relative to the Stop request, including input accepted while workers unwind. An old pending item, repeated signal or recovery notification must not masquerade as that arrival.

   Finally, [`resume`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_controls.py:188) currently returns `already_running` for an unpaused stopped assignment. The map promises explicit resume of stopped input; add that existing-owner change and its regression explicitly.

3. **Make cancel-after-Stop work after the reservation is gone.**

   Withdrawing the exact uncommitted admitted input is a coherent cancellation policy. Preserve the stated protections for committed, revised, withdrawn and unrelated input.

   But a volatile reservation callback cannot identify that input after Stop has finished—or after restart. Retain exact assignment/turn/input-revision correlation in the existing Core records. Cancellation must use that evidence, rather than infer ownership from the latest message, a held reason, or session membership.

   Add Stop → retirement → cancel and restart → cancel cases. Historical ambiguous ownership should remain unresolved, as the map already states.

4. **Expand the Runs row into an explicit UI replacement contract.**

   Fable’s missing-route finding is confirmed. The page calls removed list and relay endpoints, and still exposes [`detach` and `dismiss`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/web/src/routes/runs-page.tsx:299) actions backed by removed APIs.

   The common task direction is correct, with these requirements:

   - Specify canonical listing, pagination and cross-session coverage; avoid duplicate descendant rows or silently showing only the first page.
   - Preserve applicable task kinds, stable handles, owner/session navigation, supported actions and the shared status decoder.
   - Remove unsupported detach/dismiss controls. Do not reinterpret them as cancellation, notification acknowledgement or history deletion.
   - Preserve workflow/provenance navigation. A stopped `run_workflow` tool invocation does not establish that its accepted children stopped; the current transcript-derived workflow state must not become authoritative execution status.
   - Remove live special-relay requests from Runs, settings, infrastructure and navigation. Retained historical rows should explicitly show unavailable execution/visibility while remaining readable.

   Extending the existing repository with thin canonical query bindings is appropriate. Another run registry or independent UI lifecycle model is unnecessary.

5. **Strengthen the cursor rule: the current early check is incomplete.**

   [`observe`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:331) checks only the recipient before changing subscriptions. Version, handle binding and scan-position checks happen later in `read_observations`. A same-recipient cursor for different handles can therefore change subscriptions and then fail.

   Validate the complete cursor and request shape before subscription mutation. Share that pure validation if useful; retain authorization rechecks after asynchronous gaps.

The map correctly distinguishes several apparent duplications from necessary ordering:

| Review observation | Adjudication |
|---|---|
| Collection publishes notices | **Keep the idempotent common publication boundary.** Removing it before replacing terminal-write/publication ordering can allow later duplicate automatic delivery. It does not acknowledge collection. |
| Message authorization appears twice | Consolidation is reasonable **inside `SessionMail.peer`**, preserving authorization, recipient existence, historical-handle restrictions and confirmed acceptance ordering. Removing the writer-boundary check alone is wrong. |
| Question handle derivation appears twice | Share identity construction if useful, but preserve the existing invocation’s absolute expiry. The prior-definition read currently prevents retries from recomputing a different deadline. |
| Private helper access and token-estimator import | Small ownership/API cleanup opportunities; not grounds for another architectural pass. |
| Many replay projection dictionaries | A passive bundle could simplify maintenance later. No demonstrated rollback defect requires that refactor in R32; retain failure rollback and admission holds. |

The exact-completion gate repair, pause-independent cancellation cleanup, native-media recovery, narrow index intersection, queued initial activity and recipient-principal correction are otherwise well scoped.

Add the ordering cases above to the constructed regressions, plus Runs/service route coverage and invalid-cursor-with-`notify` coverage. Preserve unlimited canonical history and the separate runtime qualification gates.

Read-only adjudication; no files changed and no tests, services or models launched.
