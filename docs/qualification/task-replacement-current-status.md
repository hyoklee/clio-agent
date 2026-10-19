# Tasks replacement status

## Current candidate — 2026-10-19 02:54 UTC

Initial implementation and initial test construction are complete. Current work is
regression repair, independent review and live qualification. The candidate is
**not qualified or release-ready**.

- Agent production commit: **4f34bb9b9a7179b77c06e0389f1ba3427bc6045a**.
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
| Latest completed CI | b1bdb185 CI 39188351574 finished with 16 successful and eight failed jobs. All twelve XML reports were inspected. Seven distinct failures: five new observer cases failed in fixture setup; two permission cases exceeded their existing worker joins. The combined correction requires fresh CI. |
| Observer regression repair | 1af8c193 corrects the fixture to the actual session-creation 200 response. All five real-Core cases passed individually/sequentially on Windows with one worker: cold/output-free and file-output provenance, loop responsiveness/context return, start/completion cancellation retirement, interleaved identities. Receipt: r265-regressions.json. |
| Permission defect reproduction | Both immediate Allow and Deny cases failed before correction on 201087574: a pending row was visible before its wake event existed. Receipt: r268-regressions.json. |
| Permission correction | eac7759b registers the existing event before publishing the row. The original permission scenarios now wait for actual permission.requested publication, keep their existing 2/5-second joins and ten-second collection limit, capture worker stacks on failure, and retire the MCP worker before closing its executor. All six affected cases passed individually. Fable found equivalent folder/network publishers, also corrected without adding owners. All seven final cases then passed, including immediate tool/folder/network answers, fail-closed publication rollback, and unconditional executor teardown. Receipts: r269-regressions.json / r272-regressions.json. |
| Scoped static checks | Ruff/format, Linux Mypy on the changed production file, removal guard (zero violations), size guard and class guard passed. No assertion, worker count, timeout or guard budget was weakened. Receipts: r271-scoped-checks.json / r273-scoped-checks.json. |
| GACT | aca98ce4 workspace runs 39176860551 / 39176857453 succeeded, with conditional release jobs excluded. Native WebView CI is fixture-backed. Matching R245 UI build is retained in place; the current changes do not alter GACT/compiler/dependencies. |

Full CI inventory: ci-b1bdb185-complete.json. Original failures remain recorded.
Fifty historical exclusions per interpreter are not passed tests or live evidence.

## Independent review

Astra and actual Claude Code/Fable returned source GO for b1bdb185 / aca98ce4.
Astra identified the permission registration race while reviewing the complete CI
inventory; the CI traces alone do not prove either original join failure hit it.
Astra found a test-teardown blocker and Fable found the two equivalent publishers. Those findings are corrected in 4f34bb9b. Both reviewers returned source GO for that correction (Astra turn 01a1520f-c34a-7f63-a00c-9a5ae2852fcc; actual Fable receipt r274-claude-review.json). Fable records non-blocking gaps in immediate folder-approval/defer coverage and pre-existing expiry-event retention; these are not represented as new passes.
Reviews are read-only and do not substitute for executed tests or live acceptance.

## Live evidence and remaining qualification

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

## Custody and cleanup

R263's service exited zero, both sessions had no remaining active task, source and
original authentication hashes were unchanged, and both fresh roots are absent.
Its physical cleanup measured 311,712,911 logical bytes. Receipt: r263-cleanup.json.
R257/R258/R261/R266 also have confirmed service retirement and absent fresh roots. R266 cleanup measured 310,022,310 logical bytes. The R268/R269/R272 test roots, including their zero-byte Unix sockets, are absent; receipts record each exact root.

The five R265 tests exited zero and their run data was removed by the test owner.
Five zero-byte Core socket/reparse entries remained. Automatic approval rejected
that exact cleanup command before execution; r265-alias-cleanup-rejection.json
records the new manual-only boundary. It will not be retried or bypassed.
Other prior-rejected paths remain untouched. The current exact path/size inventory
is TASKS-CLEANUP-LIST-2026-10-18.md in the D execution repository.

All new test/live data remains inside the D execution repository. No archive or
backup was created. Installed Desktop, authentication/defaults/released pins,
human source changes and unrelated sessions/processes are preserved.
