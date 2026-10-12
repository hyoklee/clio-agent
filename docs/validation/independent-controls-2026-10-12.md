# Independent long-horizon controls qualification

This qualification covers control behavior, not scientific validity or multi-day
reliability. Examples use fictional checkpoint files and shell jobs. No Opal data
or private research sessions were used. The earlier coupled-control report is
superseded by this report and the [design](../design/independent-goal-controls-2026-10.md).

## Supported inputs and verification

| Control | Inputs | Evidence checked |
|---|---|---|
| Goal | `/goal <objective>`, optional `--max-iters`, `--max-hours`, `--max-tokens`; agent `set_goal(condition, max_goal_iters=0, max_wallclock_s=0, max_tokens=0)` | Starts immediately; judge reads actual tools/results and retained verified progress; creates three separate checkpoint files across continued turns; completed evidence stops continuation |
| Goal task wait | `wait_for(handle or handles, return_when="all" or "any")`; blocking `wait_tasks` | Real accepted background shell job; parked goal creates no polling schedule; terminal result wakes the owner; exactly one operation launch; analysis artifact saved after readback |
| Loop | `/loop [interval] <instruction>` or `set_loop`; optional iteration/time/token/cost limits and `stop_text` | Two real monitoring wakes, successful artifact writes, exact explicit iteration stop; whole-line `DONE` stops an otherwise unlimited loop |
| Schedule | `/schedule`/`cron_create`; instruction plus `delay_s`, `run_at` or `cron`; optional `max_fires`, `until` | Actual one-shot execution and two calendar occurrences; explicitly bounded recurring schedule disables itself after the requested count |
| Lifecycle | Identity-scoped Stop, Restart, Cancel and delete; schedule enabled state | Retained instruction and limits; restart creates a new goal/loop identity; schedule counter resets; delete retains transcript and outputs; stale/foreign identities rejected in integration tests |
| Fleet | Independent goals, Best of N/refinement and Automode model choices; null means conversation model | Actual API persistence/readback; UI selectors; routing and provider-specific configuration tests; real permission reviewer classifications for hypothetical low/high-risk requests |
| Automatic wakes | Goal, loop, schedule and task-completion injections | Exact recorded instruction and algorithm authorship; inline expandable injection without a human header or human actions; older saved envelopes classified by reserved metadata |
| Restart recovery | Retained goal/task dependency and durable pending loop wake | Actual service termination/restart; interrupted task outcome inspected; outcome report saved; accepted shell operation is not submitted again; pending wake identity retained |

All omitted/zero goal and loop limits are unlimited. Tests cover explicit limits,
user-stop protection, goal/loop independence, needs-input/failed-judge pauses,
ten repeated outputs, stale judge decisions, all/any ownership checks and
waiting-budget enforcement. These are focused unit/integration checks; the table
distinguishes real model execution from deterministic boundary testing.

The Fleet live check exercises goal continuation and permission review. Best of
N/refinement routing is covered by its consumer tests; this qualification does
not claim a fresh end-to-end scientific variants comparison.

## Live method and retained evidence

The runner is [independent_work_controls.py](../../scripts/live_verification/independent_work_controls.py).
It uses production HTTP routes, actual Codex/Luna responses, Python 3.14.6 and
clio-core 2.3.1 in an existing qualified Linux environment. It does not replace
models, tool results or clocks. Minute-based scheduling checks use real elapsed
time; the background task completes after 60 seconds. Restart deliberately
interrupts a separate 120-second shell operation.

Each attempt owns an isolated server, workspace, CLIO home and private core.
The runner retains HTTP requests/responses, transcript parts, Work state,
verdicts, failures and a cleanup receipt. Its `finally` path terminates the owned
server and reaps the private core. Source archives have per-file SHA-256
manifests. Evidence is retained under
`C:/clio-relationships-20261011/long-horizon/`.

Final-source qualification archive:
`933ce05f9a7db9d7e4739aa5ad6ab44123c2b2b16702ba649562b4d62a0d9292`
(`independent-10-source.tar.gz`, 5,175,217 bytes, 1,969 files).
The final bounded run passed all 11 conversation cases, including actual service
restart. `independent-10-evidence.tar.gz` retains `complete.json` (`passed: true`),
requests, transcripts, Work snapshots, per-check verdicts and the shutdown receipt.
The loop executed twice and stopped at its explicit limit; the `DONE` loop stopped
after one wake; the calendar schedule fired twice and disabled itself. The
interrupted recovery operation had exactly one launch and a saved outcome report.
The evidence archive SHA-256 is
`b23c5a57d1f5f6368ca6d8ed70a6a2965964a99c0c0b2e4d82e1e9f0268d7bab`.
All 1,237 production source files in the qualification manifest match the final
local source. After copying and hashing evidence from every attempt, the ten
owned remote qualification directories were removed; process readback found no
remaining owned server/core. The local browser, UI server and tunnel also exited.
Automatic approval review rejected removal of the local capture profile and
redundant source archives (`blocked by policy`); those files remain. Cleanup
receipts are `independent-remote-cleanup.json` and `independent-local-cleanup.json`.

