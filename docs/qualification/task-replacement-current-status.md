# Tasks replacement status — October 16

## Overnight live verification and CI corrections

Live verification is the priority under the renewed human goal. CI is checked
between families; failures remain failures and do not substitute for actual-model
or real-service UI evidence. Initial implementation is done; regression repairs,
bug corrections and qualification remain in progress. clio-core is unchanged.

### Capacity and Question UI checkpoint

R140 continued R139's original profile on corrected source `527a302e`; it did
not recreate the Question or assignment. Startup succeeded, the dormant
Question and previous input IDs were unchanged, and service recovery alone did
not wake a model worker. Unrelated-session answer/cancel requests returned 404.
Invalid answers through both HTTP views returned 422. All four rejections left
the Question snapshot unchanged. The valid answer returned 200, woke actual
Codex/Luna, and the model collected the original handle plus fresh file content
before completing the original assignment. Core records one answer delivery
and one ask invocation. Another normal API/native-lifespan restart retained the
terminal result and input IDs without another wake or delivery.

`r140-scoped-audit.json` and the original failed R139 receipt retain those
distinct outcomes. Both corrected service cycles exited normally. The custody
audit found no owned processes/listeners or active tasks; `r140-cleanup.json`
confirms removal of the shared R139/R140 profile and temp data. This qualifies
the owner-selection and response-binding corrections, plus scoped graceful
recovery. Hard-crash/input-commit faults, uncertain effects, Core-outage controls,
retention over 1,000 messages and final repeated races remain pending.

GACT `401efcfe` web CI completed successfully: 311 app tests, 3,558 web tests,
133 main browser cases and the subsequent 15/2 web check families passed.
Native builds and fixture WebView build prerequisites remain failed. R141
reproduced Cargo's dependency failure using actual tracked native source in
owned D-only copies. Changing the Rust minimum did not resolve it. Explicit
stable updater 2.12.0 and 2.14.0 proposals both require `zip ^4`; every listed
compatible version is yanked. The earlier automatic selection reports the same
problem for `zip ^2`. No production dependency, updater capability or check was
changed. All five proposals remained failures, and the copied source/registry
cache was removed (`r141-native-cleanup.json`); bounded logs/hashes remain.
clio-agent CI `38929794407` at `527a302e` remains failed across test shards.
Passing source/lifecycle/coverage jobs do not make it accepted.

R139 used actual Codex/Luna on `a295d54f` to create a Question, read the real file
and yield. Its first API/native-lifespan retirement completed normally. Startup
of the same profile then failed before readiness: NativeTools.restore decoded
the Question owner's saved QuestionDefinition as a SubmissionContext. The
traceback, original handles and bounded physical-custody audit are retained.
This is an execution-owner selection defect in clio-agent; the Core record was
read successfully and `iowarp-core==2.3.1` is unchanged.

The correction checks a known backend owner before decoding native submission
content, preserving recovery of native acceptance whose backend identity is
still unknown. A regression restores native execution with a real pending
Question and requires its identity/state to remain with the Question owner.
The original R139 failure remains failed. R140 recovered and settled its
original records without resubmission, then removed the disposable profile.
Wider recovery and required CI acceptance remain incomplete.

The next candidate corrects the remaining Question response findings from CI.
Compatibility answer/cancel URLs now bind the selected session tree through the
existing TaskAccess scope check; the authenticated human's broader shared-task
controls are unchanged. Both Question HTTP views use one response adapter,
returning 422 for invalid input and 409 for already-settled work. The normalized
interaction feed reports typed A2UI read degradation while retaining other
Questions/permissions. Public regressions now cover denied answer/cancel,
parent answers through both views, and invalid-answer retention through both
views. Scoped source checks pass. R140 supplies scoped live response/recovery
evidence; required CI and the wider recovery matrix remain incomplete.

R138 freshly qualified the native child-provenance correction on clio-agent
`4a92f32c` / GACT `401efcfe`. Both root-only and child-inclusive native queries
returned HTTP 200; the latter retained the actual child's task handle, session,
parent and `worker` agent ID. Before answering, the native view contained 227
spans; after actual child/parent completion it contained 425, including both
owners. Root-only lineage excluded the child. The actual connected UI made no
failing provenance requests and recorded no console/page errors after service
connection. Four initial connection-refused messages from pre-connection setup
remain recorded separately, not erased.

The same run repeated five actual desktop/phone draft cycles, phone answering,
fresh child collection, original child/parent assignment completion and one
delivery per recipient. Selected native API bodies, Core input records and
inspected screenshots are retained. `r138-cleanup.json` confirms normal
service/browser retirement, no active owned tasks/listeners, and removal of
the disposable profile, short temp root and build. clio-core remains unchanged
at `iowarp-core==2.3.1`.

This passes the specific provenance and connected Question UI checks, not the
wider Tasks matrix or final six race families. Exact-source clio-agent CI
`38924966737` and GACT workspace CI `38923122830` are still running. Native GACT
jobs already failed dependency resolution: `tauri-plugin-updater v2.0.0` requires
`zip ^2`, whose listed 2.x releases are all yanked. That packaging failure is
retained as an outstanding gate; no dependency/check has been bypassed.

R137 on clio-agent `4abdf956` / GACT `bb758d56` passed the scoped actual-model
Question/UI recheck. The child asked once, read the real file while its Question
was pending and yielded. Its answer was typed once and survived ten viewport
transitions across five desktop/390px phone cycles. The actual phone response
returned HTTP 200 for the correct child owner and original Question handle.
The child freshly collected the unpredictable answer and file text, completed
its original assignment, and woke the yielded parent, which also completed its
original assignment. Core input records contain one Question-answer delivery
to the child and one child-result delivery to the parent. No human steering,
replacement assignment or repeated question was needed. These are resize and
ordinary-delivery checks, not the six final lifecycle races.

