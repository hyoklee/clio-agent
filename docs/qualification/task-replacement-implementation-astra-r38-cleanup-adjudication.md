# R38 Astra source adjudication

Frozen source: core `27b3a381d7c2da939a57e308c4f0e1cf87c3fe4e`, GACT `416601856a1e828f658fd59fe6bc5bc4f1129f05`, marketplace `999fdafa9d0f1214e3f9f4f98a6d4d4a8f8f3751`.

Reviewer chat: Review task architecture plan. Turn: `01a13fbd-cc61-79a2-a794-c701106b0e17`. Read-only source adjudication; no execution or qualification claim.

The minimal condition is **a matching fresh backend observation, valid captured-result contract, and only known, still-owned pending cleanup—not an unknown incarnation**.

Apply it in [NativeTools._settle](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/native_task_settlement.py:107), **after** continuation reconciliation and result validation, immediately before the pending-cleanup return. That boundary already has the required evidence:

- **Matching custody:** the observation belongs to the current submission and full backend identity, including the adopted task ID. Preserve the existing acceptance binding; a health probe or matching task ID alone is insufficient.
- **Valid result:** `validation_problem` is empty after checking the original captured output schema.
- **Known pending work:** at least one admitted incarnation remains `pending`; none is `unknown`. Every unresolved incarnation belongs to the retained native runtime, with no completion receipt or `finished_at`. Other incarnations must already be `confirmed` or `never_started`.

The last condition relies on existing ownership: `NativeWork.run` retains the admitted operation through cleanup and receipt recording. [Recovery already changes pending attempts from a different runtime to unknown](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/native_task_recovery.py:139). Preserve that distinction, including provider-continuation predecessors. Do not infer live ownership from a persisted `pending` value alone after runtime loss, or inspect only the newest attempt.

When those conditions hold, update the existing snapshot to a **nonterminal cleanup-pending state**, clearing its active uncertainty status/episode. Keep the raw backend result as nonfinal evidence. Do not set `terminal_at`, acknowledge delivery, replay work, or delete historical attention mail. The existing cleanup callback later publishes the final outcome.

**No change to shared wait policy is needed.** Nor is another worker registry or liveness coordinator needed.

The contrasting regressions are:

| Evidence | Required result |
|---|---|
| Same-runtime admitted worker; cleanup held open; observation lost then recovered directly to valid `cancelled` | Clear stale uncertainty; all-wait remains blocked until cleanup finishes, then receives the final outcome. |
| Any incarnation has unknown cleanup, including an older provider/runtime incarnation | Retain uncertainty despite a fresh reply; return the handle as pending. |
| Cleanup pending and terminal payload fails the captured schema | Retain contract-failure uncertainty; fresh transport does not clear it. |
| Reply belongs to another submission/backend identity | Reject it as recovery evidence; do not clear attention. |
| All required cleanup receipts are confirmed | Use the existing terminal settlement path. |

Check both `outcomes` and `pending`: asserting only that the handle remains pending misses the erroneous uncertainty return.

This is source adjudication only; no edits or execution.
