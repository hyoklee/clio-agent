# Tasks replacement: finite live experiments

## Current qualification — 2026-10-20 02:23 UTC

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
- Earlier scoped acceptance and all 30 R1–R6 receipts retain their original
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

## Retained experiment definitions

The following earlier execution notes retain their original dates and scopes.
They do not override the current acceptance ledger or close its open rows.

## Current execution â€” 2026-10-19 17:18 UTC

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

## Live execution checkpoint â€” 2026-10-19 16:55 UTC

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
- **Race impact:** all thirty earlier R1â€“R6 repetitions remain recorded. The new
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

## Current execution â€” 2026-10-19 06:43 UTC

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

**All 30 final runtime races passed:** R1â€“R6 each have five actual-model
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

## Pre-integration evidence â€” October 18, 22:39 UTC

Frozen product source: agent a0645c21 / GACT c813c1b7. Agent exact-head CI passed
all 24 jobs with 12,993 passes and 50 exclusions per interpreter; zero failures.
Both GACT workspace runs succeeded; conditional jobs and excluded tests remain
explicit exclusions. Matching R219 online/offline UI builds and independent
Astra/actual Claude Code/Fable source reviews passed.

R227 freshly passed actual Codex/Luna two-declared-workflow child-peer coordination:
discovery, messaging/replies, observation/subscription, expired wait, denied control,
pause, revocation-before-injection, automatic retained-reply wake after regrant and
independent owner/subscriber completion commits. Grants used authenticated human
REST. The real read-only browser opened Work, the paused child and its access view.
This does not establish root Session peers, every permission variant or full Q9.

R226/R227 services/browsers settled and disposable roots are absent. No model
family remains active at this report boundary. Earlier rejected paths remain
manual-only. The full matrix and all 30 races below remain required, along with
website walkthroughs and current-service media. R210 is predecessor-scoped SSE
recovery evidence, not a measured actual over-64-KiB line or final acceptance.

R234 adds current root Session/workflow/observe-only/privacy and actual desktop/
phone grant/revoke evidence. One root needed a recorded operator clarification
before attempting standard messaging. The same original handles completed;
one subscription commit and no root self-wake were recorded. R230 passed real
native Shell/model/physical output. R234 measured 87 real SSE lines over 64 KiB
(maximum 82,331 bytes) at the unchanged configured 1 MiB ceiling.

R228's premature-idle harness and R231's legacy-projection checker remain failed,
not product-runtime passes. Their owned data is absent. Fresh storage readers
use canonical public task/results and independent manifests/hashes; they retain
all original effect checks. All seven fresh family services and fourteen roots
are settled/absent. The remaining matrix and all 30 races still block completion.

R235 subsequently passed current Indexing model behavior and exact comparison of
all 48,098 manifest paths. Its service and two disposable roots are absent.
R232 failed source approval during agent warmup before a model/Download launch;
its service/data are also absent. R238 now approves that owned source before
binding/activating an agent, preserving the existing policy guard. Download
acceptance remains pending. Astra's documentation review requested separate
child-owner versus human-root delivery claims and explicit predecessor labels
on three retained captures; this correction batch addresses both. It changes no
task-runtime source, dependency, schema or GACT code.

## Regression and live-verification loop

1. Initial production implementation and the complete initial test set precede
   execution. Those construction milestones stay complete when verification
   finds a bug; report the bug and its repair separately.
2. Push the combined regression batch to CI. Use actual models and production
   services for live qualification while CI runs; live families are the priority.
   An unrelated pending CI job is not an automatic hold on a live family.
3. Between live families, inspect current-head CI and record failures together.
   Batch corrections in the existing owners and add meaningful regression cases
   for newly found bugs before executing their checks. Do not repair one failing
   test per push or replace live work with repeated source-review cycles.
4. Rerun affected checks and affected live scenarios after relevant changes.
   Record impact and freeze one source/runtime/UI tuple within each family;
   never modify its code mid-run. Preserve unaltered evidence from failed runs.
5. Before final acceptance, freeze the integrated candidate, pass required CI,
   complete Q1â€“Q9 and run R1â€“R6 five times each. Required failures, skips and
   unavailable routes remain visible and block completion.

Tests provide regression assurance. Actual-model execution and real-service UI
interaction provide qualification. Neither source review nor executor-only
probes substitute for that evidence. Do not weaken assertions, timeouts, worker
budgets or guards. Local focused cases, when needed, run individually and
sequentially with one worker; use CI for the complete regression run.