`r137-scoped-audit.json`, the original controller receipt and selected real
screenshots retain the proof. The phone/desktop frames were visually inspected.
The service/browser exited normally, all owned work settled, and
`r137-cleanup.json` confirms profile/temp/build absence. R136 retains its original
failed result: its draft/response stage passed, but the controller cancelled
work after a single ten-second status-read timeout before verifying delivery.
R137 retained the same production tuple, used normal finite-I/O capacity and
retried transient observations against the still-live owner rather than
treating a read deadline as a terminal task failure.

Full UI acceptance remains incomplete. Native execution-provenance requests
returned HTTP 503, now captured with the exact cause: child attribution treated
the stored session agent dictionary as an object with an `.id` attribute.
The next correction reads the canonical dictionary and runs the projection in
the route's existing worker-thread helper. Two new public-route regression
cases assert actual stored child identity and include-children behavior.
R138 supplies fresh scoped live acceptance; its regression CI remains pending.

GACT CI at `bb758d56` passed all 3,558 unit/integration tests, including all six
Question-draft cases, then failed two browser cases that expected an unsent
answer to disappear on reopening at another width. Test-only `401efcfe` now
requires the initial empty/disabled state and subsequent retained/enabled draft
without retyping, preserving the existing source-navigation and geometry
checks. Its workspace CI remains pending. Native builds are also failed.
clio-agent CI at `4abdf956` remains red; Python 3.14 shard 1 executed 3,928 passed,
200 failed and 21 skipped. Unrelated-session Question response routing,
validation status and corrupt-surface projection failures in that log require
further ownership review; they are not dismissed as fixture migrations.

The next candidate also preserves the existing Question task handle and
asynchronous response marker in the normalized interaction payload. The typed
UI row previously discarded the marker, and the interaction projection omitted
both fields. GACT therefore displayed legacy waiting guidance and direct
dismissal controls for task Questions. The correction changes presentation
bindings only; the same Core Question and response owner remain authoritative.
Root/child public-route regressions now assert those fields. Scoped lint/format
and Mypy pass; regression execution stays in CI. R137 qualifies the scoped live
binding and draft behavior described above.

The earlier R134/R135 live tuple was clio-agent `bf2df179` / GACT `6669ac3a`, with the
unchanged `iowarp-core==2.3.1` library. GACT preserves unsent Question values in
the existing session Question context across layout remounts. Six constructed
regressions cover free text, choices/comments, structured values and scope
isolation. Scoped lint/format, TypeScript and all six existing GACT guards passed;
the tests are executed by CI. CI exposed missing test DOM cleanup, corrected in
test-only GACT `bb758d56` without changing production behavior or assertions.
The fresh GACT workspace runs are still pending at this checkpoint.

R134/R135 used actual Codex/Luna with root → child → leaf assignments, one
inference permit per child depth and a one-worker shared finite-I/O executor.
Both parents entered unbounded waits; the leaf posted a Question, read the real
sentinel and yielded without retaining a synchronous session worker. R135 then
completed an independent root and same-depth child while the original parents
continued waiting and the leaf Question remained open. Their canonical results
contain the actual unpredictable sentinel. Parent A required explicit feedback
to resume its initially yielded assignment; its assignment and child handles
did not change. This is scoped capacity evidence, not fully autonomous mission
acceptance or the final race matrix.

The original controllers remain failed. R134 incorrectly required an admission
reservation to disappear at the instant the leaf worker retired. R135 selected
only Session results, then incorrectly required a Subagent result in that list;
the retained canonical Subagent result contains the expected output. Its
independent scoped audit records this distinction. Neither run reached the
Question resize/answer stage, so the GACT draft correction still lacks live
acceptance. The services and all owned sessions/tasks settled normally, with
no accepted operation replay. Disposable data and the reused UI build are
covered by the R135 custody/cleanup receipts.

clio-agent CI `38914498775` at `bf2df179` completed with failures across test
shards and one cancelled shard; lint, dependency resolution, native service
lifecycle and other passing jobs do not make CI green. Regression repairs and
full live qualification remain incomplete. No clio-core source/package,
installed Desktop, authentication, defaults or released pins were changed.

R129–R131 failed harness setup/order assumptions, not product acceptance.
Their services, processes and disposable roots are settled and removed; original
failed receipts remain. R132 on clio-agent `0e57be74` / GACT `cecfb4ee` proved
independent single-worker Shell/storage queues: the held Shell ran, the second
Shell remained queued, and Indexing published the exact 514-entry manifest.
Actual phone UI cancellation withdrew the queued command without starting it;
Keep running issued no cancellation. The parent received the attributed control
and entered an unbounded Question wait. An independent Codex/Luna session made
progress with the shared finite-I/O executor limited to one worker. The parent
wait remained active for another 82 seconds with the Shell still running.

The actual phone Question answer then returned HTTP 500: the interaction route
called `question_row` on the application loop. The real Core read raised
`LoopThreadStoreWrite` before accepting the answer. The correction moves scope
and Question lookup through the route's existing thread-pool helper; two root
answer/cancel regressions supplement the existing child response case. No
clio-core, task owner, schema, timeout or budget change is introduced.
The correction awaits fresh live acceptance and CI. R132 is failed overall;
its independent audit and UI response preserve the exact error. Both sessions
and physical workloads are settled, the browser exited normally, and
`r132-cleanup.json` proves profile/temp roots absent. No operation was replayed.

Exact-head CI `38901643638` at `0e57be74` is failed. For example, the Python 3.14
shard 1 executed 3,925 passed / 202 failed / 21 skipped; that is one shard, not
the complete suite. Required failures and exclusions remain outstanding.

R133 freshly ran clio-agent `097e9f87` / GACT `cecfb4ee`. The actual phone
interaction response returned HTTP 200; the model freshly collected the answer,
reported its unpredictable nonce and completed the original assignment. Core
records one Question-answer input commit and no assignment replacement. This
qualifies the specific interaction-route correction, not the entire UI matrix.
Scoped lint/format/Mypy and size/class guards passed; no local pytest was run.

