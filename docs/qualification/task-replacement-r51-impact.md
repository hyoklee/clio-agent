# R51 — publication custody and joined provider failure

Source base: core `f92753cc43eb25da7c37798ec1f9b5420d72fd3e`, GACT
`0a4ca5d5915a0add61cd5048b742161092468481`, marketplace
`1a9b8d0337217950a2b44c303a8d22547d52d756`. The candidate commit containing
this document supplies the corrected core identity; dependencies remain the
R50 tuple. No installed state or released pin changes.

Astra's R50 source verdict was NO-GO; Fable accepted those three original
corrections while identifying further shutdown/projection risks. Neither source
review qualifies runtime behavior. R50 focused execution: 17 passed; the stale
incarnation test failed setup because its real-Core fixture was not in scope.
That setup is corrected here. No failed case is counted as acceptance.

Changes stay within existing owners:

- A plan-exit recording waiter cancelled by Stop returns without normal
  finalization. Recovery retains the original output; the turn's LM ledger closes.
  Approval carries its original assignment/context identity. Cancellation,
  supersession or changed context resolves the obsolete request instead of
  attaching it to the latest assignment or retrying admission forever.
- The registered Download and provider-continuation workers retain joined local
  observer evidence in `finally`, including nonretryable failures before shutdown.
  This evidence releases local resources; remote cleanup remains unknown. Provider
  classification reads captured source custody rather than requiring a live
  session/workspace, and never submits or cancels a remote job.
- Turn publication resumes completed steps. Session usage is a fixed projection,
  so a lost flush reply cannot add it twice. Effectful hooks are attempted once;
  failures are logged as unconfirmed rather than automatically replayed.
  Required projection writes retry. Local progress is volatile, not a new durable
  delivery authority or an exactly-once promise. Publication-only recovery checks
  the original transcript visibility identity before proceeding.

New cases exercise plan recording cancellation, obsolete approval ownership,
lost session-flush replies and effectful hook failures, plus the actual registered
FastMCP storage worker failing after provider acceptance. Provider responses in
that regression are doubles; real Globus acceptance is still outstanding.

The R49 production Codex/Luna Shell and idle/post-Stop Question traces predate
this candidate. They demonstrate that testing and actual-model work began, but
do not qualify R51. Required affected rechecks: those same model scenarios,
plan gate/Stop recovery, provider observer failure/reattachment, publication
recovery, and the remaining finite Q1–Q9/R1–R6 matrix and exact-head CI.

No new execution owner, scheduler, task registry or worker queue is introduced.
The existing 800-line/removal guards remain unchanged. Full regression migration,
independent candidate review, live matrix and release acceptance remain unfinished.

Cleanup: the R49 product service's registered processes and API/Core listeners
are settled. The R49 disposable runtime/temp removal was rejected by automatic
review before execution; those exact roots are human-manual-only and are neither
reused nor retried. Selected bounded evidence is in the independent D receipt.
Other previously rejected/manual-only roots remain protected.