## Defects found and corrected

- The completion judge initially lacked saved artifact input names and delivered
  task results. Its bounded evidence now includes both, with structured credential
  redaction, and retains cumulative verified progress.
- Automatic goal instructions were persisted as human prompts. Goal, loop,
  schedule and completion wakes now persist as typed system injections. The UI
  also projects older envelopes using their reserved metadata. Human prompts keep
  copy/mark controls; branching, rewind and activity selection belong to responses.
- Removing artificial human rows exposed missing turn boundaries in the judge
  evidence. Explicit message/turn boundaries now let it distinguish one artifact
  per turn from multiple actions within one turn.
- A graceful backend shutdown could pause an otherwise recoverable goal while
  its wait turn was finishing. Shutdown now retains recovery intent without
  reviving an explicit user stop. Real restart verified inspection of the retained
  interrupted operation and exactly one original launch.
- Work sections grew to fill the entire canvas, obscuring the other controls.
  Sections now size to content with independent scrolling. The bottom work finder
  also exposes goals waiting for tasks, monitoring loops and scheduled work.
- A loop's initial configuration revision could consume an iteration. The agent
  setter records its initiating turn so adjusting its pending wake in that same
  turn does not spend a monitoring iteration. Configuration/protection is atomic.

Earlier failed attempts remain evidence, not passing qualification. They include
a model omitting an explicitly requested setter, a harness expecting HTTP 200
instead of the schedule-delete route's successful 204, an overly specific loop
stop-reason expectation after a model voluntarily stopped, and a cold-start HTTP
timeout. Readiness now waits for actual agent/tool-hook initialization. The
isolated host's doctor also reports an unavailable optional MCP launcher; that
broader deployment health is not claimed to be qualified by these local-file cases.

## Checks and product documentation

- Expanded controls/consumer suite: 243 passed; async judge follow-up: 7 passed.
- Shutdown recovery suite: 58 passed; configuration/docs suite: 86 passed.
- Wake integration suite: 84 passed; turn-evidence/protection suite: 69 passed.
- Current focused controls suite: 190 passed, no skipped tests.
- CI regression checks: 83 passed, including the added-route/tool inventories.
- Turn-runner/scheduler suite: 15 passed. Deferred wakes are asserted to inject
  exactly once after the busy turn frees, without adding a human prompt.
- UI injection/Work checks: 15 passed; bottom work finder/status checks: 23 passed.
- Core schema/repository suite: 283 passed, including archived wake projection.
- Sidebar visibility/ownership checks: 12 passed. User branches remain visible;
  managed children remain excluded. Test conversations were explicitly created
  by the harness, rather than by goal/loop/schedule wakes.
- Website: zero check errors/warnings, 81 built pages with valid internal links,
  two browser checks covering all five captures at desktop/phone widths.
- Ruff, formatting, type checking and architecture guard results are retained
  alongside the test output. Counts overlap and are not a unique-test total.

Additional rendered-browser readback covers Goal judgment, Loop wake and Scheduled
wake after reload. Expansion text exactly matches each retained backend injection;
none has a human header or human-message actions. The genuine human prompt remains
a human prompt without branch/rewind controls. Results and exact instructions are
in `rendered-injections-proof.json`.

A separate fictional documentation conversation started an unlimited goal via
the native agent setter and saved `plan.md`, `results.md` and `report.md` on three
turns. The agent made two rejected attempts to reset its existing goal in the
first turn; protection held and judge continuation still completed it. Fresh UI
Stop/Restart checks retained the loop instruction and all zero limits while
creating a fresh identity. Cancel and delete removed that control; schedule
cancellation removed its pending work while the transcript and outputs remained.
Readbacks are retained as `docs-ui-*.json` and `docs-final-transcript.json`.

The [website guide](https://clio.iowarp.ai/docs/long-running-work/) documents
objectives, model judges, inputs, unlimited defaults, independent monitoring,
task waits, lifecycle controls, restart and limitations. Actual product captures
show Work, Fleet and all three wake-injection kinds. Each published capture was
read back and reviewed. Browser checks exercise the guide at desktop and phone
widths, including full-size images, focus restoration and horizontal overflow.

This report does not certify recovery of arbitrary external side effects, storage
rollbacks, scientific correctness, every deployment dependency or uninterrupted
operation for days. Closing the browser is independent of server lifetime; the
backend, execution host and model authentication still need to remain available.
