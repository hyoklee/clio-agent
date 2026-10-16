# Tasks replacement status — October 15

## Source and deadline

Both independent reviewers accept the production source at core
`ff9dc136630a5f329afa27a8ea0263dbe2fbb343`. GACT is
`0a4ca5d5915a0add61cd5048b742161092468481`; marketplace is
`1a9b8d0337217950a2b44c303a8d22547d52d756`.
The runtime tuple remains FastMCP/fastmcp-tasks 4.1.0, MCP 2.0.0,
Docket 0.26.2, Python 3.14.6 and iowarp-core 2.3.1.

The focused correction after accepted `e581cfd5` fixes Question presentation:
missing/empty agent-routing metadata now remains absent, matching the optional
UI schema. A real Core plan-approval regression exposed the invalid empty-string
projection. The new Core-backed routing contract and plan-pause preservation
cases pass. Astra and Claude Code Fable both independently accept this correction;
the source verdict does not qualify the remaining regression or live gates.

R79 records one actual Codex/Luna native-family Shell execution on this production
source: immediate handle, independent file read between two running snapshots,
progress/output observation, an expired wait with work continuing, unbounded
collection and a subsequent stored-result read. Actual exit code is zero and the
completion file hash is
`89174256781fcf055fd72081947b8ec17c709ef97c9b325fdb903839dad42166`.
The original harness receipt remains unchanged: its old field-name reader marked
the run failed. `r79-canonical-model-proof.json` separately derives the scoped
pass from canonical `kind`/`status`, confirmed nonterminal snapshots, original
invocation order, backend result and filesystem evidence. A preceding WebSocket
attempt closed before tool execution and remains a failed live attempt. No
production patch was made for it. These are individual proofs, not Q1/Q2 or
final-candidate acceptance.

The two-hour checkpoint was 21:45:05 UTC / 4:45:05 PM Chicago. It remains
**UNDONE**: Fable's last source verdict arrived at 21:45:08.409 UTC.
Source acceptance afterward does not retroactively satisfy that deadline or
qualify a release. The human renewed the checkpoint for 2026-10-16 01:14:18 UTC
/ October 15 8:14:18 PM Chicago. That checkpoint checks implementation convergence,
executed regression checks and actual-model verification separately.

## Regression migration

The current-source audit found 35 test files still naming removed modules or
controls, plus test-helper references. This is a regression-suite migration
backlog, not evidence that those deleted owners remain in production.

The first batch replaces old registry/inbox arrangements with actual Core
assignment records and the recipient-input commit. It retains card, feedback,
context and artifact-writer assertions. Provider setup drops the deleted special
Relay dependency. A2UI test clients now own application startup and shutdown;
the opted-in domain-tool fixture dispatches through the current MCP boundary.
It creates passive test assignments, without starting a model worker.

Collection succeeded for 211 cases in the eight affected test modules. Collection
does not mean execution. Nineteen selected cases passed individually and
sequentially with one worker: three busy-feedback cases, four pack/action/Question
cases, five card cases, five artifact-writer cases and two provider-bind cases.
The busy cases use actual Core admission and occupied TurnRunner slots; only
model execution is held in tests. Card fixtures include the production
delegation's message-only return grant. The Question case uses the sole Core
Question owner and preserves selected context, action identity and human
attribution. No model-inference qualification is claimed for these tests.

The old idle-producer `delivery=start` expectation is replaced with queued
steering plus an exact Core admission/turn/content/revision assertion. TurnRunner
alone decides admission. Failed legacy fixture arrangements remain recorded in
earlier receipts; they are not counted as passes. Scoped Ruff/format checks pass
for all ten changed test files, and Mypy passes for the shared assignment/context
fixture. Production source, dependency files and submodule pins have not changed
since the accepted review.

The refreshed AST inventory still finds 29 files with removed-module or missing
test-helper references, including relative imports. This is a minimum inventory;
obsolete runtime-field arrangements also need migration. The regression suite is
not yet coherent or CI-qualified. Its remaining work is separate from the
reviewers' accepted production-source verdict.

The second migration replaces artifact lineage, document-preview publication,
context references, Question expiry and generic tool telemetry arrangements.
The refreshed inventory finds 23 files with removed-module or missing-helper
references. Canonical wait presentation and the shipped wait/message aliases
remain asserted against the shared implementations. Scoped Ruff/format checks
pass for seven changed test files; Mypy passes for the assignment helper and
Question expiry cases. Twenty-four selected cases passed individually and
sequentially; the two initial failures described below remain recorded. Source
implementation, dependencies and gitlinks remain unchanged.