Record processes, descendants, ports and generated data before each launch.
After every family, retire owned processes and remove disposable state without
another permission request; force-close verified stuck descendants when needed
and report uncertainty honestly. Respect existing tool-rejected/manual-only
boundaries. Provider capacity or authentication failures block that route and
do not justify task-engine patches.

## Common setup and evidence

Use an isolated source service and actual production GACT connected to that
service. Never substitute an executor probe, synthetic transcript, fixture UI or
mock backend for a required model/provider/UI result. Use Codex/Luna for common
behavior and Claude for its distinct tool, child and delivery bridges. Relay's
special path is outside scope; ordinary external MCP Tasks remain in scope.

Before launch, record the exact core/GACT/dependency/schema/runtime/platform
tuple, selected model, available routes, owned process identities, ports and
data roots. Freeze the tuple for the family. All writable state, profiles,
caches, input files and generated output stay under the D: execution checkout.
Keep installed Desktop, credentials, defaults, released pins and prohibited or
manual-only roots untouched. Do not retry a rejected launch through another
command or host.

Use finite real work: Python commands producing timestamped lines and a final
file, an approved connected-source dataset with known bytes/hashes, and a known
folder tree with independently counted entries. Make operations long enough to
observe running work through realistic workload size/rate, without substituting
a test implementation for production execution. Failed operations have explicit
nonzero exit or real provider failure evidence; a harness verdict is not itself
a task failure.

Give the model an outcome-oriented assignment. For example: "Start this long
analysis in the background. Inspect the other input while it runs, report any
progress you can observe, and use the eventual result to finish the report."
Do not dictate an exact tool-call script to obtain a favorable trace. Record
model omissions and provider capacity/auth failures separately from product
defects. Stop the family on unavailable prerequisites; do not patch task code
to compensate for provider capacity.

The independent evidence reader correlates native acceptance, public handle,
invocation, assignment, actual model input/action, input-commit notification IDs,
backend settlement and filesystem/process outcomes. A handle appearing in a
transcript is insufficient: prove the independent action starts after its
acceptance observation and before terminal settlement. Inspect what the next
model input actually contains. Query/observe must not consume delivery, and
peer collection must not consume owner delivery.

## Nine experiment families

