# R21 — complete the R20 source-review correction set

Frozen review base: core `f020a5912ca9a2fe57be7dd3aaba1f640bc669f5`, GACT `ce99316446848ddd269b1bf782ff2c87cc9db14a`, marketplace `9257bba5953b012ba796299df4c633e698dbaddc`. Astra and actual Claude independently returned source NO-GO. Their complete reports are retained in `docs/qualification/task-replacement-implementation-*-r20.md`. Both review processes ended; Claude's 40-file / 713,420-byte disposable source copy was removed without an archive.

No behavioral tests or product services are launched until this complete correction set is initially implemented. Test construction continues against public contracts, without restoring removed owners.

| Obligation | Existing owner and correction | Required acceptance |
| --- | --- | --- |
| Context recovery boundaries | ARC restoration and transcript codec; no variant parent-history fallback; exact-scope traces only for nonprimary scopes; missing-version input records remain unconfirmed; current input matches ID and turn ID; preserve post-compaction parts and group thinking/text correctly; orphan effects remain uncertain before atomic publication | Fresh scope/variant isolation, mid-row compaction with later tools/results, legacy input intent, no fabricated acknowledgement, complete recovery with explicit uncertain calls |
| Pause recovery | Conversation owner restores only the matching assignment's hold | Stale A hold cannot pause successor B after startup |
| Deadline completion | Conversation owner applies the same persisted deadline at deferred Stop-hook completion | No successful terminal outcome after expiry wins the writer lock |
| Workflow identity | Existing runner writes typed checkpoint provenance through the confirmed Core writer; passive exact-root/invocation and latest-execution indexes rebuild on replay. Resolve historical invocation before continuing current execution. Bind new invocations that resume the same execution. Preserve old data-only checkpoints at startup. | A's replay cannot advance retry B or replace B's latest pointer; interrupted checkpoint/index updates repair before new work |
| Workflow data handoff | Pass the accumulated state through the existing immutable launch-context path at new-step admission; resume preserves that captured state | B's actual model input contains A's state; C sees A and B, including admission interruption |
| Passive cancellation | Observation callbacks never issue new cancellation requests. Explicit requests and owner-local retry of genuinely pending RPCs remain separate. Deduplicate identical uncertain observations. | No self-triggered cancel/attention loop; explicit retry remains possible; late proof finishes parent |
| Unknown native attempts | Publish attention before terminal-only result processing; retain each incarnation's facts | Working replacement with unknown prior cleanup is visibly uncertain, with one episode |
| Observer retirement and cancellation retries | Native/external owners release finished SDK bindings after confirmed matching terminal backend evidence, actual observer/RPC exit and durable custody. Keep cancellation holds, active cleanup, identity/schema and Core history. Late settlement reads captured submission schema without a live ToolTask. Retire obsolete delivery retries only when no pending delivery remains; retain real reattachment/recording recovery. | No retained completed bindings or unresolvable cancel-delivery spin; late cleanup still settles and publishes final; explicit refresh reconnects original identity without tools/call |
| Plan repair isolation | Question presentation repairs each gate independently; immediate repair, deferred retry on recording failure; preserve the same plan predicate and exact gate comparison | One bad session cannot prevent readiness/admission for others; answered/cancelled/expired decisions recover |
| Approval retry effects | Existing plan owner makes playbook transition idempotent for the exact Question, preserves newer queued transcript rows on repeated context clear, and reuses the captured reviewed artifact | Replaying gate repair cannot remove the execution playbook, duplicate approved artifacts or erase later feedback |

The historical lookup and resource-retirement seams received Astra's explicit design approval. They add provenance and passive indexes to the existing Core writer, not a workflow engine, scheduler, registry, database or universal reconciliation owner. Captured provider job/operation identity stays with its existing storage owner. Trusted external configuration/authentication remains necessary for reconnect.

The optional human decision about restarting despite unresolved cancellation is still pending. Strict R2 applies unless the human changes it; uncertainty is never relabelled as confirmed cleanup.

Review notes that are not confirmed defects remain separate: the plan-Question predicates currently match; short-control/Core performance needs measurement; an external acknowledgement for a member active at cancellation remains insufficient by the existing strict contract. Failed, skipped, unavailable and unexecuted gates remain unqualified.

## Initial packet state

All listed production corrections are initially implemented through existing owners. Scoped Ruff/format and Linux Mypy (23 source files), removal/size/class guards are recorded in the R21 static receipt. Behavioral cases are being constructed in bulk and remain unexecuted. Source approval from both reviewers remains required.

Plan execution transition now records the exact Question decision and both playbook keys in one SessionStore write. Repeated clear-context decisions preserve transcript rows newer than the Question creation boundary. Native Question review uses its captured artifact reference; the legacy fallback uses the existing artifact mint, whose content digest deduplicates byte-identical versions. No artifact registry was added.

The small source-review notes are also corrected: nonrepresentable explicit workflow budgets are rejected before execution, uncertain cleanup takes precedence over timeout classification, cancellation activity survives worker unwind, and distinct restart-failure reasons retain distinct notice identities. These changes create no new execution policy.