The same run again proved native pool separation and queued cancellation. Its
parent Question wait remained active for 441 seconds. The peer initially chose
a foreground Shell read, which correctly queued behind the held worker. Two
explicit Stops withdrew those foreground calls with confirmed never-started
settlement; cancellation results woke the peer. Revised human feedback queued
before the second Stop directed it to the FS tool, after which it completed its
file read and authorized query while the parent still waited. Those actual
interventions and observations are retained; they are not a clean autonomous
peer-route pass. The held command reached its explicit 600-second limit before
the delayed Question answer, and the model reported its failure honestly.
The controller's expected-cancelled assertion therefore remains failed.

`r133-final-audit.json` separates the scoped Question pass from failed full
capacity/UI acceptance. It confirms both sessions terminal, original process
identities retired and independent result commitment. `r133-cleanup.json` proves
the service/browser stopped and disposable roots removed. The original failed
controller/audit attempts remain unchanged. A real resize check also reproduced
loss of an unsent Question answer between phone and desktop layouts;
`r133-question-draft-resize.json` records it. That GACT defect remains to fix.
CI `38909154359` at `097e9f87` is still red: Python 3.14 shard 1 executed
3,927 passed / 201 failed / 21 skipped, with other shards still running at this
checkpoint. clio-core and dependency pins remain unchanged.

clio-agent now includes the human-steering and grant-wake corrections below; GACT is `cecfb4ee`
(test changes only after `954a2a33`). The locked
clio-core package remains `iowarp-core==2.3.1`. The new read correction is in
clio-agent's ARC framing adapter, not the clio-core library. Ruff/format, scoped
Mypy and unchanged removal/size/class/silent-fallback guards pass. The reader
regressions are in CI, not claimed locally executed.

### Latest two-workflow finding

R122–R124 ran on clio-agent `89f89770` / GACT `cecfb4ee` with actual Codex/Luna
and two distinct declared workflows using the existing runner. Both workflows
created their own child and Question. Discovery, observation, a subscription,
expired waiting, denied cancellation and busy/idle peer messages were exercised.
R122 failed an out-of-order harness observation lookup. R123 revoked the
receiver's read grant while leaving the sender's message grant valid; delivery
was correct and its failed assertion was a harness error. Neither is a full pass.

R124 correctly revoked the sender's message right before receiver injection.
The accepted reply stayed pending. Restoring only that right made it eligible,
but the idle receiver did not wake during the 90-second diagnostic window.
`r124-grant-wake-defect.json` records the real failure. The correction signals
the affected target mailboxes from the existing Core-backed target/lineage
indexes after a confirmed grant change. Existing staging still rechecks rights;
the hint contains no message or permission. No scheduler, registry, schema or
clio-core change is introduced. Five constructed regressions cover session,
tree, exact-handle and read-only hints plus actual queue/input commitment.
They remain unexecuted locally and await CI. The existing elicitation parser
tests now use its retained public function, with their assertions unchanged.

All three services exited normally, and their disposable profile/temp roots
were removed after physical custody checks. Bounded failed receipts remain.
R125 on clio-agent `dcdc640e` / GACT `cecfb4ee` passed the full scoped recheck:
two actual declared workflows, authorized discovery/observe/subscription,
expired waiting, denied cancellation, peer messages, revocation before input,
and automatic delivery after restoring only the sender's message grant.
Both workflow steps collected their unpredictable Question answers and both
workflow runners completed. The subscriber model freshly read the original peer
result. Owner and subscriber each have one independent final-outcome input
commit; the retained peer reply has one input commit. No workflow or Question
was submitted twice. `r125-live-workflows.json` records source/runtime/model,
invocations, handles, messages and Core commitments. Service exit was zero,
active owned tasks were empty, authentication/source hashes were unchanged,
and `r125-cleanup.json` proves both disposable roots absent. UI grant/revoke
controls and final frozen-candidate race repeats remain unverified.

CI also exposed a retained bare-model fixture that started the real application
but never recorded or bound its conversation assignment. The fixture now uses
the existing confirmed assignment and active-turn helpers; model-input safety
checks and all test assertions remain unchanged. This is a test-only correction,
not a production implementation or clio-core change. It awaits CI execution.
Exact-head CI `38891321674` finished failed; regression shards and Python 3.12
coverage remain failed/cancelled, while lint, dependency resolution, filesystem,
flake-hunt, Flowcept and Windows/Linux native-service lifecycle jobs passed.
CI `38895429794` tests the production correction at `dcdc640e`; regression
jobs were still running at the R125 cleanup checkpoint.

R126 on clio-agent `6972ce34` / GACT `cecfb4ee` repeated the actual two-workflow
case with real GACT controls. Desktop UI granted only read/observe/message;
the model discovered, observed, waited on and messaged the peer, while its
cancellation was denied. Phone UI revoked that exact grant and the model's
subsequent discovery/observation disclosed no peer task. Restoring sender rights
delivered the retained reply automatically. Both workflow runners completed;
owner/subscriber commits remained independent. The UI sent exactly one grant
and one revoke, both HTTP 200. At 390×844 the row and controls were contained
with document width 390; keyboard selection/toggling displayed the descendant
control warning and left control unselected. No page exception occurred.
Four actual light-mode screenshots were inspected. Initial browser setup
failed before service readiness; that attempt is retained separately and its
context retired before the successful browser. Connection/provenance console
errors remain recorded, including HTTP 503: this is scoped grant/revoke
acceptance, not a full error-free Q9 pass. Both services and browser exited zero;
`r126-cleanup.json` proves disposable profile/temp roots absent. Receipts are
`r126-live-workflows.json`, `r126-browser-custody.json` and `r126-ui-keyboard.json`.

CI `38896134178` on `6972ce34` still has failing regressions. Its completed
Python 3.14 shard 1 reports 201 failed, 3,924 passed, 21 skipped and one setup
error; these are one shard's counts, not the whole suite. The variant route
fixture now owns the same real application lifespan and confirmed assignment
as its shared draft fixture, including shutdown before restart. The Codex side
call fixture retains the real bound session instead of replacing its ID with
an unrecorded string. Original behavior assertions remain intact. These two
test-only corrections pass scoped Ruff/format/Mypy and await CI execution.

