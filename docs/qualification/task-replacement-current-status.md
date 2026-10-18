# Tasks replacement status â€” October 18 UTC

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

## Current state â€” October 18, 22:39 UTC

Initial implementation and initial test construction are complete. Regression
checks pass for the current production tuple. Full live qualification remains
incomplete; publication and daily Desktop installation remain separate.

| Milestone | Current evidence |
| --- | --- |
| Runtime implementation | clio-agent `a0645c216fad81fb36a063dbdb4b9f5bee1d87b0`; GACT `c813c1b7d3064c5b6125dc21c9aec70117c78ca4`. Later documentation-only commits preserve this runtime code. |
| Regression CI | Agent run 39166370524: all 24 jobs successful; twelve Python reports, zero failures/errors. Python 3.12/3.13/3.14 each have 12,993 passes and 50 exclusions. Exclusions are not passes or live acceptance. |
| UI CI | GACT runs 39166228634 and 39166224687 succeeded at c813c1b7. The first has six applicable successes and three conditional release skips. The second has five successes, the conditional native-proof job skipped and three conditional release skips. |
| Matching build | R219 online/offline builds passed at the exact tuple; 655 files / 60,368,527 bytes. Index SHA256 `0d8febb24e4855dbf402427e697355a142b83bed7a0f95ea68f2b26ce77ded0a`. |
| Independent source reviews | Astra and actual Claude Code/Fable both returned source GO for a0645c21 / c813c1b7. These do not qualify runtime behavior. |
| Current live proof | R227 child peers and R234 root Session peers passed two-workflow coordination; R234 also passed observe-only privacy and real desktop/phone grant/revoke. R230 passed native Shell/model/physical-output checks. Current SSE size evidence passed. Scope and remaining gates below. |
| Final acceptance | Q1â€“Q9 as a whole, migration/recovery obligations and all 30 final-candidate race repetitions remain unaccepted. No Tasks release or daily installation. |

