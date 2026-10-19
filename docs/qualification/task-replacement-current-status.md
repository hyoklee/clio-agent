# Tasks replacement status

## Active live execution — 2026-10-19 18:12 UTC

Initial implementation and test construction are complete. This phase is actual
production-service/model/UI qualification and bug repair; no local pytest/Vitest
suite ran in this execution period.

- Candidate: agent `acbe5cd4b886e8d87abc7a24b03c39b71d5a0655`, GACT
  `0463c6839ff747eed2ff8a63679ca8ef2bc2e5cb`. Python production bytes are unchanged
  from 52cc. Agent CI39296275978 passed all24jobs; each interpreter (3.12/3.13/3.14)
  reports13,081passes/zero failures/50exclusions. Allseven agent workflows passed.
  GACT workspace39296213548 passed six jobs, with three conditional publication
  job skips. Exclusions and publication skips are not executed test passes.
- This revision adds a coordinated repair batch from live findings: query reads
  use the existing confirmed passive view and finite SDK I/O resource instead of
  waiting on the durable-writer lane. Authorization and Core writing are unchanged.
  Explicit connected_data_download declarations resolve through the same builtin,
  with duplicate auto-attachment suppressed. Three new public-contract regressions
  are constructed; execution is delegated to CI. The green acbe result above is the
  baseline, not acceptance of these new repairs. Live R358 remains frozen on acbe.
- Astra and actual Claude Code/Fable independently found no source blocker in
  this batch. Their source reviews are not runtime acceptance.
- R341 passed allfive fresh R3 busy-to-idle arrival races with actual Luna,
  confirmed recipient-input commitment once, normal service exit and cleanup.
- R342 passed four R6 cases. The fifth parent omitted commands in its child
  assignment, so the child correctly asked for clarification. The raw family is
  failed, not five passes; all accepted work/processes/data were settled/removed.
- R347 on Ares/Core2.3.2 passed the scoped goal/dependency/Question contract:
  progress/partial results do not wake, feedback/answers bypass dependencies,
  one assignment, one delivery per outcome, real bytes/hashes and actual model
  judge completion. The raw controller remains failed because it demanded four
  explicit submits; three default yields plus a direct final response were valid.
  Independent evidence checks are in `r347-qualified-scope.json`; data is removed.
- R343 exercised current real UI restart, pause, held steering, resume, inherited
  descendant cancellation, Question answer and parent reports. Its driver failed
  an exact-label select lookup. R352 passed the focused desktop/phone grant,
  keyboard revocation, containment and clean-browser checks against the retained
  real service. Inspected/hash-matched website screenshots are updated locally.
  `Q9-current-ui-scope.json` states the limits; no full Q4/Q9 blanket pass.
  Independent evidence review supports the Q3/grant scopes, but found the explicit
  no-replay invocation guard did not execute after the UI assertion. That stronger
  claim is withdrawn and remains a fresh live obligation.
- R350 was an OS-command harness failure before workload effects. R353 reached
  actual cancellation but a five-second status request expired. Later readback
  found every task terminal and original processes absent. Neither family passed;
  both were physically retired and cleaned. No persistent deadlock claim or
  deadline increase follows from this evidence.
- R356 runs the same five races and five-second request budget in a node-local
  repository on allocated Ares node ares-comp-07/job24927, testing shared-storage
  latency as a hypothesis. Three repetitions passed, then the fourth hit the same
  five-second request timeout; shared storage did not explain it. The failed family
  settled and was cleaned. R357 now runs the remaining child Download/yield/wake
  experiment on the same frozen candidate; it is not yet accepted evidence. R357
  stopped before inference because explicit builtin declaration was rejected. R358
  uses the existing automatic attachment and has proved parent/child yield while
  the real original Download progresses; completion is still pending.
- All local campaign service/browser processes and R341/R342/R343 disposable
  roots are retired/absent. The failed read-only R354 helper was force-closed by
  verified ownership after memory pressure; no model work was submitted by it.
  Exact R345 credential staging deletion was automatically rejected; do not retry,
  bypass or delegate it. Existing manual-only boundaries remain intact.
