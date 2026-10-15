# R34: finish the existing-owner corrections

Architecture and feature scope remain frozen at R2. Astra and actual Claude Code
Fable independently support the ownership/removal direction and reject source
readiness. Their R33 reports and Astra's combined adjudication are retained under
`docs/qualification/`. None accepts the uncommitted R34 source or a release.

## Correction status

| Confirmed finding | Existing owner and removal | Current status |
| --- | --- | --- |
| Immediate disclosure denial fails an unrelated assignment. | StepRecorder handles only typed access denial, preserving the protected observation and continuing other results. Core/malformed-record failures remain strict. | Implemented, unexecuted. Existing assertions now require continuation and non-disclosure; a conversation-path survival regression is still required. |
| Wait loses observe-only/uncertain/pending permission requirements. | The local wait-result wrapper retains each member's required right. Collection and compatibility aliases preserve it into the existing recipient-input commit. | Implemented; twelve canonical/alias running/uncertain/terminal revocation cases constructed, unexecuted. |
| Runs calls a partial workflow completed. | Respect recorded predicate/stalled outcomes and require all declared steps launched before inferring completion. | Implemented; recorded and historical partial-workflow cases constructed, unexecuted. |
| Compatibility projections discard continuation and filter Questions too late. | Use existing ordered/active indexes with bounded pages; retain response fields and expose/consume continuation. Apply pending selection before paging. | Pending implementation and public route/consumer regressions. No silent truncation or additional projection owner. |
| Failed pre-assignment child creation abandons session rows. | Reuse the same child address for the same trusted spawn identity through existing session/conversation owners. Preserve uncertain custody. | Pending implementation and faults before/after durable task observation. Do not delete a potentially committed session or replay model execution. |
| Question guidance incorrectly promises child failure. | Shared guidance separates Question and assignment outcomes, independent work, yield and explicit waiting. | Corrected in the Factorio guidance; regression constructed, unexecuted. Other matching obsolete wording was not found. |

Observation without a pattern already returns immediately under R2. Its canonical
description now explicitly says timeout bounds pattern waiting; the compatibility
description still needs the same clarification. Do not add a long-poll mode.

Ungated model-segment errors currently finish that finite assignment as failed;
accepted background work retains its separate lifecycle. Later eligible input can
create a linked assignment under ordinary admission. Preserve that honest behavior
rather than silently yielding every failure or automatically retrying provider
calls. Explicit recovery retains its existing fixed-context contract.

Native admission locking is an advisory measurement concern. Preserve its serialized
cancellation/admission decision. The Shell-named callback shares the same injected
authorization for both roots; source inspection does not establish incorrect
storage authorization. Do not introduce a cache, coordinator or another admission
service to address naming or unmeasured contention.

## Evidence and remaining acceptance

R33 production is core `24e7dfbb` / GACT `75495899`; later commits through core
`0bf8359e` / GACT `3a753c4d` fix tests only. Twenty-six selected cases passed
individually and sequentially in the D qualification repository. The receipt keeps
three initial fixture/assertion failures and their corrections. Mixed revocation
requires the peer result withheld while an independently eligible owned result
can still arrive automatically; it does not acknowledge the protected mixed tool
observation. All disposable run roots and their test/Core processes settled.

Those component checks do not qualify R34. Finish this correction pass and its
bulk regression construction before executing its behavior cases. Renew both
source reviews afterward. The remaining absent-import test inventory has 39
modules, including unrelated historical imports; map retained behaviors before
migrating/deleting coupled tests. The old hard-drain assertion needs migration.

F03, exact-head CI, Q1–Q9 and R1–R6 remain required. Fresh model/service/browser
qualification has not run in this packet. Continue using the contained launcher
and D environment, preserve all protected/manual-only boundaries, and retain
bounded receipts rather than bulky exports or archives.
