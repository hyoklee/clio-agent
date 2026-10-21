# R55 — withdrawal projections and obsolete control notices

Base core `499678437d4455b2fb48e51847e9a37ef7fc8b3b`; other repositories and
dependencies unchanged. The D candidate was edited while C retained the frozen
R54 review snapshot. C is fast-forwarded only after that reviewer exits.

The recorder's existing confirmation closure also retains a withdrawal cleanup
callback. It runs even when the waiting turn was stopped; failures retain the
same recording custody for retry. Normal/paused/error owners settle the original
retry/session/cancel-event projections without publishing discarded output.
An unsurfaced original plan request is tombstoned under the Core writer lock,
only while its exact captured request still matches. Existing surfaced Questions
and successor requests are not retargeted.

Fable's R54 source finding: an obsolete approval closure created eligible result
mail that could start a successor merely because boot recovered an old header.
The same shared publication path now retains that outcome as held control-only
mail. History and explicit reads are preserved; boot reconciliation alone cannot
wake the agent. No execution owner, polling driver, mutable registry or queue is
introduced.

The corrected R54 plan/obsolete-owner regression cases both passed individually.
Affected R55 cases add session/retry settlement, pending-plan retirement and held
notice assertions; they require fresh execution and independent review.

R53 Codex/Luna native-family and idle/post-Stop Question checks passed. They are
predecessor evidence, not acceptance of this tuple. All 20 registered product
processes and seven listeners are settled; original Codex authentication hash is
unchanged. Bounded selected receipt: D execution repository
`.pytest-runtime/static/r53-live-receipt.json` (about 120 KB).

Automatic review rejected removal of the new R52 runtime/temp roots before the
command ran. Their actual audit covers 1,631,807,597 logical bytes; both roots
remain human-manual-only and must never be retried, bypassed, moved, delegated or
reused. Other prior manual/prohibited boundaries remain intact.

Full regression migration, required Q1–Q9/R1–R6, exact-head CI and publication
remain incomplete. No review or regression pass is claimed as live acceptance.
