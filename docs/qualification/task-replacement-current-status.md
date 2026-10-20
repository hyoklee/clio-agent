# Tasks replacement status

## Current qualification â€” 2026-10-20 02:19 UTC

Initial implementation and initial test construction are **done**. Current work
is regression repair and live qualification. **NO GO for merge, release or installation.**

- CI repair base: agent `b271ae0300c2be2fd0491123de2c76f2567ccdfd`,
  GACT `9bf5791c098f53f0ff5a6c9b50b6a444cb0a2446`, marketplace
  `2c172233a9f895e41f7de121a3871d282a5fc0a2`. Python 3.14.6 / Core 2.3.2 /
  FastMCP/tasks 4.1.0 / MCP 2.0.0 / Docket 0.26.2 / DSPy 3.4.0 /
  Claude SDK 0.2.159. Develop through `c3db245` is integrated, zero behind
  at the recorded October 19 23:52 UTC refresh. NDP is present.
- [Agent CI 39349269414](https://github.com/iowarp/clio-agent/actions/runs/39349269414)
  is complete: all 12 reports, **four distinct failing cases**. Each interpreter
  collected 13,338 cases with 50 exclusions; Python 3.12/3.14 had three failures,
  Python 3.13 had four. The earlier archive and explicit-idle-send failures passed.
  The remaining failures are two incomplete defer fixtures, the unregistered
  `hook_defer_cancelled` production reason, and a progress-signal test that
  allowed its watcher to enter model execution during the asserted sequence.
- One combined repair registers the actual cancellation reason, completes those
  fixtures and holds the real watcher through its existing pause control.
  R491 rejected an additional direct asyncio cancellation change: it closed the
  shared SDK connection and subsequent model controls failed. That change is
  removed completely; native MCP request-scope cancellation and the retained
  retirement boundary remain authoritative. The stronger regression now requires
  both independent work survival and a successful subsequent same-client RPC.
  Existing typed-denial, single-resolution, output and worker assertions remain.
  Scoped Ruff/format, production type checking and all nine existing guards pass.
  No local pytest/Vitest loop ran; the constructed batch goes to CI together.
- Astra found the missing reason registration and cleared the corrected source
  batch before R491. Fable R489 expired without a verdict; its owned process and
  profile were retired. Bounded final Fable R493 and Astra review are running. Source review
  does not qualify runtime behavior. Fresh actual-model Stop/waiter evidence is
  required; prepared R494 observes the real TurnRunner reservation rather than inferring
  retirement from projected task activity.
- The local computer restarted. R487's remote receipt was recovered: five actual
  Luna background Shell/Stop/ordinary-Send cycles, original handles and results,
  each retained user/future message committed once, normal service exit 0.
  Its activity predicate did **not** establish prompt physical waiter retirement.
  Do not infer that missing proof from its raw `pass=true` field. On the newly
  allocated original compute node, processes and all nine ports were absent;
  286,829,872 logical bytes plus the temporary root were removed, no archive.
- R491 is FAILED, not partial overall acceptance: two cycles completed before
  later controls hit `MCPError: Connection closed`; the third runner probe failed.
  Service exit 0 and actual cleanup are confirmed: 279,910,595 logical bytes
  removed, no remaining family processes or listeners. It does not close R3.
- R491 is FAILED, not partial overall acceptance: two cycles completed before
  later controls hit `MCPError: Connection closed`; the third runner probe failed.
  Service exit 0 and actual cleanup are confirmed: 279,910,595 logical bytes
  removed, no remaining family processes or listeners. It does not close R3.
- R482 retains its original scoped acceptance: real NDP Indexing/Download,
  602 bytes and SHA256 `0b028fd6fe6f9be231f71f1b74cbb9efeb9b6f94e8f60058910cefe008f92684`,
  five source read/hash/write-denial probes, original handles after restart,
  five ordinary and one deferred SSH cancellation cases with zero canary
  connections and normal shutdown. Its raw family failed on a nonexistent
  `session.busy` harness field; no Stop proof is inferred from that failure.
- [GACT CI 39339096564](https://github.com/iowarp/gact-tui/actions/runs/39339096564)
  passed six executed jobs; three release-event jobs were conditional exclusions.
  R471 actual-service desktop/phone controls and four published screenshots retain
  their exact bab/9bf scope: zero page/console errors, 141 aborted requests kept.
  Fixture-backed WebView is not fresh native Desktop acceptance.
- Earlier scoped acceptance and all 30 R1â€“R6 receipts retain their original
  commits. They are not a claim that all 30 ran on the current repair. Still open:
  fresh affected Stop/permission/shutdown and SPOTTER/reviewer live evidence;
  surviving approved-provider job recovery N12/W01/Q6; exclusion disposition Z02;
  final integrated review Z03. NDP streams have no surviving provider-job ID.
- Allocation 24948 is gone. New bounded allocation 24950 on ares-comp-07 owns
  custody inspection and the next family. The reusable r443 environment remains
  owned, not retired. Desktop, source credentials, defaults, released pins and
  unrelated work remain preserved. Session-recall work is queued after this goal.
- Existing automatic-review cleanup rejections remain manual-only. No retry,
  bypass, delegation or ancestor removal; no archives were created.

Receipts in the D qualification repository's `.pytest-runtime/static/` include
`ci-524-final-inventory.json`, `r488-restart-status.json`, original R487 receipt,
`r487-cleanup.json`, R482 scoped/raw/cleanup receipts, `r489-static.json` and
reviewer results. Failed and incomplete scopes remain visible.
