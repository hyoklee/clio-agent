# Tasks replacement status

## Current qualification — 2026-10-20 00:35 UTC

Initial implementation and initial test construction are **done**. Work remains
regression repair and qualification. **NO GO for merge, release or installation.**

- Repair base agent `b50fc3dc1ffd1d380bccfd8d5c3cd8b01362b1bd` had production
  source identical to `bab261dbf201ba5db5d8b2097d309944e87215f2`. GACT is
  `9bf5791c098f53f0ff5a6c9b50b6a444cb0a2446`, marketplace
  `2c172233a9f895e41f7de121a3871d282a5fc0a2`. Python 3.14.6 / Core 2.3.2 /
  FastMCP/tasks 4.1.0 / MCP 2.0.0 / Docket 0.26.2 / DSPy 3.4.0 /
  Claude SDK 0.2.159. The new repair below is not yet live-qualified.
- `develop` through `c3db245cc8d6f20cd9987293377d94d6955d348b` is merged;
  zero behind at the recorded October 19 23:52 UTC refresh. NDP is present.
  Its optional tools activate through workspace source selection.
- [Agent CI 39344604388](https://github.com/iowarp/clio-agent/actions/runs/39344604388)
  finished: all 12 interpreter/shard reports identify five distinct failing
  cases: four archive fixtures missing the complete export application and one
  Stop/explicit-idle-send race. The complete existing export fixture is reused;
  idle sending now classifies a single TurnRunner reservation snapshot.
  New regressions cover both a held empty reservation and its retirement.
  These are one combined batch; no local pytest/Vitest loop ran.
- R477 used actual Luna and the production NDP adapter. One Indexing and one
  Download completed, with independent model work. The real file has 602 bytes,
  SHA256 `0b028fd6fe6f9be231f71f1b74cbb9efeb9b6f94e8f60058910cefe008f92684`.
  Five approved-source Shell probes read/hash-checked it and were denied writes;
  all published copies matched. Normal first-service restart retained original
  handles and results without replay. NDP direct streaming has no surviving
  provider-job identity; it does not close N12.
- R477's four SSH approval/cancel cases passed. Its fifth case delegated work
  to a child the harness's root-only permission query missed. The raw family
  failed. Cleanup exposed a real short-RPC permission-worker retirement bug;
  normal second-service shutdown did not finish. Thread/async stacks were
  captured, then the exact owned service/Core processes were force-closed.
  Both family data roots were subsequently removed, with process/port absence
  receipts. No normal-shutdown or fifth-cycle acceptance is inferred.
- The repair retains a claimed short RPC until its actual server worker exits
  and shares cancellation-aware permission waiting across tool, folder and
  PreToolUse deferral paths, retaining their configured answer deadlines.
  Constructed regressions cover actual SDK cancellation/worker retirement,
  pre-execution authorization failure and original cancellation-token custody.
  The same audit adds cancellable SPOTTER clearance without cancelling its
  independent watcher, and physical AI-review worker retirement with inherited
  turn cancellation. The verdict deadline still decides timeout escalation.
  Astra cleared the final combined source batch; Fable R483 cleared its
  production changes and identified the corrected reason-set fixture. A final
  focused Fable progress-poll supplement is running. Source review does not
  qualify runtime behavior. No local pytest/Vitest cases have executed.
- [GACT workspace CI 39339096564](https://github.com/iowarp/gact-tui/actions/runs/39339096564)
  passed six executed jobs; three release-event jobs were conditionally
  excluded. Fixture-backed WebView is not fresh native Desktop acceptance.
  R471 actual-service desktop/phone UI and human controls passed on bab/9bf;
  zero page/console errors, 141 aborted requests retained, physical cleanup
  and service exit 0. Four selected current screenshots are published in site.
- R447/R449 staged peer capacity and goal/Question input, R453 Indexing reuse,
  R455 active-child shutdown, R461 two-start migration and R463 actual-model
  legacy collection retain their accepted scopes and original source IDs.
  The 30 earlier R1–R6 repetitions retain their recorded scopes, not a claim
  that they all ran on this commit. This repair changes cancellation and idle
  submission: affected R3/M07 and permission/Stop/shutdown paths require fresh
  production/model evidence and reviewer source-impact disposition.
- Still required: current repair CI/live acceptance; approved surviving-provider
  job recovery/cleanup (N12/W01/Q6); exclusion disposition (Z02); integrated
  source/evidence review (Z03). Fifty interpreter exclusions remain exclusions,
  not passes or waived gates. No earlier green CI qualifies the current head.
- Ares jobs 24940 and 24946 are absent. The reusable owned r443 source/runtime
  environment remains registered for the next campaign; no product service is
  active. R477 disposable state is gone. Daily Desktop, original credentials,
  defaults and released pins remain preserved. No archives were created.
- Earlier automatic-review cleanup rejections remain manual-only, including
  R465/R470 browser roots/token files and ci-bef-reports. Never retry, bypass,
  delegate or remove them through an ancestor.

Bounded receipts in the D qualification repository's `.pytest-runtime/static/`:
`ci-b50-inventory.json`, `r477-scoped-evidence.json`, original R477 raw failure,
shutdown stacks, `r479-force-retirement.json`, `r477-cleanup.json`, R471 UI and
cleanup receipts, and independent reviewer receipts. They preserve failures
and scope; they do not turn partial acceptance into overall qualification.