R127 on clio-agent `fc836008` / GACT `cecfb4ee` used an actual external native
FastMCP HTTP server and an owned network-fault proxy. Its initial controller
incorrectly required two simultaneous Question cards. The pinned SDK invokes
input callbacks sequentially, in the server-supplied order; its opaque surfaced
keys also differ from the tool's request keys. No task-code correction was
warranted. The original controller failure is retained. A separate live audit
answered the actual surfaced inputs, confirmed the first answer in Core while
the other remained pending, then verified recovery after the proxy lost an
already accepted update's reply. The actual model read both unpredictable
values and the effect hash. `r127-native-input-proof.json` records this scoped
pass independently of the failed controller. Normal shutdown and cleanup
retired the service, external server, proxy and disposable roots.

R128 freshly repeated that experiment with the corrected controller on the
same source/runtime tuple and passed. The model received its MCP handle before
completion, performed independent file and inline MCP work, queried/observed
the input-held task and expired a short wait without cancelling it. Core held
one confirmed answer while the other input remained open. After the accepted
update reply was deliberately lost, the original task recovered with unchanged
backend identity. The trace contains one original `guarded_pair` submission;
the backend arguments were empty, with no forwarded CLIO description metadata.
Exactly two Question handles were used. The model freshly collected both values
and the real file SHA-256 `ff3294bf0f2e38b488ff207e5a2a95ebba20d2da03691613c6091335495bc3c6`.
The file contains one effect record. All parent inputs retain the original
assignment handle, with one final-outcome input commitment. Service, external
server and proxy exited zero; owned active tasks were empty, authentication
and production source hashes were unchanged, and `r128-cleanup.json` proves
the disposable roots absent. `r128-live-mcp-input.json` records the actual
models, runtime, raw RPCs, handles, inputs and backend/file outcomes. The
external workload is explicitly synthetic; server/SDK/CLIO/model execution is
real. This does not qualify service restart, surviving provider jobs or final
race repeats.

Two further CI fixture repairs attach the export suite to the real Core history
and run eight retained provenance/lineage cases inside the application's actual
lifespan. The assertions are unchanged; most displayed diff lines are indentation.
Scoped Ruff/format/Mypy pass. These are test setup repairs awaiting CI, not live
acceptance or changes to clio-core. The broader failing regression groups still
need classification and correction; they are not all presumed obsolete.

- R103, clio-agent `57c00ddc`: actual Codex/Luna accepted a Question, read a file
  while it was pending, yielded, received its idle answer wake and collected the
  original result. The family failed its post-Stop harness gate because the
  helper omitted the session display status `cancelled`. The original failure
  receipt remains; no family pass is claimed.
- R104, clio-agent `c564083c` / GACT `8205f3ea`: the repeated post-Stop Question
  case passed. The actual stopped assignment retained its open Question; an
  answer woke the model, result collection succeeded, the later ordinary turn
  did not duplicate delivery, and Core confirmed one answer input commitment.
- R105 on that same pair: actual native Shell acceptance, independent file read
  while running, a still-running snapshot, short wait expiry, progress observation,
  unbounded collection and stored result read passed. Exit code is zero; the real
  completion file SHA-256 is
  `89174256781fcf055fd72081947b8ec17c709ef97c9b325fdb903839dad42166`.
  Real-service desktop connection/transcript/Work-menu inspection occurred, but
  the UI family timed out before cancellation and phone acceptance. Q9 remains
  incomplete. Retained screenshots are inspection evidence, not a UI pass.
- R106, clio-agent `c3466fec`: actual Codex/Luna indexing accepted a handle,
  continued independent work and produced the exact 48,098-entry manifest.
  The family then failed an obsolete harness result-field lookup before Download.
- R107's full 48,000-file transfer exceeded its 600-second harness diagnostic
  window while making byte progress. It was explicitly cancelled and physically
  settled. This stress case remains failed; no product deadline was changed.
- R108 failed startup while reading retained history. R109's read-only native
  probe proved that the stored frame was intact but its reported size was stale:
  29,070 reported/read bytes versus 33,482 required and successfully read bytes.
  clio-agent now retries the exact framed length once and still rejects genuinely
  truncated or malformed data. No stored data or clio-core dependency changed.
- R110, clio-agent `1303830b` / GACT `954a2a33`: the service reopened that history,
  preserved the original completed Indexing and cancelled Download, and actual
  Codex/Luna submitted a new selected-path Download with a new handle. Acceptance,
  independent work while running, common controls and completed physical ownership
  were recorded. A separate immutable-receipt derivation proves exactly 1,003
  manifest entries, 1,001 files and 2,772,063 bytes, with every hash matching and
  unselected folders excluded. Its original family receipt remains failed because
  the harness read an obsolete operation manifest field. The derived proof is
  `r110-canonical-download-proof.json`; it is not a full Q1–Q9 or final-race pass.
- R111's Claude attempt stopped before inference because the harness gave provider
  setup only five seconds. Normal shutdown and actual cleanup completed. R112
  uses the plan's 120-second setup diagnostic; product timeouts are unchanged.
- R112, clio-agent `66dba3d6` / GACT `954a2a33`: actual Claude/Haiku (configured
  resolution `claude-haiku-5-5`) passed both idle and post-Stop Question cases.
  The model received immediate handles, did independent work while idle-case
  input remained pending, resumed automatically after answers, collected original
  results, and completed later ordinary turns. Each answer has exactly one Core
  recipient-input commitment. Both case verdicts pass. The original overall
  receipt stays failed because a one-case total remained in a two-case harness;
  `r112-canonical-question-proof.json` records the separate two-case derivation.
  These scoped cases do not pass all Q3 delivery modes or final race repeats.
