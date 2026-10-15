# R31 source corrections and qualification boundary

This follows core `cf583134` with GACT `30df56ed` and marketplace `9257bba5` unchanged. It addresses the independently reviewed ordering and resource-retirement defects in the existing owners. It adds no task registry, scheduler, mailbox authority or execution driver.

Scoped Ruff, formatting, Mypy over the 23 changed production files, removal guard, file-size ratchet, class-in-function guard and hidden-swallow guard pass. Initial type/size/lint findings were corrected without increasing a guard threshold. The application file ratchet decreased from 2,314 to 2,308 lines. These are static checks only.

| Correction | Existing owner | Fresh behavior evidence |
| --- | --- | --- |
| Enter and leave native SDK lifespans from the same application lifespan task; share readiness through a future. | Application lifespan and native resources | The earlier real SDK teardown failure is retained. The corrected lifecycle has not been executed. |
| Settle effects before closing dependent resources; attempt independent cleanup and report grouped errors. Unwind partial startup through the same close path. | Runtime/native resource owners | New source; unexecuted. |
| Bind Stop approval to the exact saved result/context. An explicit completion disposition cannot bypass an approval. | Conversation assignment and Question | Strengthened captured-output and epoch regressions; unexecuted. |
| Persist the original plan/assignment binding; install its gate before posting an answerable Question. Recover an interrupted header without another Question or input. | Question commands and plan resolution | Fresh installation-fault, early-posting and self-approval regressions; unexecuted. |
| Use the same authorized native answer renderer for automatic input and explicit collection, under their existing recipient-input commitment. | Question presentation and step recorder | Native-image automatic/explicit cases and no-extra-mail assertions; unexecuted. |
| Permit external human waits without allowing agent self-wait deadlock. Retire old activity after context clearing without reinstalling old context. | Task operations and conversation assignment | Human/agent wait distinction added; execution pending. |
| Clear matching volatile cancellation holds, unused fanout resources, and only the cancelled assignment's Question gate. A cancelled approval creates no plan instruction. | Existing conversation controls | Source correction; cancellation/retirement regressions remain required. |
| Await the tool's existing result notification before checking physical thread retirement. | Owned tool execution | Source correction; execution pending. |

The retained artifact fixture now records assignments through the production Core history rather than the deleted registry. Its pagination assertions remain intact. The earlier SDK failure and its exact environment remain recorded rather than replaced with a passing claim.

## Storage rule

The shared pytest runtime now defaults to `<checkout>/.pytest-runtime/`. Overrides must resolve to a strict descendant of that checkout; an external absolute path, `..`, the checkout itself, or a resolving link outside it is refused. Existing run identities, private Core paths, redirected temp/cache variables and end-of-run cleanup remain in place. Regression cases were updated and expanded without running them.

No further Core or product qualification may run from the C: checkout. A D: repository is required, with its environment and generated state inside that repository. Source files and the three protected human design documents remain preserved.

The C: check-cache cleanup and old qualification-root removal were rejected by automatic approval review as `blocked by policy`; neither command ran. Those actions are not retried or bypassed. Two older manual-only Core processes remain untouched. Small cleanup audit/rejection receipts are under the primary D: repository's `.git/codex-owned-cleanup/`; static-check caches are under its `.git/codex-owned-checks/`.

## Remaining acceptance

This is source implementation, not runtime acceptance. R31 behavior tests, the SDK lifecycle retry, F03 realistic tool-volume/replay/index/memory measurements, current-head CI, and the replacement Q1–Q9/R1–R6 live matrix remain unqualified. The prior R30 checks do not qualify these changes. Independent source review must be renewed at the committed revision. Nothing here authorizes release, installation, changes to authentication/defaults, a blocked launch, or deletion of a protected/manual-only path.