[Agent CI](https://github.com/iowarp/clio-agent/actions/runs/39166370524),
[GACT workspace](https://github.com/iowarp/gact-tui/actions/runs/39166228634),
[second GACT workspace](https://github.com/iowarp/gact-tui/actions/runs/39166224687).

The unchanged 180-second retention guard passed with all 1,005 messages:
112.641 / 81.668 / 97.780 seconds on Python 3.12 / 3.13 / 3.14.
A2UI load passed in 154.509 / 158.972 / 67.013 seconds under its unchanged guard.
Fifty exclusions per interpreter include provider prerequisites and platform-only
cases. No skipped live/platform route is presented as qualified.

## R227: two distinct declared workflows

Actual Codex/Luna used the production direct-SSE bridge, conversation engine,
Core task history/mailbox and normal authenticated human grant/control endpoints.
No fixture UI or executor-only probe substitutes for these model actions.

- Workflow A: `workflow_e33c5a19008e6f44c3d22e329b6d3ad109c9d05a42487c428d2cbd0ca7dd24e8`.
- Workflow B: `workflow_08fd7cc5c7116f131c97075fdd5bb48dac8361dda58dcf4fe87388de06ffa87e`.
- Step A: `task_a8d9b1c6148335630c947375ceb8c15fe91d6b8cd37020c71beae78662caba70`.
- Step B: `task_d56a261f3ba45b52b5974723757735bacb586aa468fead50d9260b31db8938f1`.

Both steps posted one asynchronous Question, read an independent file and yielded
under their original handles. Before a grant, peer query returned no task/count.
After human read/observe/message grants, the model discovered and observed the
peer, subscribed, expired a wait while the peer continued, attempted one denied
cancellation, read independently, sent a message and received a reply.

Pause held A while the reply remained Core-pending. Revocation prevented its
injection and peer disclosure; restoring the sender's message right admitted the
retained reply automatically. It had one recipient-input commit. Answering B's
Question completed B's step and workflow; A woke, explicitly collected B's actual
result while its own Question remained open, then completed after its own answer.
Owner and subscriber each had one independent completion input commit. Each root
called its declared runner once; no workflow or Question was replayed.

This proves the child-peer workflow scenario. R234 below supplies root Session
handles and observe-only redaction. Historical-handle pinning, busy-peer cases,
additional permission cases and final race repeats remain required. R227 grants/revokes were
through authenticated human REST, not UI controls.

The separate read-only R227 UI inspection opened the real root Work panel, expanded
the paused child, opened its conversation in the center and displayed its actual
session-access rights. The successful inspection has no page errors. Two console
connection failures were captured without a persisted post-connect boundary;
therefore it is not claimed as the complete clean-console Q9 gate. Earlier
browser failures were locating hidden panels; product source was not changed.

## R234: root Session handles, permissions and real UI

Two distinct declared workflow roots retained their original Session handles
through Questions, peer feedback, pause/resume and completion:
`task_d345b106c3e54e3ab306dede05797821` and
`task_bd4a4dbd679b4a43b8cebfd100c2123f`. Their workflow IDs are
`workflow_62bc4118ffe5ec1caac6daa5cdcfa75de771ca6d9f90797b9133efd4554eb81a`
and `workflow_3cf9e088499c44c0552a2ae0601600c6689a9150c1a2ce9526a7a85275b9795d`.
Each workflow ran once; its child read the actual sentinel file and completed.

Before grants, peer query disclosed no task/count. Observe-only query and observe
returned safe status/numeric progress with no assignment, owner, message, output
or result. Explicit result reading was denied. The desktop UI then granted
read/observe/message, leaving control and descendant access separate. The model
discovered, observed/subscribed, expired its wait without cancelling the peer,
was denied cancellation, and sent an attributed message.

One root initially declined to reply, incorrectly claiming the standard control
was undeclared. One recorded operator clarification entered the regular feedback
queue under the same handle; the model then used the actual control successfully.
This run is not represented as an unassisted first-attempt model success.

With A paused, B's reply remained Core-pending. Real phone UI revocation blocked
its injection and peer disclosure. Regrant admitted it once; answering B woke A
with one subscribed completion, and both roots completed after their own answers.
There was one Session handle per root, one reply input commit, one subscription
completion commit and no human-root self-completion wake. Desktop/390px keyboard,
permission controls and containment passed with zero connected-console/page errors.
The four selected images were visually inspected. Pending busy-peer, historical
handle and race cases are not inferred from this proof.

## Current native and SSE evidence

R230 on the same tuple passed actual Codex/Luna background Shell acceptance,
running snapshots before/after independent file reading, expired wait, observation,
unbounded wait and explicit result collection. The 45-second process produced
619 output bytes and its actual completion file; canonical Shell handle
`task_4d057a41769e49e1b1795be4ae2f2604` completed before cleanup.

R231's model-side Indexing evidence passed with 48,098 entries, but its physical
checker incorrectly expected a flattened result in a legacy UI projection.
The run remains failed and its data was removed. Both storage scenarios now read
canonical task/result endpoints and retain independent complete manifest/path/
byte/hash assertions. The large-result reader respects pagination/references and
does not parse truncated JSON as a complete native result.

R235 at documentation commit `38ce7d8a8` passed the complete current Indexing
model/physical case. Handle `task_060516abb2864b18b5cf0a07cce70a84` completed
with manifest `link_442056e231fc4eb880ec964edb9a7828`; all 48,098 paths exactly
matched the independently enumerated filesystem. Runtime Python, dependencies,
schema and GACT are unchanged from a0645c21, as recorded by r236-doc-impact.json.
The source-approved-before-agent-warmup Download recheck R238 is active;
R232's earlier source-approval request was rejected by the existing permission
guard before any Download/model submission. It remains a failed prerequisite,
not a passed Download. Full Download verification remains required.

R234 observed 12,242 actual native SSE lines: 87 exceeded 65,536 bytes and the
maximum was 82,331 bytes. All passed at configured 1,048,576 bytes; zero observer
errors. The harness used read-only CPython monitoring of the original parser's
existing size-check line, recording lengths/limits only. It changed no parser,
request, response bytes or timeout. `lm15.sse_limit` / `CLIO_LM15_SSE_LIMIT`
therefore has current actual-model over-64-KiB evidence. R229 separately measured
73,563 bytes; its later provenance-lookup failure remains a failed family.

## Scoped preceding evidence and source reviews

R212 reproduced reserved task-body downloads during cold semantic replay; R213
passed the correction using ARC's existing event-chunk grammar. Actual-Core
coverage retained 48 linked outputs and 20 pending messages. Exact-head CI adds
this regression. Core index write work previously fell from 105,815,856 to
44,701 bytes with all 1,005 messages preserved. Actual-model large-history restart
and the complete F03 performance gate remain pending.

R218 reproduced Runs losing/doubling structured diagnostics. The correction
retains the original issue for deduplication and disclosure, with a separate short
summary. Both new cases, scoped checks, six guards and workspace types passed.
R219 built the matching UI. No schema, production budgets or assertion was weakened.

Astra current review turn `01a150d6-e54d-7651-aed1-30b6468d4f4d` returned source GO.
Actual Claude Code/Fable R219 also returned source GO. Remaining review advisories
are nonblocking: workflow-derived Runs may omit their concise reason in Details;
the private SDK hook lacks a direct attribute assertion; one ARC docstring is
stale. External attention paths that replace numeric progress are not represented
as numeric-preservation acceptance.

R210 remains scoped predecessor evidence at fcd8737c / GACT 07cf095f: actual SSE
acceptance, independent work, one uncertainty attention, original-identity
reconnection without replay and one final wake under the same assignment.
Its 77-byte result/hash/execution-count check and desktop/phone views passed.
It does not prove a measured actual SSE line over 64 KiB or the final matrix.

## Runtime, evidence and remaining work

The D runtime is Python 3.14.6, iowarp-core 2.3.2, DSPy 3.4.0,
FastMCP/fastmcp-tasks 4.1.0, MCP 2.0.0, Docket 0.26.2 and clio-schemas 0.6.0b13.
Lock SHA256 `04d97494089a6fdbdb28a105b7119bedaf4957f0984e3a17c3d3a88892b81508`.
No clio-core source was changed. The supported isolated Core configuration uses
256 MiB main and 32 MiB metadata segments; product defaults remain unchanged.

Bounded receipts and inspected images live under
`D:/Libraries/Documents/projects/clio-agent-task-qualification/.pytest-runtime/static/`:
`ci-a0645c21-complete.json`, `r219-web-build.json`, `r219-claude-review.json`,
`r227-live-workflows.json`, `r227-ui2-inspection.json`, `r226-cleanup.json`
and `r227-cleanup.json`. Three canonical reports remain this status document,
the acceptance ledger and the live experiment sheet. Older dated construction
notes are historical and do not override this current state.

Next: complete current-tuple native storage/mixed work and remaining peer cases; Claude-specific
delivery/child controls; external input/provider-job recovery; Core/input-commit
and visible-effect recovery; migration twice and actual large-history restart;
capacity/retirement, real desktop/phone controls and the 30 final races. Website
walkthroughs and selected current-service screenshots remain required. Relay's
special transport/lifecycle is outside qualification scope.

## Owned cleanup

R226/R227/R228/R229/R230/R231/R234 services exited normally; active tasks were
empty after cleanup, launched browsers closed and all fourteen fresh data/temp
roots are confirmed absent. Their cleanup receipts total 4,225,608,895 logical bytes. These are
logical counts, not claims about total volume free-space changes.

The 21:54 UTC inventory measured 173 remaining paths / 29.46 GiB before R226
disposal. Its two paths are now absent; subsequent fresh paths were also removed.
Seventy-six earlier rejected boundaries remain manual-only. No retry, bypass,
delegation, parent removal or archive was used. Current source, human design
files, the D execution environment, installed Desktop, authentication, defaults,
released pins and unrelated work remain preserved. The 22:04 UTC volume reading
was C 6.77 GiB / D 50.54 GiB; the larger external free-space increase is not
attributed to this campaign's bounded cleanup.
