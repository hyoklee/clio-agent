# R35: complete the two confirmed R34 corrections

R2 scope and execution ownership remain frozen. Both independent R34 reviews
support the architecture; the combined adjudication identifies two source defects.
Their reports are in `docs/qualification/`. They do not accept subsequent R35
changes or establish runtime qualification.

| Finding | Existing owner correction | Status |
| --- | --- | --- |
| Reused child rows can skip known unfinished initialization. | SessionStore retains bounded initialization receipts. Its existing provenance observer checks the child's recorded Core creation before publishing again. Known-unattempted SessionStart runs once; an admitted hook with no completion receipt remains uncertain and is not replayed. Completed creation and human edits are preserved. | Implemented, unexecuted. Ten same-process/reconstructed-store fault cases use the real Core observer; four visible-hook-effect/receipt-failure cases distinguish known completion from uncertainty. |
| Load-more errors never reach the existing error surface. | The observability query owner requests rejection for this action and supplies its single page-controls projection. Workspace data forwards it. | Implemented, unexecuted. The actual query hook and continuation component now have a failed-second-page/retained-first-page/successful-retry case. |

No task scheduler, execution registry, delivery acknowledgement or recovery worker
was added. Initialization receipts are server-owned session metadata; lifecycle
evidence is read from the existing Core provenance lane. Missing legacy hook
receipts mean unknown effects, not permission to run the hook again. A recovered
creation event is not sent through its derived fanout again. These checks do not
claim exactly-once external effects.

Preserve the established Stop and any-wait contracts. Accepted eligible work may
release a Stop-held input; an ordinary wake hint cannot. Veto/setup-failure holds
have separate release rules. Any-wait includes a member error, keeps other handles
explicitly pending and cancels no member. Strengthen coverage and wording without
changing those policies. Workflow metadata limitations are documented rather than
used to expand coordination scope. Work shows active pages plus available live
child records; retained history stays accessible through Runs and shared queries.

All runtime, test data and caches remain in the D qualification repository under
`.pytest-runtime`. No R34 or R35 behavior, native/model/browser qualification has
run. Finish this construction pass and bulk regressions, then run focused cases
individually/sequentially and renew source reviews. Legacy test migration, F03,
exact-head CI and Q1–Q9/R1–R6 still block completion and release.