- R113, clio-agent `c459bc67` / GACT `954a2a33`: actual Codex/Luna started a
  background Shell, long Subagent and Question. The parent did independent file
  work, queried still-running work and observed 23 child-Shell output chunks.
  An any wait returned the Shell failure while the child and Question remained
  pending. A 0.1-second all wait expired without cancelling either; after the
  answer, an unbounded all wait collected failed/completed/completed outcomes.
  The parent retained one assignment across the collection-phase feedback and
  read the failed result again with the same reference. Real child/failure files
  and exactly one committed notification per outcome were independently checked.
  PowerShell returned 1 for the Python child's declared exit 7, and the model
  honestly reported the observed shell code. The original harness receipt remains
  failed because it parsed a clipped UI preview; the actual model had already
  finished. R115 reads complete, integrity-checked committed observations from
  Core and records both context-call and UI-invocation identities.
  `r113-canonical-mixed-proof.json` is the separate scoped derivation. The wrong
  cursor used for a different handle set was rejected; that is not cursor-recovery
  acceptance. This does not pass all Q2/Q4 modes or final race repeats.
- R116 on clio-agent `5392544d` / GACT `cecfb4ee` reproduced a real missing
  parent notice. Actual Codex/Luna paused a child while its accepted background
  Shell continued and completed. Authenticated human steering remained pending
  in the paused child, but its parent had no attributed notice. The immutable
  reproduction is `r116-human-notice-defect.json`; the family remains failed.
  Owned tasks and service settled, and its disposable profile/temp roots are absent.
- R117, clio-agent `50e1fdeb` / GACT `cecfb4ee`, failed because the model
  supplied a nonexistent working directory. The native Shell honestly settled
  `cwd_not_found`; no task-code change was made for that model error. The original
  failed receipt and independent final-custody receipt remain. Its disposable
  profile/temp roots are absent.
- R118 on the same pair passed actual Codex/Luna pause, steering, resume and
  restart. Background Shell completed while the child stayed paused; queued
  steering and the original result reached the resumed model under its original
  assignment handle. Restart used a new handle in the same session and made a
  fresh result read on the inherited Shell. The command ran once. Core capture
  proves attributed parent steering content existed. A separate read-only
  parent-response audit exited without a completed proof, so actual parent
  acknowledgement of that steering is unverified. The service exited zero;
  tasks settled and the profile/temp roots are absent.
- R119 on that pair passed real-service desktop/390px phone cancellation.
  The identifying dialog warned about descendants, kept assignment text behind
  disclosure, and remained inside the phone viewport when expanded. Keeping
  work running issued no control request; confirmation issued exactly one.
  The child and its native background Shell settled cancelled after the original
  process and its recorded grandchild retired. Actual Codex/Luna woke, collected
  the cancelled child and acknowledged the human action. The attributed notice
  has exactly one Core recipient-input commitment and no pending duplicate.
  This is scoped cancellation acceptance: native provenance returned errors in
  the isolated bare-Core configuration, so full Q9 remains incomplete. The
  service exited zero with no active owned tasks. Browser context closed, its
  idle controller was retired, and profile/temp roots are absent. Bounded
  receipts and five selected screenshots remain; no archive was created.
- R120, clio-agent `c3835984` / GACT `cecfb4ee`, recorded an actual external
  MCP handle, independent model work, input-required and expired waiting. Its
  harness looked only at recipient-input tool observations and missed ordinary
  MCP observations in the same Core context lane. The failed receipt remains.
  A read-only audit found the original accepted receipt and all seven tool
  call/observation pairs. Cancellation honestly retained uncertainty after the
  external server reported cancelled. Normal service/stdio shutdown retired the
  owned processes; physical custody and cleanup are separately recorded without
  promoting historical uncertain task rows to settled outcomes. The disposable
  profile/temp roots are absent.
- R121 on the same pair passed the corrected external MCP input case with actual
  Codex/Luna, native FastMCP Tasks and stdio. The explicitly synthetic workload
  uses the production server, SDK, CLIO task boundary and model bridge. The model
  received a handle while input remained open, read the sentinel, queried and
  observed the task, expired a 0.1-second wait without cancellation, and invoked
  a separate inline MCP tool. After the operator supplied an unpredictable value
  through the native input Question, the model woke and freshly read the original
  task result containing that value. Core records one final-outcome input commit
  and one original model submission. This does not prove partial/lost-update
  input, reconnect or persistent provider jobs. Service and transports exited
  normally; the cleanup receipt records actual disposable-root removal.

The correction relays confirmed human/composer input through the existing human
control recorder. It uses the accepted input's pinned assignment and stable notice
identity; acceptance replay repairs a missing derived notice without duplicating
child input or targeting a successor. Human controls keep the same recorder and
parent-mail format. No execution owner, scheduler, dependency or clio-core change
was introduced. Six regression cases are constructed for CI. Scoped Ruff/format,
Mypy and unchanged removal/size/class/silent-fallback guards pass. R118 provides
the scoped correction evidence above; complete Q3/Q4 and final races remain pending.

The `50e1fdeb` CI run `38865042758` finished failed. Lint, dependency resolution,
filesystem/Flowcept checks and Windows/Linux native service lifecycle jobs passed;
regression shards and flake-hunt failed. The 3.14 shard-zero result is
262 failed / 3,859 passed / 19 skipped / 13 collection errors; these are one
shard's counts, not full-suite totals. Failure and exclusion counts remain failures
or exclusions. Two confirmed obsolete arrangements are being repaired for CI:
the schema suite's removed-invoker generator/callers, and a telemetry fixture's
non-native client. Shared package schema equality and its shadow-detection
assertions remain; the inline telemetry case now uses an actual FastMCP server
and SDK transport, preserving complete spill data, output bounds, structured
evidence and private-metadata exclusion. No production or dependency change
is part of this regression migration; passing execution is not yet claimed.