Two initial regression failures remain recorded: transform-metadata teardown
exceeded the 120-second test limit, and a composer case missed its five-second
runner-admission assertion. Their reruns passed without production or timeout
changes; the causes remain unproven. The timed-out case's exact private daemon
and console helper were retired and its owned runtime root removed. Later
selected cases completed their normal cleanup. These are regression results,
not final-candidate model acceptance.

Bounded D execution-repository receipts are under `.pytest-runtime/static/`:
`r56-reviewed-source.json`, `implementation-deadline-current.json`,
`r57-current-retired-bindings.json`, `r57-test-migration.json`,
`r58-test-migration.json`, `r60-test-migration.json`, `r61-test-migration.json`,
`r62-test-migration.json`, `r63-provider-setup-migration.json`,
`r60-retired-test-bindings.json` and `r63-migration-custody.json`.
The second batch adds `r64-test-migration.json`, `r64-timeout-cleanup.json`,
`r65-metadata-diagnostic.json`, `r66-artifact-context-question-migration.json`,
`r68-composer-telemetry-checks.json`, `r69-retired-test-bindings.json` and
`r70-wait-compatibility.json`.

The third migration removes four more retired test dependencies; the AST audit
now finds 19 files requiring migration (a minimum inventory). Eight selected
cases pass: optional Question routing, real plan-pause preservation, MCP input
exhaustion retaining uncertainty, paused remainder writes, evidence-parser
negative controls and three strict transcript traces. Capturing the traces was
not counted as acceptance. The reviewed baseline changes are exactly: no
invented client message ID, one user-created event instead of duplicate
publication, removal of the retired input projection and resulting identity
renumbering. Original assistant content, tool events and runtime provenance are
otherwise identical. Strict comparisons passed with regeneration disabled.
Receipts: `r72-question-projection-fix.json`, `r74-plan-and-mrtr.json`,
`r80-current-contract-regressions.json`, `r81-transcript-baseline-capture.json`,
`r82-baseline-review.json`, `r82-transcript-baseline-assertions.json` and
`r83-retired-test-bindings.json`. Failed intermediate fixture expectations remain
recorded; production was not changed to restore them.

## Qualification still required

The full acceptance ledger remains authoritative. Q1–Q9, R1–R6 repeated five
times, migration idempotence, current-head CI and real-service desktop/phone
review remain incomplete for the reviewed tuple. R53's actual Codex/Luna Shell
and idle/post-Stop Question runs used predecessor core `9e94f0ee`; they are
useful affected-path evidence, not final-candidate acceptance. Reviewer CLI
execution, tests and collection do not replace actual model acceptance.

Shell, Download and Indexing use one FastMCP/Docket execution family. Their
bytes, hashes, manifests and process cleanup still need workload-specific proof.
Relay has no special execution path or qualification gate in this replacement.
Installed Desktop, authentication, defaults and released pins are preserved.
No target-branch merge, tag, release, publication dispatch or installation has occurred.

## Owned state

All recorded source-review processes and the R53 live service/processes are
settled. Bounded review receipts remain outside the disposable review profile.
Automatic review rejected removal of the R52 runtime/temp roots and, separately,
the R47 isolated review profile before either command ran. Those exact roots
remain human-manual-only: no retry, bypass, delegation, move, parent deletion,
reuse or mutation. Audits and rejection receipts preserve the actual outcome;
no absence or recovered-free-space claim is made. Earlier protected boundaries
remain unchanged.

The fresh R73 Claude review process has also exited. Its separate 9,817,180-byte
cache removal was rejected by automatic review before execution. The exact
`.pytest-runtime/review/r73-question-routing` root is now human-manual-only, with
the same no-retry/no-reuse boundary. Its bounded verdict, prior audit and rejection
receipt are retained outside that root. The R74 timed-out MCP test's private
daemon and console helper were identified, retired and its owned test root removed.

The R61/R62/R63 case receipts record process identities and disposable-root
settlement. All recorded matching processes have exited and all tracked runtime
roots were absent after their cases. The rejected roots were not retried,
re-audited or reused during this migration batch.

R76–R79 isolated service families have exited and their disposable profiles,
Core storage and copied authentication are removed, with no original-auth or
production-source changes. R76 stopped at readiness under a pipe-based harness;
R77 exposed the harness's initial-idle race before any tool work; R78 records the
failed WebSocket attempt; R79 contains the scoped native-family proof above.
Their bounded receipts and cleanup audits remain under `.pytest-runtime/static`.
