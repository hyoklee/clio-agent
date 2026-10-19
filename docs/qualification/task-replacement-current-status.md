# Tasks replacement status

## Current candidate — 2026-10-19 04:37 UTC

Initial implementation and initial test construction are complete. Current work is
regression repair, independent review and live qualification. The candidate is
**not qualified or release-ready**.

- Agent test correction: **cc2a8086faa05672caebd7d4f19027568b8215f0**.
- Agent production commit: **6c79df316273aeed0fb95230c846706f574cb834**.
- GACT: **aca98ce477bbee1d1f14b1f384d1cf283906de6d**.
- Both repositories retain `codex/agent-facing-async-tasks`; no merge, release or
  daily Desktop installation has been performed.
- Integrated agent develop: cee026de3; GACT main: f2b96308.
- Runtime: Python 3.14.6, iowarp-core 2.3.2, DSPy 3.4.0, FastMCP/Tasks 4.1.0,
  MCP 2.0.0, Docket 0.26.2, Claude SDK 0.2.159.
- Marketplace: 2c172233; schema 0.6.0b14 / 3224a797.

## Regression evidence

| Gate | Current result |
| --- | --- |
| Completed historical baseline | 0593f40a CI 39179068184 passed all 24 jobs. Twelve XML reports: each Python 3.12/3.13/3.14 had 13,062 passes, zero failures/errors, 50 exclusions. All nine earlier repair cases passed per interpreter. This is a baseline, not acceptance of later changes. |
| Previous failed CI | 1a0881055 CI 39192188767 finished with 20 successful and four failed jobs. All twelve XML reports were inspected. Three distinct failures: two cancellation tests asserted a child task's ContextVar cleanup in the parent task; one context-steering case failed before entering its first model call. The completed Docker, Document runtime, Pages, schema and Linux/Windows/macOS packaged-startup workflows all succeeded. |
| Previous green CI | 69d1a8696 CI 39195215077 passed all 24 jobs. Twelve reports: each Python 3.12/3.13/3.14 had 13,072 passes, zero failures/errors and 50 exclusions. This precedes the prompt correction. |
| Latest completed CI | e4940b3be CI 39197197958 finished 23 successful jobs / one failed job. All twelve reports were inspected: the only distinct failure was Python 3.12's real launcher-lock timeout case, which raised the expected typed exception but took 3.5396 seconds against its unchanged <3-second assertion. The prior three failed cases, 1,005-message retention and A2UI load cases passed. This is not a green current-candidate baseline. |
| Current test-only correction | cc2a8086f replaces assumed lock readiness with a real held event and guarantees release/join on assertion failures. It retains the 0.5/3-second bounds, real polling/audit and exact typed assertions. Three focused cases passed individually/sequentially: unidentified holder, real holder handoff and killed-process acquisition. Astra and actual Fable returned source GO. The old 3.54-second cause remains unproven; explicit cache isolation does not establish prior interference, and the correction does not clear CI until a fresh run passes. Receipts: r290-regressions.json / r291-claude-review.json. Its fresh test root and review diff are absent. |
| CI repair scope | 69d1a8696 checks cancellation cleanup inside the cancelled child, explicitly seeds/verifies the parent's independent value, and verifies the exact structured result. Token-balanced fixtures isolate direct artifact producers. The steering case uses the existing fake-model barrier, keeps its three/five-second budgets and records actual input-commit/readiness/worker diagnostics on failure. All three previously failed cases and three artifact cases also passed locally, individually/sequentially. Receipt: r278-regressions.json; its fresh root is absent. |
| Observer regression repair | 1af8c193 corrects the fixture to the actual session-creation 200 response. All five real-Core cases passed individually/sequentially on Windows with one worker: cold/output-free and file-output provenance, loop responsiveness/context return, start/completion cancellation retirement, interleaved identities. Receipt: r265-regressions.json. |
| Permission defect reproduction | Both immediate Allow and Deny cases failed before correction on 201087574: a pending row was visible before its wake event existed. Receipt: r268-regressions.json. |
| Permission correction | eac7759b registers the existing event before publishing the row. The original permission scenarios now wait for actual permission.requested publication, keep their existing 2/5-second joins and ten-second collection limit, capture worker stacks on failure, and retire the MCP worker before closing its executor. All six affected cases passed individually. Fable found equivalent folder/network publishers, also corrected without adding owners. All seven final cases then passed, including immediate tool/folder/network answers, fail-closed publication rollback, and unconditional executor teardown. Receipts: r269-regressions.json / r272-regressions.json. |
| Live prompt defect and correction | R276's actual runtime toolsets included messaging, but its root model twice refused the reply as undeclared. The canonical orchestration briefing presented the shorter blueprint list as the declared tool surface. A constructed regression failed before correction on db8c009aa. 6c79df316 distinguishes blueprint tools from the actual runtime catalog while preserving role, permissions, evidence and tool-less-parent boundaries. All three affected briefing/stability cases passed; Ruff/format, scoped Linux Mypy and removal/size/class guards passed. Receipts: r280-regressions.json, r282-regressions.json, r284-scoped-checks.json. No task engine, grant, dependency or GACT change was made. |
| Scoped static checks | Ruff/format, Linux Mypy on the changed production file, removal guard (zero violations), size guard and class guard passed. No assertion, worker count, timeout or guard budget was weakened. Receipts: r271-scoped-checks.json / r273-scoped-checks.json. |
| GACT | aca98ce4 workspace runs 39176860551 / 39176857453 succeeded, with conditional release jobs excluded. Native WebView CI is fixture-backed. Matching R245 UI build is retained in place; the current changes do not alter GACT/compiler/dependencies. |