The subsequent CI run `38889866678` on `c3835984` passed flake-hunt, including
the repaired actual-SDK telemetry scenario. Lint, dependency resolution,
filesystem/Flowcept checks and both native service-lifecycle jobs also passed;
the regression shards were still running at this observation. This is not
full CI acceptance. Further confirmed fixture-scope errors are repaired by
making the existing real Core ARC and watcher fixtures visible to GACT tests
and moving the existing Question application fixture into their shared conftest.
Question answer assertions now require the canonical `question_answer` mail kind,
retaining exact identity/count/backpressure assertions. These fixture changes
have scoped Ruff/format checks; their execution is left to CI.

R103–R105 services exited with code zero and no active owned tasks. Their
disposable profile/data and short-temp roots are actually absent; bounded live,
custody and cleanup receipts remain under `.pytest-runtime/static/`. Authentication
hashes and production source hashes stayed unchanged within each run. The failed
browser launch was settled before the installed test browser was used with a
repository-contained profile. No installed Desktop or clio-core change occurred.

After R110, the retained R106–R110 profile, source inputs, copied data/cache and
short-temp root were also removed. The cleanup receipt confirms both roots are
absent and no active owned tasks or private listeners remain. Bounded original,
derived-proof and cleanup receipts remain; no archive was created.
R111/R112 services also exited normally, original authentication and production
source stayed unchanged within each run, and their disposable profile/temp roots
are absent. The R112 cleanup additionally checked process working directories.
R113's service and read-only Core clients retired, with no private listeners or
active owned tasks. Its disposable profile, scripts, outputs, caches and short-temp
root are absent. Only bounded original/derived/observation/cleanup receipts remain.

`c564083c` repairs pending-assignment empty-presentation handling, preserves real
execution failures, fixes the regression fixture's owner entry point, and repairs
the Stop-status harness check. Scoped Ruff/format pass; fresh source review and
full regression passing are not claimed.