| ID | Actual agent experiment | Actual UI experiment | Required physical/record evidence |
| --- | --- | --- | --- |
| E1 / Q1 | Start background Shell, Download and Indexing through the same native Tasks integration; continue independent work while each is running. Include a genuine task-returning external MCP call and a valid inline MCP call. A root Session handle exists before inference; spawn a child and post an asynchronous Question to cover all seven kinds. | Work shows the same handles, short descriptions, kind and queued/running/progress. Open each row for output/details; no raw technical wall of text in the collapsed view. | One shared native mechanism, workload-specific effects: exact shell output/exit, download bytes/hash, complete manifest/count. Capture full external server/session/task identity and Session/Subagent/Question ownership. |
| E2 / Q2 | With mixed Shell/Subagent/Question/MCP work, query and observe incremental output/cursor/pattern; use any/all waits, a positive wait expiry and a zero snapshot. One member fails while others keep running. Read a settled result again. | Show mixed pending/success/failure without marking the entire collection complete early. Expand output and follow large-result references. Stop a wait while members remain active. | Per-member outcomes and pending handles; expired/cancelled waiter leaves members running; observation is non-consuming. Uncertainty returns attention plus pending, without a fabricated terminal timestamp. |
| E3 / Q3 | Complete work while the parent is busy, idle, explicitly stopped and explicitly paused. Inject human feedback between model iterations. Resume the paused parent. Repeat distinct delivery cases with Claude. Answer a Question while other work/goal dependencies remain pending. | Watch live feedback land during execution. Post Question immediately, answer through its card, and distinguish waiting from Finished. Stop leaves background work and the Question open; later completion/answer wakes the stopped agent. Pause holds execution until resume. | Busy input appears at the next eligible model call; idle/post-Stop input admits one continuation. Paused input remains pending. Stable assignment across yield; no ordinary duplicate on a later turn. Include the known empty-wake/pending-work regression. |
| E4 / Q4 | A child starts a download, yields, receives its completion and analyzes it under the same handle. Parent observes and continues other work. Exercise child pause/resume, steering, cancellation and explicit restart; control inherited predecessor work. Repeat Claude-specific child/control bridges. | Apply real human controls through identifying confirmations. Child cancel warns about descendants. Show Cancellation requested/Stopping until physical settlement. Verify the parent receives attributed intervention notices. | Model hold differs from task cancellation. Admission closes before subtree cancellation. Actual child execution and owned descendant processes/transfers settle; restart gets a linked new handle without replaying accepted work. Unknown settlement prevents successor launch. |
| E5 / Q5 | Run two independent root sessions in two distinct declared workflow executions. Discover authorized sessions, message while busy/idle, reply, observe/wait/subscribe to an exact peer handle. Attempt denied control, then revoke a grant before injection. | Grant only selected read/observe/message rights, separately opt into control/descendants, and revoke the exact grant. Open peer task details according to rights. | Distinct workflow/root/step/session provenance; human grant attribution; no model-created grant. Observe-only does not disclose assignment/output/answers. Historical handles do not retarget successors; peer collection preserves owner delivery; revocation blocks pending disclosure. |
| E6 / Q6 | Use an actual external task-capable MCP server and approved provider operation. Exercise progress-only updates, input required, partial answers, a lost input-update reply and reconnect. Collect a surviving provider job through its verified original identity. | Present input required even when the agent is idle; answer through the existing permission/question surface. Show lost visibility distinctly from failure and restore it after reconnect. | Immutable server/auth/session/task/input identity, persisted answers and original provider job ID. No repeated question for a confirmed answer, no acceptance/submission replay, no changed-content key reuse. An unavailable real backend leaves this family blocked. |
| E7 / Q7 | In disposable isolated services, interrupt before and after recipient-input commit; interrupt after a visible side effect but before result recording; temporarily lose Core and recover. Agent inspects prior effects and deliberately retries/revises with a linked new handle. Import retained-format records twice. | Display uncertainty/recording-unconfirmed honestly. Trusted pause/cancel still acts on verified work during a Core outage; new undurable submissions are refused. After recovery show one attention episode followed independently by the final outcome. | Reconstruct committed model input, retain precommit pending input, no automatic replay of uncertain commands, matching owner-local recovery flush. Migration identities/mail/results stay stable and migration submits nothing. More than 1,000 messages remain retained; positive capacity counts only undelivered peer mail. |
| E8 / Q8 | Saturate Shell's configured native capacity (default 10) and submit storage work; storage starts independently. With child inference capacity one, execute nested children/peer work while waits release inference capacity. Exercise foreground versus background Stop and worker retirement under constrained executor capacity. | Show queued versus started work and Stopping during actual worker retirement. New input remains pending; no second turn starts before the old worker exits. | Independent native roots/pools; no shared-executor starvation. Foreground Stop cancels and physically settles its process tree; background Stop preserves the task. No leaked children/listeners or unbounded worker growth after settlement. |
| E9 / Q9 | Complete an end-to-end user assignment through the real UI: start tasks, ask/answer, steer, observe, pause/resume, cancel and collect. Use production service outcomes from E1â€“E8 rather than fabricated fixtures. | Review desktop and 390-pixel phone widths: Work, Observability and Runs; progressive disclosure, clickable rows, Questions, grants, cancel confirmations, output and history. Use keyboard interaction and check viewport containment and browser errors. | Screenshots/interaction timestamps link to actual handles and server state. Cancellation has actual physical outcomes; dismissal does not cancel. Accepted user controls reach the parent. No falsely Finished waiting state, duplicate card or hidden pending input. |

E1 groups ordinary native workloads rather than treating them as three task
engines. Shell/transfer/manifest algorithms still need their own real effect
checks. E2â€“E5 reuse those tasks to exercise shared behavior; they do not add a
separate protocol matrix per workload. E6 and E7 require their own external/fault
routes because a successful local shell cannot establish those contracts.

## Final-candidate races and completion

After the relevant family passes, repeat each existing race five times on the
final tuple: R1 Stop/acceptance; R2 late-start/cancel; R3 busy-to-idle arrival;
R4 collection/automatic delivery; R5 recipient-input commit recovery; R6 subtree
cancellation/admission. These are 30 targeted race repetitions, not 30 full
repeats of every family. Assert both sides of the boundary. Repeat affected
gates after a relevant source/runtime change; do not accumulate predecessor
passes into a claim about a new candidate.

CI supplies the regression baseline. It does not replace actual-model service
acceptance or rendered UI acceptance. A failed/skipped/unavailable required gate
remains failed/blocked. No Tasks release while any required row is outstanding.

For each family, record its bounded receipt before launch and update it after
settlement. Harness diagnostic limits remain 120 seconds for native/Core cases,
600 for model scenarios and 900 for capacity/recovery families. On expiry stop
the model segment, explicitly cancel owned work and await actual settlement;
unknown custody blocks subsequent launches. Remove disposable data/profile
roots after the family, preserving only bounded receipts and selected media.
Do not change product deadlines or output/test budgets to obtain a pass.
