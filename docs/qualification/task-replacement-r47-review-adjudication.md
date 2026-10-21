# R47 adjudication and next correction

R47 is not source-accepted or qualified. Astra found a demonstrated production
cold-loader defect: accepted-message repair preserves the raw lane, then resident
rehydration can invoke the old JSON-driven whole-lane replacement and remove
unrelated partial output. The new six regression cases passed, but their initial
fixture loaded directly from atoms and did not exercise that production loader.
Two additional cold-loader cases now use the production resident-set factory;
they are constructed, not executed. The legacy identity-conflict case is also
constructed and unexecuted. No assertions or budgets were weakened.

The independent actual Fable review gave scoped GO for the splice, while explicitly
listing the reachable cold-loader data loss as outside its delta review. That GO
does not override Astra's end-to-end NO-GO. Its result print hit a Unicode-output
failure, so only the bounded partial report and complete model identity/usage
receipt were returned. No complete implementation-review approval is claimed.
Future reviewer controllers must retain the selected result before printing and
emit UTF-8/ASCII-safe JSON; parsing and printing failures must be distinguished.

Astra subsequently prefers replacing the old JSON-first recording contract:
confirm Core before projections; make normal reads, restart reconciliation and
metrics Core-backed; remove runtime JSON remint/backfill policy; retain immutable
unconfirmed output through existing owner-local CoreRecovery without rerunning
inference, finalization or tools. Optional JSON failure is projection lag. Later
clear/delete must prevent stale pending evidence from restoring removed content.
Legacy JSON is handled once through data-only Core migration before admission and
before file-based startup reconciliation. Stable occurrence identities/receipts
preserve duplicates, original timestamps and conflicting evidence; ambiguous
visibility/delivery remains unknown and cannot trigger execution or mail ack.

This Core-first direction is a clarification of R2, not implementation approval.
R48 construction has not begun. It replaces a competing recovery authority rather
than adding another task driver, scheduler or reconciliation engine. Focused
regression assurance, full source review, required CI and the finite actual-model
matrix remain separate gates. R44/R45 model evidence applies to its original tuples.

Reviewer profile isolation was corrected. PID 38864 was stopped after two small
session metadata files were found in the CLI's default C profile. Their exact
removal was automatically rejected, did not run and is manual-only. PID 43968 then
ran actual `claude-fable-5-1` with a private D profile and a non-refreshing credential
copy, exited 0, and the original Claude credential hash remained unchanged during
that isolated run. Its D profile is retained for reuse during the ongoing review
family; no product process was stopped. The prior unrestricted-profile reviews
do not supply proof that original Claude authentication was unchanged.

All earlier exact cleanup/manual/private boundaries remain. R44/R45 disposable
families and short IPC roots remain after rejected removals; their services and
registered processes/listeners are absent. No root-absence or free-space recovery
claim is made. Protected human documents retain their previously verified hashes.

Current remote targets were read: core develop/main `9965667afd6981194705b160ab22a3e0b09a5158`
and GACT main `6ea4e15e4ac3b0160237810b2f11ed3d2311c6a0`. They are not yet integrated
into the current feature tuple. Target integration and recorded impact precede
final candidate freeze and final acceptance; no released branch or pin was changed.