- Remaining: required Q3/Q4 combinations (including child Download/yield/wake),
  Q6 real-provider work, Q7 recovery/history/effect-loss obligations, affected R6
  repetitions and final integrated adjudication. The candidate is not qualified
  for publication or daily Desktop installation.

## Current execution — 2026-10-19 17:18 UTC

Initial implementation and test construction are done. Current production source
is agent `52cc8e7bcff0a4d28347aa9beac0ac1654e00172` with GACT
`b44037fdde19568f1085da44f0c970c32f439ab0`; Python digest
`7b24b26aaf3358d867bb6dca7c65079579d0f3b2e6dd646b4a828b85d5550c44`.
This is not a release go decision.

- Actual-model R338 passed the two-workflow Q5 family. Real SSE lines reached
  85,924 bytes without parser errors under the configured 1 MiB limit. Q1/Q2/Q8
  retain their explicitly scoped evidence and source-impact records.
- R332 discovered inherited-result admission after cancellation and inaccessible
  completed-child restart. The backend correction uses the captured cancellation
  set. GACT preserves live-work queries and loads completed history on demand.
  R339 verified real UI restart/pause, then failed its navigation to Resume; it
  is not a complete lifecycle/UI pass. R343 corrects panel navigation and remains
  prepared, not executed.
- e114 CI exposed the unchanged 800-line guard. The redundant assignment
  forwarding method was removed in 52cc; the guard now passes at 783 lines,
  scoped Ruff/Mypy pass, and replacement CI is pending. No guard baseline changed.
- Matching TypeScript/online/offline UI builds passed at e114/b440; the later
  Python-only binding change leaves all UI compilation inputs identical.
- Astra and actual Claude Code/Fable cleared b440's source delta. Astra also cleared the mechanical
  52cc binding removal; neither reviewer identified a remaining source blocker. Reviews and builds do not qualify runtime.
- No local pytest/Vitest suite ran in this live campaign. Tests are in CI.
- All R332/R338/R339 service/browser processes and disposable runtime/temp roots
  are retired/absent. Current live launches are held by machine commit headroom
  below the recorded 4 GiB preflight threshold. No unrelated app was stopped.
- Remaining live work: Q3/Q4 full combinations, Q6 approved-provider work, Q7
  outage/history/effect-loss obligations, Q9 current controls and affected R3/R6
  five repetitions each. Thirty earlier races remain recorded; do not claim all
  thirty accepted on the new tuple. R341/R342/R343 have not run on this tuple.

Receipts: `Q5-current-adjudication.json`, `SSE-current-adjudication.json`,
`candidate-impact-e114b5db8.json`, `candidate-impact-52cc8e7bc.json`,
`r343-web-build.json`, `r340-claude-review.json`, `r344-claude-review.json`,
`r332-cleanup.json`, `r338-cleanup.json`, `r339-cleanup.json` in the D execution
repository. Installed Desktop/auth/defaults/released pins and manual-only
boundaries remain preserved; no merge, release, install or archive was performed.

## Live execution checkpoint — 2026-10-19 16:55 UTC

Initial implementation and test construction are complete. Live qualification and
bug repair continue. No local pytest/Vitest loop ran during this checkpoint.

- **Q5 passed:** R338 used two independent declared workflows and actual
  Codex/Luna. Discovery, busy/idle messages, unassisted replies, observation and
  expired waits, denied control and revoked reads, withheld notifications,
  automatic regrant delivery, independent owner/subscriber receipts and historical
  handles passed. Both workflow and Shell submission counts remained one. Scope:
  `Q5-current-adjudication.json`; raw `r338-live-workflows.json` passed unchanged.
- **Oversized SSE cleared:** actual provider traffic in R338 included 90 lines
  above 65,536 bytes, maximum 85,924 bytes, under the configured 1 MiB limit.
  The unchanged parser reported no errors. No synthetic stream bytes were added.
  `SSE-current-adjudication.json` clears this specific gate, not all of Q7.
