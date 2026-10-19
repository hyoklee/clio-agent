# Tasks replacement: finite live experiments

## Live execution checkpoint — 2026-10-19 15:53 UTC

Candidate: **agent a61577ba6 / GACT 7260f2dd**. The D service ran source
`efe47301bd4ce51f2517cc74f6e832ea991edf81`; a615 changes only tests/reporting.
Production digest: `3d297de0ec9afc791d77cfc5416ade9efaa912a00a6068975859d10b19ba4024`.
Initial implementation and test construction are done. Qualification is incomplete.

- **CI:** all seven workflows succeeded, including all 24 CI jobs. Twelve XML
  reports show 13,079 passes / 50 exclusions per Python 3.12, 3.13 and 3.14, with
  zero failures/errors. Exclusions remain exclusions. Receipt: `ci-a61577ba6.json`.
- **Accepted live gates:** Q1, Q2 and Q8, with explicit source impact recorded in
  `candidate-impact-a61577ba6.json`. All thirty R1–R6 repetitions remain recorded
  on their original frozen native/conversation runtime. Only the external MCP
  input/control owners changed afterward; affected input paths were requalified.
- **Fresh Claude native input:** R325 passed immediate handle, independent work,
  two sequential answers, partial persistence, one lost accepted update response,
  original identity, one backend effect and one final model delivery.
- **Fresh recovery:** R326 passed five intentional crashes after a confirmed
  Question answer and before its callback copy, followed by original-identity
  reconnect and cancellation. The original answer survived all five. Input-key
  iteration order is unspecified; the scripted operator answered an already-ready
  second key in two cases. No task was replayed. Five intentional exits86 and a
  final normal exit0 are evidence of the controlled faults, not native crashes.
- **Capacity:** R329 completed all five actual models with child inference one,
  finite executor one, independent peer progress, no worker for the yielded leaf,
  original assignment handles and one answer/result input at each parent. Its raw
  later action-order assertion remains failed; `r329-qualified-scope.json` accepts
  only capacity. Q8 also uses R297 pool isolation and R305 physical settlement.
- **Cleanup:** R325/R326/R327/R329 services and descendants are physically retired;
  fresh runtime/temp roots are absent, including R330/R333. Raw receipts remain
  bounded; no archives.
- **Workflow evidence:** R333 ran two distinct declared workflows, captured a
  peer message while its recipient waited on real Shell work, received its
  unassisted reply, reported a timed-out peer wait and denied agent cancellation,
  then withheld pending peer/final notices after revocation. Its raw run failed
  because the harness incorrectly expected the authenticated human API to lose
  access to the human's result. `r333-qualified-scope.json` preserves only the
  passed scopes. R336 tests the denied read through the actual agent instead;
  regrant/final history remain pending. R330's earlier workflow-request fixture
  failure remains recorded and its accepted work was explicitly cancelled.
- **Independent review:** Astra found no concrete source blocker in the full
  a615/7260 implementation. Actual Fable found none in core (R331), then inspected
  the correct GACT checkout (R334) and withdrew its wrong-checkout caveat; no UI
  source blocker remained. These source assessments do not waive live gates.
- **Next:** R336 workflow permissions and R332 retained-work/UI lifecycle are
  prepared, not executed. The launch guard stopped them before creating state;
  latest observed headroom was 2.69 GiB commit / 0.89 GiB physical. No local
  pytest/Vitest loop was executed. Preparation/review is not live acceptance.

Remaining: Q3/Q4 delivery/lifecycle combinations; Q5 complete workflow permissions;
Q6 approved-provider surviving jobs; Q7 remaining outage, history and effect-loss
recovery; Q9 full current UI controls. Current task inspection media is complete,
but does not qualify the whole UI. Relay remains excluded. No release/install or
installed Desktop/auth/default/pin change occurred. Earlier rejected/manual-only
cleanup boundaries remain intact.

## Current execution — 2026-10-19 06:43 UTC

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

## Pre-integration evidence — October 18, 22:39 UTC

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
   complete Q1–Q9 and run R1–R6 five times each. Required failures, skips and
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
| E9 / Q9 | Complete an end-to-end user assignment through the real UI: start tasks, ask/answer, steer, observe, pause/resume, cancel and collect. Use production service outcomes from E1–E8 rather than fabricated fixtures. | Review desktop and 390-pixel phone widths: Work, Observability and Runs; progressive disclosure, clickable rows, Questions, grants, cancel confirmations, output and history. Use keyboard interaction and check viewport containment and browser errors. | Screenshots/interaction timestamps link to actual handles and server state. Cancellation has actual physical outcomes; dismissal does not cancel. Accepted user controls reach the parent. No falsely Finished waiting state, duplicate card or hidden pending input. |

E1 groups ordinary native workloads rather than treating them as three task
engines. Shell/transfer/manifest algorithms still need their own real effect
checks. E2–E5 reuse those tasks to exercise shared behavior; they do not add a
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
