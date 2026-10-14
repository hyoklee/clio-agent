**Approved. The original delegation is an indivisible assignment input**, so extending the existing batching exception to it is appropriate.

The current code confirms the problem: staging can clip delegation text, while the final rendered-input check excludes oversized delegation items. The child’s initial prologue contains only generic continuation text. [Batching code](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:113), [initial input](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversations.py:264)

Apply these boundaries:

- **Cover both staging and final rendered-input budgeting.** Changing only `bound_rendered` would preserve text already clipped during staging.
- **Allow one oversized delegation as the sole newly rendered item.** Keep other arrivals pending. Already-recorded explicit collections remain independent.
- **Preserve the full original assignment and exact evidence-reference metadata.** Evidence bodies remain bounded, with usable references and explicit partial markers.
- **Keep delegation’s identity and authority unchanged.** Share only the batching predicate with human/composer inputs; do not classify delegation as human input or grant additional rights.
- **Require the original assignment in the child’s first committed model input**, or its recovered committed equivalent. The generic continuation alone is insufficient.
- **Retain complete-request/provider limits.** If those reject the input, report the failure explicitly and preserve recoverable input. Do not clip-and-acknowledge it or repeatedly wake an assignment that cannot fit.

Focused checks: oversized assignment preserved exactly; small assignment with oversized reference metadata; bounded evidence bodies; sibling notifications remain pending; interruption before commitment; recovery after commitment; provider-limit rejection without silent loss.

This is a shared input-selection correction. It needs no new scheduler or execution policy, and leaves the previous observation decision unchanged.