- **Lifecycle/UI R332:** actual child completion left its original background
  Shell alive. API restart created a linked handle. Real UI pause/resume,
  descendant-warning cancellation and Question answering worked; original Shell
  processes physically retired, old child stayed completed, and the parent model
  reported attributed interventions and the exact answer. This is scoped evidence,
  not a family pass: the observer selected a completed foreground read Shell;
  completed-child restart was inaccessible in the UI, and cancellation of inherited
  work incorrectly admitted a new child assignment. Raw failures are retained.
- **Repair batch:** the cancellation admission check now recognizes its existing
  captured inherited-member set. GACT `048f008d` changes the same bounded evidence
  query to include completed tasks, exposing existing restart controls. New
  regression cases cover both live findings; static Ruff/Mypy passed. These repairs
  require fresh CI and affected live qualification. No new execution owner exists.
- **Previous baseline/review:** agent a61577ba6 CI passed 24 jobs, 13,079 passes
  and 50 exclusions per interpreter. Astra/Fable found no source blocker at
  a615/7260. Those results precede the repair batch and are not new-head acceptance.
- **Review follow-up:** Astra identified a P2 in the first UI correction: fifty
  historical rows could hide current work and its footer state. GACT `b44037fd`
  preserves the independent active-work query and adds optional, separately paged
  completed-work disclosure. Its regression keeps a current task visible while
  paging fifty older records and restarting a completed child. Fresh review,
  exact-head CI and a matching live UI build remain required.
- **R339:** the real UI confirmed completed-child restart and pause with background
  heartbeat continuity. The browser driver then could not reopen the Resume row
  after navigation; that family remains failed. Its source stayed frozen and
  service exited0; all fresh runtime/temp data was removed after physical audit.
- **Current resource hold:** R341 race preflight stopped before creating a service
  because available machine commit headroom fell below 4 GiB. No qualification
  services, browsers or review workers remain active. Do not count this prepared
  race family as executed. No unrelated application was stopped.
- **Race impact:** all thirty earlier R1–R6 repetitions remain recorded. The new
  post-cancellation admission correction requires affected R3/R6 repetitions and
  lifecycle verification; do not claim all thirty accepted on the new tuple yet.
- **Cleanup:** R332 and R338 services exited normally; exact process/listener
  audits passed and both fresh runtime/temp roots are absent. Cleanup receipts
  retain bounded evidence only, without archives.

Accepted scoped gates: Q1, Q2, Q5 and Q8 on their recorded tuples. Remaining:
Q3/Q4 full delivery/lifecycle combinations; Q6 approved-provider jobs; Q7 remaining
outage/history/effect-loss obligations; Q9 current UI controls, plus affected
requalification after this repair. Relay stays excluded. No release, installation,
Desktop/auth/default/pin change or retry of rejected cleanup occurred.

## Current candidate — 2026-10-19 06:43 UTC

Initial implementation and initial test construction are complete. Current work is
regression repair, independent review and live qualification. The candidate is
**not qualified or release-ready**.

- Frozen runtime candidate: **305a33e33b61f1ab8ee362c78fbd5c39794e0c6b**; subsequent documentation commits do not change the qualified runtime identity.
- Agent test correction: cc2a8086faa05672caebd7d4f19027568b8215f0.
- Agent production commit: **6c79df316273aeed0fb95230c846706f574cb834**.
- GACT UI correction: **7260f2dd0b63852333f581ce28216fa6b7d0e124**;
  completed runtime/race evidence used aca98ce477bbee1d1f14b1f384d1cf283906de6d.
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
| Previous failed CI | e4940b3be CI 39197197958 finished 23 successful jobs / one failed job. All twelve reports were inspected: the only distinct failure was Python 3.12's real launcher-lock timeout case, which raised the expected typed exception but took 3.5396 seconds against its unchanged <3-second assertion. The prior three failed cases, 1,005-message retention and A2UI load cases passed. This is not a green current-candidate baseline. |
| Previous completed CI | 4b33f858d CI 39200422623 passed all 24 jobs. All twelve XML reports inspected: 13,072 passes, zero failures/errors and 50 exclusions per interpreter. Prior lock failure and all inventoried repair cases passed. Exclusions remain exclusions. Receipts: ci-4b33f858d.json / ci-4b33f858d-summary.json. |
| Current agent CI | 305a33e33 CI 39206788536 passed all 24 jobs; twelve XML reports, 13,072 passes / zero failures/errors / 50 exclusions per interpreter. Receipts ci-305a33e33.json and ci-305a33e33-summary.json. |
| Current GACT CI | 7260f2dd workspace 39206586099 passed all six applicable jobs, including all browser and native WebView checks. Three release/event jobs were conditional skips. Fresh current-service UI R309 passed separately. |
| Current test-only correction | cc2a8086f replaces assumed lock readiness with a real held event and guarantees release/join on assertion failures. It retains the 0.5/3-second bounds, real polling/audit and exact typed assertions. Three focused cases passed individually/sequentially: unidentified holder, real holder handoff and killed-process acquisition. Astra and actual Fable returned source GO. The old 3.54-second cause remains unproven; explicit cache isolation does not establish prior interference, and fresh exact-head 4b33f858d CI now passes, without establishing the old timing cause. Receipts: r290-regressions.json / r291-claude-review.json. Its fresh test root and review diff are absent. |
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

