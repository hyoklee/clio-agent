# Tasks replacement status

## Current qualification — 2026-10-20 00:00 UTC

Initial implementation and initial test construction are **done**. Current work
is regression repair and qualification. **No merge, release or installation GO.**

- Production source: agent `bab261dbf201ba5db5d8b2097d309944e87215f2`, GACT
  `9bf5791c098f53f0ff5a6c9b50b6a444cb0a2446`; marketplace
  `2c172233a9f895e41f7de121a3871d282a5fc0a2`. Python 3.14.6, Core 2.3.2,
  FastMCP/tasks 4.1.0, MCP 2.0.0, Docket 0.26.2, DSPy 3.4.0, Claude SDK 0.2.159.
- Current `develop` through `c3db245cc8d6f20cd9987293377d94d6955d348b`
  is merged, with zero commits behind at the October 19 23:52 UTC refresh.
  Its matching GACT pin is integrated. Old task/relay drivers remain deleted.
- [Agent CI 39341328047](https://github.com/iowarp/clio-agent/actions/runs/39341328047)
  completed with **seven distinct failing cases**: four recorded-read export
  fixtures lacked TaskHistory; three SSH approval fixtures lacked an assignment.
  The complete inventory contains all 12 interpreter/shard reports. Both are
  corrected together in the following regression-only batch, without production,
  assertion or resource-budget changes. No local pytest/Vitest loop ran.
  Current-head regression assurance awaits that batch's CI; earlier green CI is
  not current-head acceptance. The earlier intermittent SSE replay timeout did
  not recur on this head; no timeout or test change was made to hide it.
- [GACT workspace CI 39339096564](https://github.com/iowarp/gact-tui/actions/runs/39339096564)
  passed all six executed jobs, including Linux/Windows/macOS debug builds and
  the fixture-backed native WebView check. Three release-event jobs were
  conditionally excluded. Separate schema/CI workflows passed. Fixture-backed
  WebView evidence is not fresh native Desktop acceptance.
- **New scoped live acceptance:** R447/R449 proved staged peer capacity before
  input commit and human/Question injection while a goal waited. R453 proved
  active Indexing reuse and distinct options/session handles with actual native
  identities (one real enumeration, two existing-source results). R455 proved
  shutdown with a running Shell/descendant: no early terminal publication,
  physical cleanup before service exit, and closed late admission.
- R461 performed two normal startups of the same 19-record historical data set,
  preserving identities/results/mail/Questions/subscriptions with zero native
  submission. Its overall receipt failed later on a wrong grant URL. R463 used
  the corrected URL: actual Luna collected original Shell/MCP results and both
  structured Question answers, inspected retained uncertainty and read a fresh
  sentinel. The freeform Question had been cancelled during prior cleanup;
  R463 does not prove its answer path. Astra accepted these stated scopes.
- **R471 passed on the current production pair:** real Luna root/child Shell and
  Questions, independent work and yields, UI pause/resume, child subtree cancel,
  parent Question answer, phone Shell cancel, attributed parent injections and
  final model collection. Desktop 1440×1000 and phone 390×844 were inspected;
  phone scroll width was 390; zero connected-browser page/console errors. An
  exact owned-workspace host process audit found no surviving workload/child
  processes. Sandbox PIDs are not treated as host PIDs. Service exit was 0.
  R465 observer failure and R470 diagnostic expiry remain failed raw receipts.
- **30 R1–R6 repetitions retain accepted scoped evidence:** R1/R3/R5/R6 on 8ff;
  R2/R4 on 6a4. This does not say all ran on one commit. Current source-impact
  review distinguishes additive data migration and presentation from unchanged
  execution/admission/delivery owners; affected migration and current UI paths
  have the fresh evidence above. R430 separately covers the Core-health delta;
  R418 covers lost-result inspection/revision. Final reviewer disposition remains
  a gate rather than an automatic carry-forward based on line counts.
- Independent Astra accepted migration scopes and the presentation correction;
  actual Claude Code/Fable R457 and R464 found no remaining blockers within their
  respective migration/presentation reviews. Final integrated matrix review is
  pending; those source verdicts are not full live qualification.
- **Still open:** real approved surviving-provider job and its continuation /
  cleanup (N12/W01/Q6), the required exclusion disposition (Z02), current
  regression CI, and final integrated evidence/source-impact adjudication (Z03).
  All 50 interpreter exclusions remain exclusions, not passes: 32 ALCF opt-in,
  four provider-live, seven Windows long-path, three Windows hard-kill/native,
  and four collection exclusions. No acceptance waiver is inferred.
- Ares job 24940 is absent. Job 24946 currently retains only the reusable owned
  checkout/environment pending final retirement. R471 family service/processes
  and eight ports are retired; 403 files / 281,113,848 logical bytes plus its
  temp root were removed. No archives. Daily Desktop/auth/defaults/released pins
  and unrelated work remain preserved.
- Automatic approval review rejected cleanup of the closed R465/R470 browser
  roots and their temporary UI token files. That command did not run; those
  exact targets are manual-only, alongside `ci-bef-reports` and earlier rejected
  paths. Do not retry, bypass, delegate, or delete them through an ancestor.

Bounded D receipts: `ci-bab-inventory.json`, `r447-live-busy-goal-inputs.json`,
`r449-live-busy-goal-inputs.json`, `r453-live-native.json`, `r455-live-native.json`,
`r461-live-migration.json`, `r463-live-migration.json`, `r471-live-ui.json`,
`r471-ui-browser-accepted.json`, `r471-cleanup.json`, and the independent review
receipts. Exact names and raw failures are retained; no bulky Core export is
needed to claim the scopes above.