GACT retains the unknown-state fixture correction and raw-state preservation;
the original stronger assertion exposed metadata coercion and was retained.
The attempted updater dependency change did not fix native builds: the zip 4
versions also resolve only to yanked releases. `954a2a33` removes that ineffective
change. `cecfb4ee` repairs the eight observed web regressions: tests now select and
assert the owning conversation for storage work, preserve the missing-owner
rejection, await actual query/UI updates, and no longer infer child completion
from a workflow tool call. No production code, assertion budget or timeout changed.
Scoped formatting/lint and all six guards pass. Fresh workspace CI
[`38861125366`](https://github.com/iowarp/gact-tui/actions/runs/38861125366)
passes lint, types, unit/integration tests and the production build. Browser
e2e/accessibility/visual checks are still running. The three native build gates
remain failed; no Desktop launch or installation occurred.

The initial main clio-agent regression run reached tests after the marketplace
commit was published. Python 3.14's three shards reported 11,582 passed, 714 failed,
56 errors and 53 skipped. The suite still contains obsolete fixture/import calls;
these counts do not identify that many distinct runtime defects. The newer
[clio-agent CI](https://github.com/iowarp/clio-agent/actions/runs/38852002469) is not
green. Current clio-agent [CI on `a557c991`](https://github.com/iowarp/clio-agent/actions/runs/38858339870)
completed with regression failures after the framing extraction; superseded runs were cancelled, not
counted as passes. The [finite nine-family plan](task-replacement-live-experiments.md) and its
six five-repeat race obligations remain the acceptance scope.

All sections below are earlier snapshots, not the current CI or qualification
verdict.

## Earlier snapshot: regression CI started; live experiments designed

The constructed core/GACT test commits are pushed to
`codex/agent-facing-async-tasks`: core `f9538f3f`, GACT `0795157b`.
[Core CI](https://github.com/iowarp/clio-agent/actions/runs/38846834707) is running;
[GACT workspace CI](https://github.com/iowarp/gact-tui/actions/runs/38846793266)
is queued. No pass is claimed. Core PR 1704 is closed, so its existing CI workflow
was explicitly dispatched on the feature branch; GACT PR 590 remains draft/open.

The interrupted local collection completed with exit 0 and no residual run root.
It executed no test bodies. The human replaced the local regression sequence
with CI; no further local tests or live qualification were launched. The
[nine live experiment families](task-replacement-live-experiments.md) distinguish
actual-model, physical/backend and real-service UI acceptance.

Implementation and test construction are done. Regression passing, remaining
bug corrections, final source acceptance and live qualification are separate
outstanding stages. Earlier migration counts below are historical snapshots;
they do not mean test construction is still incomplete.

## Test construction completed after the renewed deadline

Initial production implementation is done. Regression test construction is now
done; regression execution and full live qualification are not done. The human
required the complete test set before further execution, so this phase launched
no pytest collection/tests, CI, product service, model or browser checks.

The [construction map](task-replacement-test-construction.md) maps all 60
regression obligations to 61 written test files and separates five process/live
gates. It includes the six pending-work empty-wake cases, two declared workflow
executions with grants/messages/replies/observe/wait, partial external-input
answers, Core-backed composer/Question/watcher fixtures, and session-grant UI.
The old 15-file import inventory was incomplete: additional runtime-field and
direct-spawn fixtures also required replacement. Static AST inspection now finds
no missing production bindings or syntax errors. Scoped Ruff is clean, Mypy
passes for seven new/shared fixture modules, and GACT TypeScript passes with the
2 GiB budget. These are static checks, not executed regression tests.

GACT test-only commit: `0795157b5652efb8a497950cdc92344eec5bbca3`, based on
`0a4ca5d5915a0add61cd5048b742161092468481`. Its production files are unchanged.
Core's last production-changing commit remains `00b3092d`; the known empty-wake
bug and Claude Fable NO-GO remain. Neither deadline's UNDONE result changes.
No merge, release, installation or accepted-task cleanup is claimed here.

## Source and deadline

The last production-changing commit is core `00b3092dc6a31fe1f76fe80a5c87ffe462a4ba33`;
Its finalization correction has Astra GO but Claude Code Fable NO-GO as a complete
correction. Fable accepts the reproduced-case patch but identifies a remaining
empty wake segment with other owned work pending: presentation-only empty output
can still fail the assignment. That source blocker remains unresolved. Both
reviewers accepted predecessor `ff9dc136630a5f329afa27a8ea0263dbe2fbb343`.
GACT is
`0a4ca5d5915a0add61cd5048b742161092468481`; marketplace is
`1a9b8d0337217950a2b44c303a8d22547d52d756`.
The runtime tuple remains FastMCP/fastmcp-tasks 4.1.0, MCP 2.0.0,
Docket 0.26.2, Python 3.14.6 and iowarp-core 2.3.1.

The focused correction after accepted `e581cfd5` fixes Question presentation:
missing/empty agent-routing metadata now remains absent, matching the optional
UI schema. A real Core plan-approval regression exposed the invalid empty-string
projection. The new Core-backed routing contract and plan-pause preservation
cases pass. Astra and Claude Code Fable both independently accept this correction;
the source verdict does not qualify the remaining regression or live gates.

A fresh Codex/Luna Question run on ff9dc136 exposed an operation-only segment
being marked `empty_response`. R96 reproduces that outcome through real Core and
the FastMCP Question boundary. 00b3092d evaluates recorded operation output before
classifying a response as empty and honors explicit yield; it adds no assignment
or delivery policy. Both default and explicit Question-yield regressions pass,
and the genuinely-empty-response regression still passes. R95 first stopped at
an obsolete HTTP-200 fixture assertion; R97's old negative case stopped at the
deleted runner `_in_flight` fixture. Those failures remain recorded. The shared
fixture now requires HTTP 202 plus a handle and the current loop retirement
boundary. Scoped Ruff/format, Mypy (three files) and all four source guards pass.
R100 is the affected actual-model rerun on the new source. It records an error-free
operation-only `end_turn`, the original assignment still yielded and the Question
still pending. Its ordered-mission gate failed because the model omitted the later
query; no full Question-family or final-candidate pass is claimed. R100's owned
work/processes are settled; profile cleanup is being audited.

R79 records one actual Codex/Luna native-family Shell execution on predecessor
source: immediate handle, independent file read between two running snapshots,
progress/output observation, an expired wait with work continuing, unbounded
collection and a subsequent stored-result read. Actual exit code is zero and the
completion file hash is
`89174256781fcf055fd72081947b8ec17c709ef97c9b325fdb903839dad42166`.
The original harness receipt remains unchanged: its old field-name reader marked
the run failed. `r79-canonical-model-proof.json` separately derives the scoped
pass from canonical `kind`/`status`, confirmed nonterminal snapshots, original
invocation order, backend result and filesystem evidence. A preceding WebSocket
attempt closed before tool execution and remains a failed live attempt. No
production patch was made for it. These are individual proofs, not Q1/Q2 or
final-candidate acceptance.

The evidence reader now also requires the independent tool call to start after
acceptance and the later query to start after the read result. Negative controls
reject favorable result ordering from preaccepted/batched calls. R93 passes that
contract; R94 confirms that the original immutable R79 transcript still meets it.

The two-hour checkpoint was 21:45:05 UTC / 4:45:05 PM Chicago. It remains
**UNDONE**: Fable's last source verdict arrived at 21:45:08.409 UTC.
Source acceptance afterward does not retroactively satisfy that deadline or
qualify a release. The human renewed the checkpoint for 2026-10-16 01:14:18 UTC
/ October 15 8:14:18 PM Chicago. That checkpoint checks implementation convergence,
executed regression checks and actual-model verification separately.

## Regression migration — historical construction snapshots

Before construction completed, the source audit found 35 test files naming removed modules or
controls, plus test-helper references. This is a regression-suite migration
snapshot, not a current backlog or evidence that deleted owners remain in production.

The first batch replaces old registry/inbox arrangements with actual Core
assignment records and the recipient-input commit. It retains card, feedback,
context and artifact-writer assertions. Provider setup drops the deleted special
Relay dependency. A2UI test clients now own application startup and shutdown;
the opted-in domain-tool fixture dispatches through the current MCP boundary.
It creates passive test assignments, without starting a model worker.

Collection succeeded for 211 cases in the eight affected test modules. Collection
does not mean execution. Nineteen selected cases passed individually and
sequentially with one worker: three busy-feedback cases, four pack/action/Question
cases, five card cases, five artifact-writer cases and two provider-bind cases.
The busy cases use actual Core admission and occupied TurnRunner slots; only
model execution is held in tests. Card fixtures include the production
delegation's message-only return grant. The Question case uses the sole Core
Question owner and preserves selected context, action identity and human
attribution. No model-inference qualification is claimed for these tests.

The old idle-producer `delivery=start` expectation is replaced with queued
steering plus an exact Core admission/turn/content/revision assertion. TurnRunner
alone decides admission. Failed legacy fixture arrangements remain recorded in
earlier receipts; they are not counted as passes. Scoped Ruff/format checks pass
for all ten changed test files, and Mypy passes for the shared assignment/context
fixture. Production source, dependency files and submodule pins have not changed
since the accepted review.

The refreshed AST inventory still finds 29 files with removed-module or missing
test-helper references, including relative imports. This is a minimum inventory;
obsolete runtime-field arrangements also need migration. The regression suite is
not yet coherent or CI-qualified. Its remaining work is separate from the
reviewers' accepted production-source verdict.

The second migration replaces artifact lineage, document-preview publication,
context references, Question expiry and generic tool telemetry arrangements.
The refreshed inventory finds 23 files with removed-module or missing-helper
references. Canonical wait presentation and the shipped wait/message aliases
remain asserted against the shared implementations. Scoped Ruff/format checks
pass for seven changed test files; Mypy passes for the assignment helper and
Question expiry cases. Twenty-four selected cases passed individually and
sequentially; the two initial failures described below remain recorded. Source
implementation, dependencies and gitlinks remain unchanged.

Two initial regression failures remain recorded: transform-metadata teardown
exceeded the 120-second test limit, and a composer case missed its five-second
runner-admission assertion. Their reruns passed without production or timeout
changes; the causes remain unproven. The timed-out case's exact private daemon
and console helper were retired and its owned runtime root removed. Later
selected cases completed their normal cleanup. These are regression results,
not final-candidate model acceptance.

Bounded D execution-repository receipts are under `.pytest-runtime/static/`:
`r56-reviewed-source.json`, `implementation-deadline-current.json`,
`r57-current-retired-bindings.json`, `r57-test-migration.json`,
`r58-test-migration.json`, `r60-test-migration.json`, `r61-test-migration.json`,
`r62-test-migration.json`, `r63-provider-setup-migration.json`,
`r60-retired-test-bindings.json` and `r63-migration-custody.json`.
The second batch adds `r64-test-migration.json`, `r64-timeout-cleanup.json`,
`r65-metadata-diagnostic.json`, `r66-artifact-context-question-migration.json`,
`r68-composer-telemetry-checks.json`, `r69-retired-test-bindings.json` and
`r70-wait-compatibility.json`.

The third migration removes four more retired test dependencies; the AST audit
now finds 19 files requiring migration (a minimum inventory). Eight selected
cases pass: optional Question routing, real plan-pause preservation, MCP input
exhaustion retaining uncertainty, paused remainder writes, evidence-parser
negative controls and three strict transcript traces. Capturing the traces was
not counted as acceptance. The reviewed baseline changes are exactly: no
invented client message ID, one user-created event instead of duplicate
publication, removal of the retired input projection and resulting identity
renumbering. Original assistant content, tool events and runtime provenance are
otherwise identical. Strict comparisons passed with regeneration disabled.
Receipts: `r72-question-projection-fix.json`, `r74-plan-and-mrtr.json`,
`r80-current-contract-regressions.json`, `r81-transcript-baseline-capture.json`,
`r82-baseline-review.json`, `r82-transcript-baseline-assertions.json` and
`r83-retired-test-bindings.json`. Failed intermediate fixture expectations remain
recorded; production was not changed to restore them.

## Qualification still required

The fourth regression migration removes special Relay expectations and retired
task-fold fixtures while retaining generic catalog/trace reads and Claude pool
algorithms. Fresh tests require historical transcript reads to remain immutable
and provider release to occur exactly once after physical worker retirement in
normal, failed and stopped turns. Thirteen selected cases passed individually
and sequentially. The first stream-order attempt still targeted a deleted
blocking queue; its migrated asynchronous-queue observation passes with the
same exact end-before-reset assertion. The initial failure is retained in R87.
The minimum obsolete-binding inventory now contains sixteen files. Scoped
Ruff/format and lifecycle-test Mypy checks pass; production remains ff9dc136.
Receipts: `r84-wire-contract-migration.json`, `r85-provider-retirement-migration.json`,
`r86-provider-abort-and-collection.json`, `r86-retired-test-bindings.json`,
`r87-provider-sdk-fixtures.json` and `r88-provider-stream-order.json`.

The full acceptance ledger remains authoritative. Q1–Q9, R1–R6 repeated five
times, migration idempotence, current-head CI and real-service desktop/phone
review remain incomplete for the reviewed tuple. R53's actual Codex/Luna Shell
and idle/post-Stop Question runs used predecessor core `9e94f0ee`; they are
useful affected-path evidence, not final-candidate acceptance. Reviewer CLI
execution, tests and collection do not replace actual model acceptance.

Shell, Download and Indexing use one FastMCP/Docket execution family. Their
bytes, hashes, manifests and process cleanup still need workload-specific proof.
Relay has no special execution path or qualification gate in this replacement.
Installed Desktop, authentication, defaults and released pins are preserved.
No target-branch merge, tag, release, publication dispatch or installation has occurred.

## Owned state

All recorded source-review processes and the R53 live service/processes are
settled. Bounded review receipts remain outside the disposable review profile.
Automatic review rejected removal of the R52 runtime/temp roots and, separately,
the R47 isolated review profile before either command ran. Those exact roots
remain human-manual-only: no retry, bypass, delegation, move, parent deletion,
reuse or mutation. Audits and rejection receipts preserve the actual outcome;
no absence or recovered-free-space claim is made. Earlier protected boundaries
remain unchanged.

The fresh R73 Claude review process has also exited. Its separate 9,817,180-byte
cache removal was rejected by automatic review before execution. The exact
`.pytest-runtime/review/r73-question-routing` root is now human-manual-only, with
the same no-retry/no-reuse boundary. Its bounded verdict, prior audit and rejection
receipt are retained outside that root. The R74 timed-out MCP test's private
daemon and console helper were identified, retired and its owned test root removed.

The R61/R62/R63 case receipts record process identities and disposable-root
settlement. All recorded matching processes have exited and all tracked runtime
roots were absent after their cases. The rejected roots were not retried,
re-audited or reused during this migration batch.

R76–R79 isolated service families have exited and their disposable profiles,
Core storage and copied authentication are removed, with no original-auth or
production-source changes. R76 stopped at readiness under a pipe-based harness;
R77 exposed the harness's initial-idle race before any tool work; R78 records the
failed WebSocket attempt; R79 contains the scoped native-family proof above.
Their bounded receipts and cleanup audits remain under `.pytest-runtime/static`.

R90 failed before model execution at Core IPC binding. A shorter repository-owned
temp path allowed the next source service to start. R91 records an idle Question
answer waking the model after explicit observation-order clarification; its Stop
case proved that an actual stopped wait left the Question pending, then the harness
misclassified the expected cancelled turn as failure. R92 records the independent
empty-response defect above. All R90–R92 service processes are settled and their
disposable profiles/short temp roots are absent. Their original failed receipts
remain unchanged. R100 owns fresh data and processes; no old manual-only root is
reused. Complete Question qualification and final-candidate acceptance are pending.