Earlier runtime evidence: agent **305a33e33** / production **6c79df316** / GACT
**7260f2dd**. Python source digest is
`5954bc76035275f28ce666ffb031b1e4a13f49eeb3c8df31efbccb3f7816cde7`.
Initial implementation and initial test construction are complete. Qualification
and bug diagnosis continue; this is **not a release go decision**.

Current agent CI [39206788536](https://github.com/iowarp/clio-agent/actions/runs/39206788536)
passed all 24 jobs. All twelve XML reports were inspected: each Python
3.12/3.13/3.14 has 13,072 passes, zero failures/errors and 50 exclusions. Exclusions
remain exclusions. Current GACT workspace CI
[39206586099](https://github.com/iowarp/gact-tui/actions/runs/39206586099) passed
all six applicable jobs, including browser/accessibility/visual regressions,
all three native debug builds and fixture-backed native WebView proof. Three
release/event jobs were conditional skips; they are not executed tests.

**Q1 is accepted for all seven kinds.** `Q1-current-adjudication.json` links hashed
actual-model receipts for Shell, Download, Indexing, MCP, Subagent, Session and
Question, including a Session recorded before its first model input, immediate
handles followed by independent work, and valid inline MCP output. R289's original
checker failure remains preserved with its same-run ownership adjudication.

**All 30 final runtime races passed:** R1–R6 each have five actual-model
repetitions. R298 covers queued cancellation and collection/delivery; R301 covers
three before-commit and two after-commit crashes; R303 covers closing-turn arrivals;
R304 covers Stop/acceptance; R305 covers physical child/process-subtree cancellation
and closed queued admission. R305's first setup used one recorded human steering;
its other four setups were unassisted. Runtime evidence carries from 4b33f858d /
aca98ce4 through the verified presentation/documentation-only impact to the current
candidate. No agent execution owner, dependency or schema changed.

Fresh actual production-service work now includes:

- R293/R294: all 8,001 Download files / 36,124,063 bytes and hashes, and all
  48,098 Indexing manifest paths, checked exactly with invocation provenance.
- R297: ten real Shell workers occupied concurrently; storage indexed independently;
  the eleventh queued body never started; Stop left background work running.
- R307: two real Core startup migrations over nine historical fixture tasks, stable
  handles/aliases/lineage/results/pending mail/Question/disabled subscription and
  proven acknowledgements; ambiguous native alias refused; zero native replays.
  Actual Codex/Luna read retained results and collected the original Question once.
- R309: real external task visibility loss, one attention input, original-identity
  reconnect without replay, one separate final input and one backend execution.
  Current matching online/offline UI builds passed. Keyboard navigation opened
  actual task evidence at desktop and phone widths; Work/Runs and final-state
  checks passed without connected-browser errors. Two inspected/hash-matched
  captures are selected for the website. This owned protocol job is not an
  approved-provider surviving job.
- R312: actual mixed Shell/Question query, cursor/pattern progress, expired wait
  with continuing work, any-wait failure, surviving siblings and all-wait collection.
  One recorded human steering continued the omitted wait phase; no work replay.
- R316: actual native external input, two sequential human answers, persisted partial
  response, one lost accepted update reply, original identity, one backend effect
  and one final model delivery. The old observer wrongly expected simultaneous
  Questions; a separate operator completed the same frozen accepted run. Raw
  observer state is preserved. API/proxy/server retired normally with exit zero.
- R317: while the actual owned Core daemon was suspended, Pause returned in about
  four milliseconds, Cancel in about seven, and both native processes retired
  before Core resumed. The message client timed out with an uncertain reply;
  this does not establish the new-admission rejection gate. Raw failure is retained.

Remaining live obligations are still explicit. R315 reached both nested parent
waits, a yielded leaf without a worker and successful independent same-depth child
execution under a one-worker finite-I/O executor and one child inference slot per
depth. The peer root and later leaf model calls returned actual provider-overloaded
errors; deliberate peer continuation succeeded without replay. The clean successful
leaf-answer family remains blocked, not passed. R314's default agent-audience input
route also left cancellation/shutdown unresolved after an unrelated harness error;
owned processes were force-retired and uncertainty retained. Astra and actual
Claude Code/Fable are diagnosing that route. Provider errors are not task-engine fixes.

**Live-discovered cancellation repair under construction:** actual Claude Code/Fable
R319 independently confirmed R314's four-way input/cancellation wait cycle. A late
input Question escaped the cancellation member snapshot, blocked the SDK input
phase and prevented subsequent terminal polling. The patch reuses the existing
Question command and cancellation admission barrier: late inputs persist a cancel
response without posting a Question; external cancellation closes already-posted
inputs through its recoverable intent. Confirmed answers remain unchanged. No new
scheduler, driver or shutdown deadline is added. Four constructed regression cases
(two cancellation scopes, pending input closure and confirmed-answer retention)
will run in CI; no local pytest/Vitest loop was executed. Scoped Ruff/format,
Mypy and removal/size/class guards passed. R320 passed all ten actual-model cancellation races (five subtree, five individual)
on ffc974100, with no late Questions and normal service shutdown. Astra then found
a distinct persistence gap: a confirmed Question answer could be replaced before
its callback checkpoint. The follow-up reads that authoritative answer first,
preserves accepted control recording across later grant revocation, and expands
constructed coverage to seven cases. The follow-up requires fresh CI and affected
live recovery acceptance. The first CI inventory found one new-test contract
error: task_handles returns a set, while the test expected a tuple. Both matching
identity/count assertions now compare the exact singleton set; no production
behavior, timeout or assertion strength changed. No local pytest loop was run. R321 normal input was provider-blocked after acceptance;
its already accepted native operation completed without replay, but that does not
pass the model gate.

Both reviewers found no blockers in the specific GACT 7260f2dd correction; that
source assessment is not candidate or release clearance. Remaining recovery,
agent lifecycle/workflow, capacity and full UI obligations, approved-provider
access and required unavailable cases still prevent qualification. R318 passed
an actual-model uncertain-wait check: the original handle remained pending, no
final result was consumed, and a later final outcome arrived once. Q2 is now
accepted by Q2-current-adjudication.json, alongside Q1 and all thirty races. Relay remains excluded.

Receipts live in the D execution repository's `.pytest-runtime/static` directory:
`ci-305a33e33.json`, its summary, `Q1-current-adjudication.json`,
`final-races-4b33f858d.json`, matching qualified-scope/cleanup receipts, and
`r315-final-assessment.json` / `r316-input-adoption.json` / `r317-live-native.json`.
All retired fresh roots are being removed after physical process/listener proof.
Earlier rejected/manual-only targets, installed Desktop/auth/defaults/pins and human
work remain preserved. No archive, merge, release or installation was performed.

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
- Q1–Q9, final migration/recovery obligations remain incomplete; **25/30 final race repetitions** pass, and R6 also passed five repetitions in R305. The finite obligations remain in the acceptance ledger and
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
R292–R304 completed runtime families and failed harness preflights have absent fresh
roots. R305 is settled and both fresh roots are absent. R295 retains honest unconfirmed
Core settlement; independent process/port proof establishes physical retirement.
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
