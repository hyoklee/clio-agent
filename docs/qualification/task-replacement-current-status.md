# Tasks replacement status — October 15

## Source and deadline

Both independent reviewers accept the production source at core
`e581cfd504d16ca4abc3e7c1c4ed1ea1f642e2be`. GACT is
`0a4ca5d5915a0add61cd5048b742161092468481`; marketplace is
`1a9b8d0337217950a2b44c303a8d22547d52d756`.
The runtime tuple remains FastMCP/fastmcp-tasks 4.1.0, MCP 2.0.0,
Docket 0.26.2, Python 3.14.6 and iowarp-core 2.3.1.

The two-hour checkpoint was 21:45:05 UTC / 4:45:05 PM Chicago. It remains
**UNDONE**: Fable's last source verdict arrived at 21:45:08.409 UTC.
The one-checkpoint automation is paused. Source acceptance afterward does not
retroactively satisfy that deadline or qualify a release.

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

Bounded D execution-repository receipts are under `.pytest-runtime/static/`:
`r56-reviewed-source.json`, `implementation-deadline-current.json`,
`r57-current-retired-bindings.json`, `r57-test-migration.json`,
`r58-test-migration.json`, `r60-test-migration.json`, `r61-test-migration.json`,
`r62-test-migration.json`, `r63-provider-setup-migration.json`,
`r60-retired-test-bindings.json` and `r63-migration-custody.json`.

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

The R61/R62/R63 case receipts record process identities and disposable-root
settlement. All recorded matching processes have exited and all tracked runtime
roots were absent after their cases. The rejected roots were not retried,
re-audited or reused during this migration batch.
