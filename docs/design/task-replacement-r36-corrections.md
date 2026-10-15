# R36: prepare once, execute in the existing session owner

R2 feature scope and execution families remain fixed. R35 architecture is supported
by both reviewers; source readiness is rejected. The combined adjudication confirms
initialization lock scope, a regenerated workflow deadline, and approval-setting
reuse as the bounded corrections. Reports are retained under `docs/qualification`.

## Existing-owner replacement map

| Boundary | Correction | Required evidence |
| --- | --- | --- |
| Conversation submission and SessionStore | Prepare complete child metadata, confirm the assignment and delegation under the existing writer, then let the existing child-session worker perform startup before inference. Startup hooks execute outside the global task writer and outside a shared executor wait. SessionStore guards one initializer per trusted identity. Parent/child admission and cancellation remain checked before execution. | Same-identity concurrency, cancellation before/during startup, unrelated query/Question/control progress, no model call before initialization and truthful physical retirement. |
| Trusted creation context | Apply initial private profile/metadata during original row construction. Reuse validates immutable identity/profile and preserves mutable human settings. No post-reuse approval reset. | Original profile and descriptor retained; human approval-mode edit survives reuse; changed immutable work is rejected. |
| Workflow checkpoint | Persist the absolute prepared deadline before child metadata creation; reuse it on reconciliation. Other launch inputs already derive from the fixed declaration, request and saved workflow state. | Timed pre-assignment fault, same-process/reconstructed-store recovery, original session/step/deadline and no duplicate launch. |
| Recorder/mail tests | Exercise late eligibility and context-budget exclusion through real commit/recovery. | Excluded trigger absent from model context and acknowledgement, remains pending, later arrives once. No forced-inclusion assertion or changed ordering. |

The child remains a conversation-engine task. This adds no initialization task kind,
queue, scheduler or execution registry. The existing TurnRunner owns its worker and
retirement, and existing hook cancellation handles owned subprocess cleanup.
Known startup failure becomes the accepted child's stored error and queued result.
Previously admitted but unconfirmed hook effects remain non-replayable; document
the parent inspection/evidence path and explicit recovery choices. Unsupported
loop-thread initialization must fail before effects rather than confirm a scheduled
write.

Preserve established any-wait and uncertainty contracts. Clarify that unavailable
members return independent outcomes and uncertainty requires inspection rather
than repeated receipt waiting. Do not add a new wait or observation lifecycle.
F03 measures existing input-recovery scans and session-file writes before choosing
any performance correction.

All correction source and tests are initially constructed before behavioral
execution. Source checks and renewed reviews precede final qualification. Tests,
Core state, caches and disposable data stay inside the D repository; existing
manual-only/rejected boundaries remain. R35 component/live cases remain unexecuted.
