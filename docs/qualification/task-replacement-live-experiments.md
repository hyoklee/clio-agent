# Tasks replacement: finite live experiments

## Integration and live update — 2026-10-18 23:30 UTC

Initial implementation and initial test construction remain complete. Current work
is integration, regression assurance and live qualification. Full acceptance is
still incomplete; no release or daily Desktop installation is authorized.

The next candidate integrates `develop` through `cee026de3` into the existing
feature history, GACT `aca98ce477bbee1d1f14b1f384d1cf283906de6d` and marketplace
`2c172233a9f895e41f7de121a3871d282a5fc0a2`. FastMCP/fastmcp-tasks 4.1.0,
MCP 2.0.0, Docket 0.26.2 and iowarp-core 2.3.2 remain pinned. The incoming
canonical schema revision is `3224a7970d9271b2ff4ca9fe7bec2e227c4eea19`
(0.6.0b14). This integrates the upstream LM request-admission and NDP changes;
it does not add a new Tasks owner or scheduler. Its exact committed tuple, CI,
matching build and independent delta reviews must be recorded before acceptance.
The protected human design files remain outside the merge index.

Pre-integration source `3582bb82` / GACT `c813c1b7` freshly passed **R242** with
actual Claude Haiku through the production `claude_code` SDK bridge. In both
idle and post-Stop cases the model received an asynchronous Question handle,
read the real sentinel while it remained pending, and later automatically received
the answer under the same original assignment. It explicitly read that result.
Each Question answer has exactly one confirmed recipient-input commitment;
a later human turn created a linked assignment without repeating the Question or
its answer. Both original assignments and both Questions completed. This covers
these two Claude Question scenarios, not all child/lifecycle or Q3/Q4 behavior.
The service exited 0, no active work remained and both disposable roots are absent.
Both original authentication files and the frozen production source hash match.

R242 idle assignment: `task_633d07b37cfb4f2d89af97affe427164`;
Question: `task_c199f1a064b5fe375168f419dfc4de8146d84acad2f94f88e6e9c072a9a66419`.
Post-Stop assignment: `task_c03464834bbb4d9081ce35dbf61b8f96`;
Question: `task_91313719fc84e3f79f5824488f9b56637dcd98c422f622c3c1bffb4330136567`.
Receipts: `r242-live-native.json`, `r242-cleanup.json` in the D checkout's
`.pytest-runtime/static/` directory.

Download remains **unqualified**. R238 exceeded the unchanged 600-second model
experiment diagnostic with 48,000 selected small files; accepted work progressed,
then the operator cancelled and removed its data. R239 missed the 120-second
startup diagnostic before any model/work submission. R240 accepted a Download,
but the real transfer raised `MemoryError` at `reader.read(1024 * 1024)` while
Windows was observed at 99% of its 84,128,354,304-byte system commit limit.
The backend reported completed while physical settlement remained unknown; this
is not a completed Download proof. Stop and explicit cancellation were requested;
its service tree needed an authorized force-close. Physical process retirement
and fresh-root removal are proven; task outcomes remain uncertain. Do not turn
those outcomes into successful cancellation or file/hash acceptance.

R241 was a harness provider-selection error: Codex was bound with a Claude model
name. It supplies no Claude evidence. The corrected R242 checks the returned
provider before submitting a model assignment. All R238–R242 services and fresh
data roots are retired/absent; no archives were created. The exact rejected
cleanup paths in the separate inventory remain manual-only and were not retried.
R242 preflight recorded 7,099,703,296 bytes of system commit headroom before launch;
future families check that resource prerequisite before creating a service.

Agent CI `39173458592` at `38ce7d8a` completed all 24 jobs with twelve reports and
zero failures/errors. Retention kept all 1,005 messages under its unchanged
180-second guard (88.861 / 115.743 / 95.790 seconds). The A2UI guard passed at
158.887 / 143.620 / 50.250 seconds. Website run `39175400770` at `3582bb82`
passed its build/browser checks; deployment was skipped. Agent CI `39175391771`
at that head was still running at this report boundary. These runs do not execute
the subsequent integration merge. Fifty exclusions per interpreter remain
exclusions, not passed tests or live acceptance.

Astra and actual Claude Code/Fable returned source GO at `a0645c21` / `c813c1b7`
and documentation GO at `3582bb82`. New integration reviews remain pending.
Q1–Q9 as a whole, the complete migration/recovery gates and **0/30** final race
repetitions remain unaccepted. The old gates below are retained in full.

The current model/tool cases used the real application factory and production
owners under isolated Uvicorn. Final startup/shutdown acceptance must also use
the production `run_server` foreground entrypoint. Factory-service artifact-fold
warnings are retained for investigation at that entrypoint; no Tasks-engine
patch is justified solely by the different harness startup path.

## Current execution gate â€” October 18, 22:39 UTC

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