Full CI inventories: ci-b1bdb185-complete.json / ci-1a0881055-complete.json /
ci-69d1a8696-complete.json / ci-e4940b3be-complete.json.
Original failures remain recorded.
Fifty CI exclusions per interpreter are not passed tests or live evidence.
R285 separately executed all ten Windows-only cases individually: ten passes, zero
skips, including actual process-tree reaping and native long paths. This resolves
those platform regressions, not model acceptance or the remaining exclusions.

## Independent review

Astra and actual Claude Code/Fable returned source GO for b1bdb185 / aca98ce4.
Astra identified the permission registration race while reviewing the complete CI
inventory; the CI traces alone do not prove either original join failure hit it.
Astra found a test-teardown blocker and Fable found the two equivalent publishers. Those findings are corrected in 4f34bb9b. Both reviewers returned source GO for that correction (Astra turn 01a1520f-c34a-7f63-a00c-9a5ae2852fcc; actual Fable receipt r274-claude-review.json). Fable records non-blocking gaps in immediate folder-approval/defer coverage and pre-existing expiry-event retention; these are not represented as new passes.
Reviews are read-only and do not substitute for executed tests or live acceptance.
Both reviewers also returned source GO for 69d1a8696's test correction (Astra turn
01a15235-4972-7c80-8e39-986fd8dcced3; actual Fable receipt r279-claude-review.json)
and 6c79df316's canonical prompt correction (Astra turn
01a15241-ad71-76d3-8238-e2507e8ee3f1; actual Fable receipt r283-claude-review.json).

## Live evidence and remaining qualification

- R275 passed the scoped actual Codex/Luna child-peer scenario across two declared
  workflows: exact addressing, messages/replies, observation/subscription/expired
  wait, denied control, revocation-before-injection, regrant wake, and independent
  owner/subscriber completion inputs. One root explicitly yielded after reporting
  completed workflow work and needed one logged human completion instruction;
  this is assisted evidence. It kept its original assignment and did not replay
  the workflow. All 23 observed calls had canonical Core transforms. Service
  exit was zero, tasks were settled and both roots are absent. Receipts:
  r275-live-workflows.json / r275-qualified-scope.json / r275-cleanup.json.
- R276 failed the root-peer reply prerequisite, including after one logged
  clarification. Its actual runtime catalog and model refusals established the
  prompt contradiction; it is not a full Q5/Q9 pass. Before failure, real desktop
  grant controls and observe-only redaction worked. The unchanged native SSE
  parser accepted 66 actual lines above 65,536 bytes, maximum 77,577, at the
  configured 1,048,576-byte limit; no observation callback errors occurred.
  The observe-only notify=false subscription error matches the existing
  read-plus-observe contract and requires no engine change. The service exited
  zero with no active tasks; 316,446,107 logical bytes of fresh data were removed.
  Receipts: r276-live-workflows.json / r276-actual-toolsets.json /
  r276-qualified-scope.json / r276-cleanup.json.
- R281 passed its programmed root-workflow/UI checks on 6c79df316. Its model ended
  one reply instruction with an intention instead of a tool call; one follow-up
  is logged, so this is assisted evidence. The same original root handles then
  completed, a reply stayed pending through revocation and was automatically
  admitted after regrant, the root owner had zero self-completion inputs and
  its peer subscriber had one. All 24 observed calls had canonical transforms;
  47 actual recipient-input commits are retained. The real desktop/phone UI
  exercised grant/revoke, keyboard control preview and viewport containment,
  with zero page or connected-console errors. The native parser accepted 99
  actual lines above 64 KiB, maximum 80,998 bytes, at its configured 1 MiB limit.
  The service/browser exited zero, tasks were settled and both fresh roots are
  absent (323,574,118 logical bytes removed). Receipts: r281-live-workflows.json /
  r281-qualified-scope.json / r281-cleanup.json. Three inspected, hash-matched
  captures replace the website's root-session access walkthrough images;
  r281-media.json records their identity. Full Q5/Q9 and unassisted peer reply
  remain separate obligations.
- R288 freshly demonstrated actual Codex/Luna background Shell acceptance, a
  running handle followed by independent work, progress, an expired wait, terminal
  collection, exact 45-step output and one owner completion input on e4940b3be.
  The original checker failed after execution with a NameError; the same captured
  evidence was adjudicated without replay. Its warning about a missing sandbox
  startup temp directory is retained. Service exit was zero and both roots are
  absent. Receipts: r288-live-native.json / r288-adjudication.json / r288-cleanup.json.
- R289 freshly demonstrated actual Codex/Luna parent/long-child execution: an
  immediate Subagent handle, independent parent work while the child ran, exact
  native Shell output, terminal child-owned Core record, public parent query,
  one parent completion input and verified PID/birth retirement. Parent/child
  observed-call transforms matched 8/8 and 1/1. Its original checker searched
  only parent-owned records; the correct captured child scope was adjudicated
  without replay. Raw failure and the sandbox startup warning remain visible.
  Service exit was zero and both roots are absent (312,389,060 logical bytes
  removed). Receipts: r289-live-native.json / r289-adjudication.json /
  r289-cleanup.json. This is not pause/restart/cancellation acceptance.
- R261 used actual Codex/Luna SSE and production run_server. Its outcome-led
  Download mission completed 8,001 files / 36,124,063 bytes with every selection,
  file hash and published manifest checked. It supplied all five durable semantic
  transform traces. Its original first-chunk Core capture failed after rollover;
  that failed capture remains recorded rather than promoted to a full pass.
- R265's real-Core regressions now execute the canonical multi-chunk event reader.
  Full actual-model provenance acceptance on the final production tuple remains due.
- R263 used actual Claude Haiku/SDK and production run_server. The idle Question
  case completed its visible answer/wake/follow-up checks. The second case first
  invented a handle, recovered, then claimed an independent file read without
  making that call and entered a valid Question wait. The harness was still
  waiting for the read prerequisite, so its model diagnostic expired before Stop.
  This does not establish a dispatch or wait-deadline defect. Full final Core
  assertions did not execute. Receipts: r263-live-native.json / r263-diagnostic.json.
- R266 passed the actual Claude Haiku/SDK Stop/Question checks on production
  run_server: the real wait was stopped, model ownership retired, the Question
  stayed open, and its answer automatically woke the original assignment. Core
  confirmed one answer input. A later human turn created a linked successor
  without another Question or duplicate answer. The model used the queued answer;
  it did not make an explicit get_task_result call, so that control is not claimed
  by this family. Every successful observed call had its canonical Core transform.
  The service exited zero with no active tasks; both fresh roots are absent.
  Receipt: r266-live-native.json / r266-cleanup.json. The source impact from eac7759b
  to 4f34bb9b is limited to folder/network approval order and failed-publication
  rollback, outside this scenario's Question/Stop/input path. This carries the
  scoped proof, not the whole Q3 matrix. The original resource rejection remains
  recorded; the later launch had more than twelve GiB commit headroom.
- Q1–Q9, final migration/recovery obligations and all **0/30 final race repetitions**
  remain unaccepted. The finite obligations remain in the acceptance ledger and
  live experiment sheet; narrow proofs do not pass whole rows.
- R252 supplied six inspected website views at desktop/phone widths, keyboard
  disclosures and clean browser output. This is documentation evidence, not Q9
  production-service acceptance.
- The approved external-provider surviving-job prerequisite is unavailable in
  the checked standard Windows and legacy CLIO profiles: neither contains a
  storage credential file. The existing profile/receiving collection has been
  requested; no login, refresh or original credential modification was attempted.

## Custody and cleanup

R263's service exited zero, both sessions had no remaining active task, source and
original authentication hashes were unchanged, and both fresh roots are absent.
Its physical cleanup measured 311,712,911 logical bytes. Receipt: r263-cleanup.json.
R257/R258/R261/R266 also have confirmed service retirement and absent fresh roots. R266 cleanup measured 310,022,310 logical bytes. The R268/R269/R272 test roots, including their zero-byte Unix sockets, are absent; receipts record each exact root.
R275/R276 and R278/R280/R282 fresh roots are absent. R279/R283's fresh review-diff
files were removed; their earlier manual-only review profile was preserved.
R281's service/browser are retired and both fresh roots are absent.
R285/R288/R289/R290 fresh roots are absent; R291's fresh review diff is removed.
The earlier manual-only review profile remains preserved.

The five R265 tests exited zero and their run data was removed by the test owner.
Five zero-byte Core socket/reparse entries remained. Automatic approval rejected
that exact cleanup command before execution; r265-alias-cleanup-rejection.json
records the new manual-only boundary. It will not be retried or bypassed.
Other prior-rejected paths remain untouched. The current exact path/size inventory
is TASKS-CLEANUP-LIST-2026-10-18.md in the D execution repository.

All new test/live data remains inside the D execution repository. No archive or
backup was created. Installed Desktop, authentication/defaults/released pins,
human source changes and unrelated sessions/processes are preserved.
