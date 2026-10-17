# Tasks replacement status — October 17

## Overnight live verification and CI corrections

Live verification is the priority under the renewed human goal. CI is checked
between families; failures remain failures and do not substitute for actual-model
or real-service UI evidence. Initial implementation is done; regression repairs,
bug corrections and qualification remain in progress. clio-core is unchanged.

### External MCP observation boundary — CI pending

Complete `e7094280` Python 3.14 CI contains 11,991 passes, 427 failures, four
errors and 53 skips. All seven finalizer cases pass. Permission coverage has
47 passes/two failures: the catalog placeholder corrected in `4ba4a69b`, and
a production external-call failure. Its real application-loop SDK test reaches
synchronous semantic-event persistence from the observer, which the unchanged
off-loop guard correctly rejects.

The existing synchronous external-tool entry now owns permission and both
observer phases on the same worker. Its native client construction and SDK call
remain on the application loop under the existing external owner. The async entry
delegates through the existing owned-call boundary and waits for actual worker
retirement. The obsolete private-loop/thread fallback is deleted. Invocation
identity is captured on the observing worker before SDK dispatch; no new task
registry, scheduler, observer worker pool or driving policy is added.

The real FastMCP/SDK regression now covers both sync and async callers and requires
application-loop client construction, one backend execution, unchanged read-only
permission behavior and matching nonempty invocation/start/completion IDs. The
factory-routing case now uses the real application, Core assignment and SDK;
three obsolete fake-client classes are deleted. Its exact transport assertion
now names the actual resolved server rather than a synthetic string. The isolated
structured-result unit supplies its hosting loop; all privacy/error assertions
are retained. Its test-double schema spelling and non-suppressing exit annotation
match the pinned MCP API. No execution or test timeout is changed.

Scoped Ruff/format, Mypy and removal/class/size guards pass. No local pytest/vitest
or live model ran. The bounded source receipt is
`ci-external-observer-4ba4-source-audit.json` in the D checkout's static evidence.
The candidate Python-source SHA256 is
`c9771f6c337f0b3bae85c513c9aaaea0c0135d74779d44e6dbea3be2a7b99423`;
the shared snippet remains `3dc3abe51bca664c4cf8a5b9f9426b5bb6fa6fdc9a43f8f9ed59a176cafef55c`.
Native-client/Stop/input/reconnect and invocation-correlation live checks must use
the eventual frozen candidate. R184 source, iowarp-core 2.3.1, dependency pins,
GACT and installed state are unchanged. Full regression and live qualification
remain incomplete; R184's unresolved shutdown still prevents a new live family.

### Shared task instructions and native permission fixture — CI pending

The six provider/role prompt cases and marketplace prompt sweep still expect
pre-R2 prose, including the obsolete claim that every accepted task survives
Stop. They now check the reviewed background/foreground distinction, next-model-
call injection, idle wakes, finite assignment disposition, immediate Questions,
grant boundaries and independent owner delivery. Whitespace normalization avoids
depending on Markdown line wrapping. Provider/role parameterization, declared
tool sets, marketplace coverage and the four other test bodies are unchanged.

Two useful earlier prompt requirements were missing from the replacement text:
child assignments belong to the child, and automatic wakes do not excuse skipping
the human's requested independent work. Three lines restore those instructions
in the existing shared snippet. No provider-specific prompt, execution owner or
admission path is added. The candidate snippet SHA256 is
`3dc3abe51bca664c4cf8a5b9f9426b5bb6fa6fdc9a43f8f9ed59a176cafef55c`;
the frozen R184 snippet remains
`1197ebe2af97fb58158e91ea635bf4be9aa3f2f5c55a4a9b8582b976d650fc4e`.
Affected actual-model acceptance remains required on the eventual candidate.

Two available `e7094280` Python 3.14 shards contain 8,001 passes, 285 failures,
two errors and 40 skips; the third shard is pending. Their permission subset
has 26 passes/one failure and their finalizer subset has two passes. The remaining
permission failure occurs while constructing the test executor from its old
opaque root placeholder. That fixture now uses a real empty FastMCP catalog root
and separately observes the actual mutation namespace. All original assertions
remain: no mutation body or backend-client creation before human approval, one
of each afterward, exact pending card/result and physical thread retirement.
The catalog connection cannot execute the mutation. Budgets are unchanged.

Scoped Ruff/format and Mypy pass. No local pytest/vitest or live model ran.
The bounded prompt audit is `ci-task-guidance-9183-source-audit.json` in the D
checkout's static evidence. iowarp-core, dependencies, installed state and frozen
R184 execution remain unchanged. Full CI and live qualification remain incomplete.

### Recall contract fixtures — CI pending

Four recall-contract cases in `5fe0f422` fail before their behavior assertions
because they construct applications without entering their lifespans. They now
use the existing real Core fixture and actual application startup/shutdown. The
reload case closes its first application before opening a fresh reader, retains
its assignment through Core, and binds that assignment for the agent tool call.
No model is substituted for the missing persistence/conversation owners.

All four test signatures/markers and 27 of 28 original assertions are retained.
The legacy `allow_same_session` policy-label assertion now requires the existing
`allow_core_relationship` decision; two additional assertions pin the exact
session and historical assignment handle. No authorization policy, recall
algorithm or output bound changed. Scoped Ruff/format and Mypy pass; no local
pytest/vitest or live model ran. The bounded source receipt is
`ci-memory-summary-9183-source-audit.json` in the D checkout's static evidence.
Production source remains `f8127171edb610a7d25b931f24effc7b0a0c98e75481421d8bff91f13bee94bf`;
the frozen R184 source and iowarp-core 2.3.1 remain unchanged.

### Model-input additions and historical answer fixture — CI pending

Complete `5fe0f422` Python 3.14 CI contains 11,987 passes, 431 failures, four
errors and 53 skips. All 20 main plan, 19 plan-reuse and 10 plan-variant cases
pass. Stall replanning has 18 passes/two failures: enrichment prepares its
additions, but the actual session worker never binds them for model execution.
The existing `turn_injections` setter had no production caller. The common
worker now binds those additions immediately around module execution and resets
the context in `finally`. The two independent end-to-end assertions remain
unchanged. No new execution or persistence owner is introduced.

Export coverage has 24 passes/one failure. Its 105-answer retention fixture
created freeform Questions without allowing freeform answers. It now declares
that permission explicitly; all 22 original test functions retain their
assertions, signatures and markers. Production Question validation is unchanged.

Scoped Ruff/format, Mypy and removal/class/size guards pass. No local pytest or
vitest ran. The bounded source receipt is
`ci-turn-injections-e709-source-audit.json` in the D checkout's static evidence.
The corrected clio-agent production hash is
`f8127171edb610a7d25b931f24effc7b0a0c98e75481421d8bff91f13bee94bf`.
Fresh CI and affected actual-model acceptance remain required. The frozen R184
source is unchanged; its unresolved shutdown still prevents another live launch.
GACT, dependency pins, installed state and the actual iowarp-core 2.3.1 package
remain unchanged.

### Safe plan rejection and Download wire input — CI pending

The first two Python 3.14 shards on `f9891834` pass canonical modifier retries,
both original invalid-selection cases, auto/interactive approval, immutable plan
reuse and queued busy approval. They expose two remaining failures. Empty plan
answers are refused by generic Question validation before the existing safe-reject
decision can run. The plan-only authenticated boundary now canonicalizes an empty
human response to the already-advertised reject option. Modifier-only selection
still fails, and an added ordinary empty-Question case retains generic refusal.

The all-auto-tool wire test now reaches every tool except Download: its table
omitted the required `paths`, so DSPy rejected the arguments before the observed
body ran. That fixture now supplies a valid missing path with its missing source,
keeping provider/network operations out of this test and retaining the unchanged
every-executed-call assertion. No Download production code changed.

All original assertions are preserved; two parameter cases add modifier-only and
ordinary empty-input coverage. Scoped Ruff/format, Mypy and removal/class/size
guards pass. No local pytest/vitest ran. The bounded audit receipt is
`ci-plan-safe-reject-0d71-source-audit.json` in the D checkout's static evidence.
The current production hash is
`7ffd923c684ff07bdb3b3e39128b0b6bb43d61eadcee2019e661a26b436d0f89`.
Fresh CI and actual-model acceptance remain required. The still-live R184 source,
GACT, dependencies and clio-core 2.3.1 remain unchanged.

### Plan/playbook owner fixtures and complete Question export — CI pending

Six approval cases in plan reuse, plan variants and stall-playbook continuation
now enter the actual application lifespan, surface the real plan Question and
answer through the authenticated HTTP route. They share the existing approval
setup, including a real model hold, and inspect the indexed Core continuation
mail. Nine fabricated Question/answer/resume helpers are deleted. Save-failure
injection occurs during actual immutable-plan capture, before approval.

All original behavior assertions are retained, except the two synthetic callback
counts replaced by a count of confirmed Core continuation items. The no-playbook
case additionally requires the approved mode and a queued continuation, preventing
a rejected/no-op answer from satisfying the absence check. AST comparison also
confirms that extracting the shared approval setup preserves the original owner
operations after substituting its explicit session-id argument. No model runs
in these unit scenarios; they are not live acceptance.

All `8db0a28d` Python 3.14 shards are now available: 11,963 passed, 453 failed,
four errors and 53 skips. All three transport cases, all eight strategy cases and
24 of 25 export cases pass. The remaining export case lacked the real Question
commands for its 105 historical answers. Its data-only fixture now installs those
commands on the same confirmed writer; every retention/correlation assertion is
unchanged. No competing store or execution owner is introduced.

Scoped Ruff/format and Mypy pass for all five changed test modules. No local
pytest/vitest ran. Fresh CI remains required; the production hash is still
`7ffd923c684ff07bdb3b3e39128b0b6bb43d61eadcee2019e661a26b436d0f89`.
The broader regression baseline and final live qualification remain incomplete.

### Finalizer and MCP permission owners — CI pending

Complete `6ba52a32` Python 3.14 CI contains 11,981 passes, 436 failures, five
errors and 53 skips. All 20 plan cases, all 13 short-MCP host cases, all 13
catalog cases and the every-auto-tool wire check pass. Permission coverage has
45 passes/two failures; finalization has five passes/two failures. These are
scoped regression results, not a green baseline or model acceptance.

The remaining finalizer cases reach child-resource authorization, which requires
the real conversation owner. Their unit app factory now owns startup/shutdown
and creates the Core assignment record. It starts lazily at the same point as
each former builder call, preserving custom-hook setup before startup and
off-loop construction in asynchronous tests. The prologue inputs and every
original error/cancellation/minter assertion remain intact; no model segment is
launched for these unit cases.

Both remaining MCP permission fixtures now use actual in-memory FastMCP servers,
native SDK clients, tool catalogs and recorded assignments on the application
loop. The mutation case still requires the exact pending card and human allow
response; it additionally proves zero transport creation before approval and
one body execution afterward. The read-only case retains its exact response,
requires one body execution and no permission card. Three fake-client booleans
are replaced by these stronger execution counts. RPC/thread/test budgets and all
other original assertions/markers are unchanged.

Scoped Ruff/format and Mypy pass. No local pytest/vitest ran and no production
code, dependency, installed state or frozen R184 file changed. Fresh CI remains
required for these fixture corrections.

### Initial plan-answer correction — scoped CI evidence, wider acceptance pending

Exact `5d21491c` CI exposed a plan-answer mismatch: the question advertises
`clear_context` as an auxiliary option, while generic single-choice validation
rejects it alongside the primary approval decision. The authenticated plan-answer
boundary now canonicalizes that modifier into answer metadata before the existing
Question owner validates and records it. Ordinary choices and permissions retain
their existing validation. The explanatory option text now correctly distinguishes
fresh model context from retained session history.

Four added cases cover two primary decisions, duplicate modifiers, canonical
answer retries and an ordinary option with the same name. The pre-existing plan
cases retain their original assertions except one architecture-dependent busy
check: paused admission can briefly reserve the owner while examining mail.
Its replacement requires both the public paused state and no committed model
input for the resume notifications. AST comparison confirms all other original
assertions, test signatures and markers are retained.

The all-auto-tool wire test timed out in the real permission gate, with no human
responder. Only that test now explicitly selects the existing session approval
policy for its harmless missing-input calls. It still traverses the production
gate, executes actual tool bodies and retains every original wire assertion.
No permission policy or timeout changes in production.

Scoped Ruff/format, Mypy for all five changed code/test files and
removal/class/size guards pass.
No local pytest/vitest ran. This initial correction's production hash:
`43593e67ded67853b1b89c387a5b852f3a497c25b5c38a1a6ca32347afc82978`.
GACT, dependencies, clio-core 2.3.1 and the still-live R184 source are unchanged.

### Export, MCP permission and variant assembly fixtures — CI pending

The next fixture-only migration addresses three exact `5d21491c` setup clusters:
18 export cases lacking interaction projections, 15 MCP cases patching the
removed receipt-module client name, and two child-strategy cases assembling
against a partial application. Export now starts from the real application
builder; client-construction doubles target the actual SDK seam; strategy
assembly uses recorded real child sessions and the installed built-in boundary.
Protocol-alias examples still validate the original camel-case wire fields
through the SDK model, rather than changing their expected normalization.

All original test assertions and markers across the five modules are
AST-identical. Two strategy tests add only the real application fixture argument.
Scoped Ruff/format and Mypy pass; behavior remains pending CI execution. No
production source, dependency or runtime identity changes in this batch.
The bounded audit receipt is `ci-fixture-migration-f989-source-audit.json` under
the D qualification checkout's `.pytest-runtime/static`; it also verifies that
the still-running R184 production files retain their original frozen hash.

The first available `8db0a28d` shard passes nine export cases and one
streamable-HTTP transport case. Two permission fixtures still fail in SDK
inference: globally replacing `fastmcp.Client` with the test class makes the
factory mistake that class for the native SDK and interpret fake transports as
real server configuration. Their doubles now enter through the factory's existing
explicit `client_cls` argument, leaving the SDK type and native application
clients intact. All 38 permission-test assertion sets, signatures and markers
remain unchanged; scoped Ruff/format and Mypy pass. This test-only correction
requires fresh CI. No result is claimed for the other shards yet.

### Catalog startup and prologue test inputs — CI pending

Eight catalog cases on `5d21491c` called blueprint activation without entering
the application's lifespan. Their shared client fixture now enters and leaves
the real lifespan, including admission initialization and normal shutdown.
Six prologue/finalizer unit cases instead attempted to obtain a runner-owned
cancel token without admitting a segment. They now supply the real cooperative
token type as a unit input; they start no competing model segment. Their original
failure causes, cancellation checkpoints, minter cleanup, typed events and
persisted-output assertions remain unchanged. Actual runner ownership is covered
separately by the runner/conversation and live lifecycle cases.

AST comparison preserves every original assertion, test signature and marker in
both modules. Scoped Ruff/format and Mypy pass. No production source changed and
no local pytest/vitest ran; fresh CI results remain required.

### Short MCP result conversion — scoped CI passed; model acceptance pending

The declared-presentation loss is repaired in the common clio-agent adapter,
without changing execution owners. `BuiltinTool` now uses FastMCP's public
`Tool.convert_result`; its standard wrapped-output schema and client `data`
decoder preserve JSON values, including null, scalars and lists. Explicit UI
presentation travels through MCP metadata and a local data-only result restores
it in the provider's calling context. It cannot acknowledge task delivery.
The former thread-local channel is invocation-local, and both actual execution
routes clear it on success or failure. There is no new scheduler or result store.

Ten constructed real-Core/real-SDK cases cover seven JSON value forms, overlapping
async declarations, and sync/async failures followed by ordinary untrusted JSON.
All pre-existing short-control assertions, markers and signatures are unchanged.
Scoped Ruff/format, Mypy for the three production files and SDK test module, and
removal/class/size guards pass. Exact `5d21491c` Python 3.14 CI passes all ten added
SDK cases and the original Goal structured-presentation regression. The three
interpreter shards contain 11,924 passes, 487 failures, five errors and 53 skips;
the broad regression baseline remains failed. No local pytest/vitest ran.
Actual-model acceptance of this repair is pending. This repair's production hash:
`4b27e5d132b4fd1884e790b6a1fb08f7fc90ee8552b653694646277a723dbbc6`.
R184 remains frozen on its old source, with unresolved shutdown; the prepared
R185 guard still requires an explicit new source binding after retirement.
GACT, dependencies and clio-core 2.3.1 remain unchanged.

### R183/R184 UI review and unresolved isolated shutdown

New CI on `7e3d026e` reaches the unchanged wait-declaration assertions and exposes
a production schema defect: `ClioNativeTool` wraps an already-nullable argument in
another nullable union. The clio-agent adapter now preserves schemas that already
validate null. Three added regression cases cover `anyOf`, `oneOf` and type-list
forms while retaining bounds, descriptions, defaults and caller-owned input.
All existing assertions remain unchanged. Scoped Ruff/format, adapter Mypy and
the removal/class/size guards pass. Exact `21c4311a` Python 3.14 CI passes the
unchanged wait-declaration case and all three new nullable-form cases. The full
regression baseline and fresh model qualification remain incomplete.
The nullable-only correction had production hash
`174e03587d170482e6567b62fd2ec4e8c2693004525b064131cefff783f65518`.
Dependencies, GACT and clio-core 2.3.1 are unchanged. The live R184 checkout remains
frozen at its earlier source; its files have not been overwritten. The prepared
R185 source guard must be explicitly rebound to the corrected candidate before
that run, after R184 retirement. Earlier model evidence is historical, not
acceptance of this changed tool declaration candidate.

Subsequent read-only Python 3.14 async inspection identifies R184's awaited
dependency: `uvicorn.Server._wait_tasks_to_complete` is inside
`asyncio.Server.wait_closed`, before the application lifespan teardown starts.
The prior thread-only sample could not identify that suspended coroutine.
The harness constructed Uvicorn directly with its unbounded connection grace;
production `run_server` delegates to `desktop_lifecycle.serve_foreground`, which
uses a three-second **HTTP-connection** grace and registers the managed server.
Its shutdown owner also latches runtime reacquisition and discovery shutdown.
This omission makes R184 a launcher/harness failure, not evidence of a clio-core
shutdown defect. Native-work settlement remains a separate unbounded obligation.
`r184-async-task-tree.txt` retains the actual wait chain. A prepared R185 observer
wraps the real builder/lifespan while calling the real `run_server` and managed
shutdown owner; it has not been run. R184's pending force-close question remains
unanswered, and no force-close or subsequent live launch has occurred.

The exact `8bd9501e` CI job log also supplies the cancellation timeout's earlier
cause: FastMCP/Docket raises `KeyError: 'tool:dispatch_blocker@'` before task
acceptance. The fixture registered its test tools after entering the native
lifespan, after Docket captured the worker functions. Production Shell and storage
tools are registered before that boundary. The fixture now registers through a
test-only wrapper immediately before the real `NativeTools.__aenter__`, retaining
the actual SDK/Docket execution, held acceptance and all ten original assertions.
No production registry/driver/cancellation change follows this finding. The
registration correction requires fresh CI; local pytest/vitest remains unused.

CI triage also identified 24 earlier standalone assembly failures at the required
built-in MCP boundary. The optional-schema module and wait-declaration case now
opt into a real application lifespan, recorded Core assignment and production
MCP boundary through the existing test helpers. This addresses four intended
cases without adding a production bypass; other assembly fixtures remain to be
migrated. AST comparison confirms every original assertion in these two modules
is unchanged. Scoped Ruff and formatting pass; these changes await CI execution.
Run `38994982164` on `2715f6fc` has passed native lifecycle checks on both Windows
and Linux and all three lint jobs; its regression shards are still running.
No fresh live qualification or clio-core library change is claimed.

All three Python 3.14 cancellation results on `2715f6fc` now pass: Shell,
Download and Indexing execute their actual native queued-cancellation cases.
The three interpreter artifacts total 11,868 passed, 531 failed, four errors
and 53 skips. This confirms the registration repair for those three cases,
not a green regression baseline.
The prompt-stability fixture now constructs the real `BuiltinBoundary` for
declaration binding only; it starts no client lifespan or workload, and its
authorization callback rejects unexpected execution. All original prompt
assertions are AST-identical. Scoped Ruff/format pass; fresh CI is still required
for that additional fixture migration. Production source remains unchanged.

The observation suite's eight assembly sites now bind tools under the application
they will actually call, and the application helper records an owning assignment
before dispatch. Its four declaration-only cases opt into the real boundary
fixture. Every original assertion and test signature is AST-identical; scoped
Ruff/format pass. This migration awaits CI execution and does not qualify runtime
observation behavior. No local pytest/vitest or fresh live family ran during it.

Fresh `7e3d026e` Python 3.14 artifacts pass all ten prompt-stability cases and all
three original optional-schema cases. The unchanged wait-schema assertion still
exposes the duplicate-null defect corrected in `21c4311a`; that correction awaits
its own CI. `c755e36d` also passes the four native declaration/presentation cases.
Its remaining actual-call setup failures distinguish recorded ownership from
active invocation context: the observation sites now bind the complete recorded
turn identity, and the unchanged catalog-equality assertion covers six newly
attached tools in its call table. The real Goal-status case reaches MCP and
records two results, but loses declared structured presentation data across the
worker/MCP boundary. The common output repair above requires fresh CI/model
acceptance; no test expectation has been relaxed to hide the original failure.

Playbook approval tests now reuse the production Question answer route instead
of copied Question views and synthetic resume callbacks. Their common fixture
pauses the owner through the real control route before inspecting accepted mail;
eligible input on an unpaused owner otherwise correctly races TurnRunner
admission. Original mode/playbook assertions remain, with additional checks for
queued revision content and the preserved hold. All tests/markers/assertions are
retained; scoped Ruff/format pass. This test-only migration needs fresh CI and
supplies no actual-model acceptance claim.

Artifact export and grounding fixtures now explicitly accept the existing real
Core ARC fixture and install the production `TaskHistory` reader. Thirty-two
tests retain their original algorithm assertions while supplying the lineage
source required by descendant walks. Existing child cases still write real
assignment lineage; two unused pre-replacement `_FakeTask` classes and a duplicate
reader construction are removed. AST auditing preserves every test, original
parameter, marker and assertion. Scoped Ruff/format pass; CI execution is pending.
The first `831625ba` artifact also confirms the optional null/default schema case
now passes. Other schema/prompt results are not yet available.

Both actual Codex/Luna direct-SSE runs on clio-agent `d86c9120` / GACT `0f9c00a4`
demonstrated external-task acceptance, independent work, one lost-visibility
attention episode and desktop Work disclosure. The rendered row said "Needs
inspection"; keyboard disclosure retained the original assignment and handle,
with raw backend `working`, connection `lost` and viewport containment. Selected
untouched desktop captures and phone failure captures were visually inspected.
There were no connected-API HTTP failures or page errors in the browser record.

Neither UI run passes. R183's driver treated the four-state Evidence layout
button as a binary toggle and selected Data when resizing. R184 selected Bottom
but the docked panel was hidden after its desktop gutter disappeared on the phone.
The next driver must reopen Work using the actual layout controls. Phone Work,
Runs filtering and final-result UI acceptance remain unverified; no product UI
patch follows these driver assumptions.

R183's original backend completed once; the original model assignment completed
after one final result. API/external/proxy exited zero and the deliberately failed
browser exited one after closing its context. All local processes/listeners were
absent before removing its 514,151,625-byte profile and 2,777,191,463-byte temp root.
The unchanged 29,037,620-byte UI build remains registered for the pending repeat.

R184's backend has physically completed/cleaned; browser context and process are
closed, and its session reports no active task after explicit cleanup controls.
The external server/proxy have retired normally. The isolated API has not exited:
verified API PID `63128`, launcher `29952`, private runtime `45180` on port `30300`.
Its controller is still waiting for normal exit. Read-only py-spy stacks show an
idle application event loop and idle worker/proxy threads; these do not identify
the awaited shutdown dependency. Do not call this settled or remove its live
profile/temp data. The R2 human-force-close question is pending; no force-close
or subsequent live launch has occurred. The installed Desktop and clio-core
library remain unchanged. Bounded evidence is `r183/r184-live-external-recovery`,
UI results/captures/custody, `r183-cleanup*.json` and `r184-shutdown-stacks.txt`.

CI `38991839575` on `e837c3bf` completed failed. All three Python 3.14 artifacts
report 11,865 passed, 534 failed, four errors and 53 skips. The new public SSE
factory regression passes. Preceding `8bd9501e` artifacts report 11,864 passed,
532 failed, six errors and 53 skips; all four migrated observer cases pass.
The three native cancellation cases now reach a 110-second diagnostic timeout
instead of the missing-invocation setup error. Their failure record contains no
application-task stack, so a test-only diagnostic now captures thread/task stacks
and cancels its failed exercise waiter before re-raising. Its assertions, 110/120
second limits, worker settings and production cancellation policy are unchanged.
That diagnostic is not a fix or a passing regression claim. No local pytest/vitest
ran; source/live qualification and the full CI baseline remain incomplete.

### R181 selection failure and R182 actual direct-SSE recovery

R182 passed actual Codex/Luna direct-SSE execution on clio-agent `e837c3bf` / GACT
`0f9c00a4`, production hash
`a9c9ae58b09e073e456ee2f21bcf3746b34f8dff9a1c601871edf97fd5c8ccc6`.
The production provider-selection API accepted SSE. Luna received external task
`task_72506661a0fc464c9fbce698500331b7`, performed an independent filesystem read
while it ran, then yielded assignment `task_eeb30f73ae1f40f490d1dd1caf4661ae`.
The original external job finished and cleaned up while the caller was stopped.
The restarted caller restored the selected SSE model without another selection
write; its fresh SDK client discovered/read the original native backend identity
and captured schema without resubmission. Luna automatically woke, collected the
actual tag/nonce/77 bytes/SHA-256 and completed the same assignment.
All six confirmed inputs retain that assignment, one final result was delivered
once, and only one backend body/`tools/call` ran. Both callers, external server and
proxy exited zero, with no active assignments, pending mail or workers remaining.
Auth and production hashes match. Bounded source/runtime/model/identity/input/RPC
and byte/hash evidence is `r182-live-external-recovery.json`; physical/data cleanup
is recorded separately in `r182-cleanup*.json`. The 496,446,630-byte profile and
1,073,741,824-byte temp root are removed/absent. This qualifies the normal SSE
route, not oversized SSE lines or the full frozen-candidate race matrix.

The two-line factory behavior correction passed scoped Ruff/format, Mypy for the
changed source file and removal/class/file-size guards. Its new regression has
not run locally. CI `38991839575` is running on `e837c3bf`; CI `38991236612` remains
running on the preceding test/qualification commit `8bd9501e`. No passing full
regression baseline or complete Tasks qualification is claimed.

R181 on clio-agent `8bd9501e` / GACT `0f9c00a4` failed before model execution:
the production provider-selection API returned HTTP 400, "A custom HTTP wire
requires its explicit asynchronous counterpart." The factory passed its normal
synchronous wire explicitly into both HTTP engines, which correctly require
an explicit asynchronous counterpart for custom-wire injection. WebSocket
construction was unaffected.

The clio-agent factory now lets each HTTP engine construct its native matched
provider pair, while retaining the existing shared WebSocket wire and custom-wire
guard. A new public `create_lm` regression requires both real HTTP engine/provider
types, independent asynchronous wires and preserved credential/account bindings.
Its execution goes to CI; R182 supplies the scoped actual-model SSE qualification.
No clio-core source/dependency, provider parser or size-limit policy changed.
The failed run's API, external server and proxy exited zero; its 378,117,557-byte
profile and 1,073,741,824-byte temp root are removed/absent. Bounded failure and
cleanup receipts are `r181-live-external-recovery.json` and `r181-cleanup*.json`.

### R177–R180 external visibility and caller-restart recovery

R177 passed on clio-agent `ec3a405f` / GACT `0f9c00a4`, with production hash
`abe140a51dc1cad7205c3f8553549eca2c81da441441bfd4026e024137bc9728` unchanged.
Actual Codex/Luna received a native HTTP MCP handle, performed an independent
filesystem read and yielded. Six real proxy 503s interrupted observation while
the backend kept running. One attention episode reached the same assignment;
repeated failures did not produce repeated wakes. Restoring visibility and
completing the original job delivered one final result. The actual 77-byte output
and SHA-256 matched, with one backend body and one `tools/call`. This is visibility
recovery; R177 did not restart the caller process. All three services exited zero;
its 555,066,857-byte profile and 1,073,741,824-byte temp root are removed/absent.

R178 preserved a failed harness result: bare `build_app()` omitted production
`run_server` startup flags, so its restarted caller stayed agentless. The external
job actually finished once while CLIO was offline. Independent physical retirement
and cleanup removed the 551,249,809-byte profile and 1,073,741,824-byte temp root;
unknown detached exit codes and unqualified persisted task settlement remain
explicit in `r178-retirement-audit.json`. No product patch followed that omission.

R179 enabled the production startup flags and supplied an independent successful
behavior audit: a new caller/client recovered the original backend identity,
and Luna collected its final result under the original assignment. Its controller
still failed a wrong readiness predicate: provider-selection `state` stays `idle`
on boot even when `configured=true` and the model executes. The controller also
expected the legacy `initialize` handshake; this pinned MCP v2 HTTP route uses
`server/discover`. A cleanup helper wrongly rejected Stop's correct HTTP 204.
Those harness failures remain recorded separately from `r179-behavior-audit.json`.
All owned processes retired, and its 496,305,632-byte profile and 1,073,741,824-byte
temp root are removed/absent. The owned Python-cache junction was audited without
following it before removal.

R180 passed the complete corrected check on the same production source. Luna
received external handle `task_ef75cd28a6fa4f3da4e56ec08cc98bb3`, freshly read a
sentinel while its job ran, and yielded assignment
`task_caf5e7e6ae044a18bae1448e6cd7bc10`. The first CLIO caller exited zero; the
original external job then finished and cleaned up while CLIO was offline.
The restarted caller restored its model without a second model-selection write.
Its new SDK client performed protocol-v2 discovery and read the original task ID,
server/session/auth scope and captured result schema; no second submission ran.
Automatic final delivery woke Luna, which collected the real nonce, tag, 77-byte
length and SHA-256 `4e7bb1168da30f2f321a9776bab8490b66d3f5516bb0b00b453aa3437ce918b3`.
All five committed inputs retain the original assignment. One final notice was
committed once; no pending mail, active assignment or worker remains. Both callers,
external server and proxy exited zero. The 495,900,865-byte profile and
1,073,741,824-byte temp root are removed/absent; auth and production hashes match.
Bounded receipts/audits are under the execution checkout's `.pytest-runtime/static`.
These synthetic workloads use actual production server/SDK/CLIO/model routes;
they do not qualify approved-provider jobs, UI recovery or final-candidate races.

CI `38987288853` on `ec3a405f` completed failed. Python 3.14 reports 11,860 passed,
538 failed, four errors and 53 skipped. The restored startup-recovery fixture now
passes; 40 cases in the recently migrated setup modules pass and 26 reach further
failures. Three native-cancellation cases stopped at a fixture missing the required
assignment invocation ID; that setup now supplies it. Four observer regressions
patched the removed `task_receipt.TaskAwareClient` location; they now use the
client-factory/external-call test seams while retaining every telemetry, typed
failure and private-metadata assertion. No production or clio-core change, local
pytest/vitest, timeout/budget reduction or assertion weakening is included.
Scoped Ruff/format/diff checks pass; these fixture repairs require CI.

### R176 busy-goal next-iteration delivery passed

R176 passed on clio-agent `e894dddf` / GACT `0f9c00a4`, with unchanged production
hash `abe140a51dc1cad7205c3f8553549eca2c81da441441bfd4026e024137bc9728`.
Actual Codex/Luna accepted two background Shell handles and a Question, freshly
read the sentinel, declared the two native dependencies and yielded assignment
`task_e0935bc397634d83a41fb28176e28024`. The first background command completed;
its result stayed pending while the second command kept running.

Human feedback then requested one real foreground Shell gate. Its process entered
and the parent's single session worker remained busy inside that tool call.
Another human message and the Question answer were accepted while it ran. Both
remained Core-pending; the confirmed input list and worker count did not change.
After the actual foreground tool returned, both notification IDs appeared together
in the **next model input**, iteration
`msg_user_928d0b6c7116:c4777517a000470e:1`, within the same running turn
`msg_user_928d0b6c7116`. The model reported the new answer, freshly read steering
value and real gate nonce, then yielded again. The first background result was
still pending; the second background command was still active.

Releasing that second command delivered the original dependency outcomes and
completed the original assignment. All twelve confirmed inputs retain one
assignment. Each background/Question final outcome appears once; no pending input,
new assignment, child or worker remains. Both actual 496-byte payloads match their
reported SHA-256 and final answer. The actual goal judge marked completion.
Together with R175's separate idle-goal audit, this supplies current Codex busy
and idle M04 evidence; fresh Claude differences, UI and final-candidate races
remain unqualified.

The service exited zero. All three producer PID/creation identities, private Core
and listeners were absent before removing the 555,621,248-byte profile and
1,073,741,824-byte temp root. Both exact roots are absent. Auth and production
hashes match. Bounded evidence is `r176-live-busy-goal-inputs.json`, the three
result receipts and `r176-cleanup-audit.json` / `r176-cleanup.json` in the execution
checkout's `.pytest-runtime/static`. No clio-core source/dependency changed.

Between families, 24 setup sites in six existing test modules were migrated to
finite off-loop app construction. Prior exact-head CI exposed 24 cases failing
at `task.restore` before their behavior assertions ran. The app still constructs
through the same production function and the Core loop guard remains strict.
An independent AST comparison verifies all non-setup code, assertions, markers
and budgets are unchanged. Ruff/format/diff checks pass; no local pytest/vitest
ran. CI `38985031067` on `e894dddf` subsequently supplied all Python 3.14
artifacts: 11,842 passed, 556 failed, four errors and 53 skips. Thirty-four of
the prior 35 mailbox-read failures now pass. The remaining startup-recovery
fixture constructed a fresh passive `TaskHistory` but never restored its Core
records before requesting the owning assignment. It now explicitly performs
the same data-only restore as production startup; all partial-write, idempotence
and acknowledgement assertions remain. This additional fixture correction and
the async app-setup changes await CI. The full regression baseline is unproven.

### R172–R175 goal dependencies, feedback and Question answers

R175 used clio-agent `d289ea01` / GACT `0f9c00a4`, with production still identical
to `38a8794b`. Actual Codex/Luna set an explicitly unbounded goal, received two
native Shell handles and a Question handle, freshly read a sentinel, recorded
both Shell dependencies with `return_when="all"`, and yielded Session assignment
`task_e36c81924c7344ad9f2825dccb77fb19`. Both command bodies were actually running.

Native output progress changed without another model input. The first command
then completed while the second remained running; its final notice stayed
Core-pending and the model stayed yielded. Ordinary human feedback woke the same
assignment, followed independently by the Question answer. Both inputs reached
the model while the second dependency remained active and the first result stayed
pending. Completing the second command delivered the two results and completed
the original assignment. Thirteen confirmed inputs retain one assignment; each
native/Question final outcome appears once, with no pending input or model worker.
The actual goal judge evaluated once and marked `goal_met`. Both 496-byte files
match their reported SHA-256 and the model's final report.

The original controller is **failed**: an unrelated copied assertion required
every submit to omit its disposition. Actual submits were `yield`, null, null,
null; explicit yield is supported. `r175-goal-behavior-audit.json` independently
verifies the complete recorded idle-goal behavior and actual filesystem hashes,
without changing `r175-live-goal-inputs.json`'s failed verdict. This supplies
scoped M04 evidence; busy-goal next-iteration injection, Claude differences,
fresh UI and final-candidate races remain separate gates.

Earlier attempts remain failed. R172's model explicitly selected a 12,000-token
goal budget and capped before judging. R173 selected a disallowed working
directory for one command; confinement rejected it before its body started.
R174's blueprint still advertised a worker despite its main expert's empty child
list; the model spawned it and the controller incorrectly counted descendant
Shell rows as the two original commands. R175 corrected the experiment's explicit
limits/cwd and actual blueprint manifest, using a single expert. No production
code, confinement rule, task owner, worker limit or diagnostic budget changed.

All four services retired normally with exit zero, and cancellation of unfinished
owned work was confirmed before retirement. All profile/temp roots are absent.
R175 also verified both original producer PID/creation identities were absent;
its 555,822,188-byte profile and 1,073,741,824-byte temp data are removed. Bounded
run, independent-audit and cleanup receipts remain under the execution checkout's
`.pytest-runtime/static/r172-*` through `r175-*`. Original auth/source hashes match.

CI `38982891702` at `d289ea01` passed all 52 Codex direct-engine cases on Python
3.14, including the HTTP fixture contracts. Its full Python 3.14 artifacts still
show 591 failures, five errors and 53 skips; there is no passing regression
baseline. CI identified 35 mail-read guard failures across eight test modules.
Twenty-one test-only mailbox/content assertion reads now use finite off-loop
calls, retaining every assertion, ordering check and resource/guard budget.
Scoped Ruff/format/diff checks pass; these changes are built for CI and were not
executed locally. Other regression failures remain unresolved, rather than being
presumed stale. clio-core remains `iowarp-core==2.3.1`, unchanged.

### R170/R171 historical migration and real-model recovery

R171 passed the scoped startup-migration experiment on clio-agent `2c7469c2` /
GACT `0f9c00a4`, using the unchanged production source from `38a8794b`. Fixture
data used retained legacy semantic-event, context and JSON formats through the
real Core writer; no historical execution owner was imported. Two normal
production-service restarts preserved nine historical tasks, stable handles and
lineage, terminal results, proven input acknowledgements, pending mail, a Question
and a disabled subscription. Identical external task IDs with distinct full
server/session/auth identities remained distinct; their ambiguous short alias
did not resolve. Missing legacy descriptions remained explicitly identified.

The first attempt, R170, failed a harness expectation: its unpaused future queue
correctly promoted a queued message. R171 set the authenticated future-queue Stop
policy before seeding, included the historical child's proven result delivery,
and submitted its human mission as steering. Both corrected migration passes
were stable and made zero native submissions. This is scoped migration evidence,
not acceptance of every historical provider/metadata variant or active job.

Actual Codex/Luna queried the historical results, inspected both identity-bound
MCP outcomes, and yielded on the retained Question under Session assignment
`task_9b58e94f052246e786ed4cbd5a7dc83b`. A real human answer to
`task_migrated_9dd6fbaa76b36c807db2bb5f58982ecb402740d7b469596a31a035b5b8ef7510`
woke that same assignment and reached its confirmed input once. The model
completed with the stored results and actual answer. The future queue remained
paused and its queued/held records stayed retained; no old operation replayed.

All three R171 service runs exited zero. PID/creation-time and listener audits
found no owned processes before disposal. Its 554,065,510-byte profile and
1,073,741,824-byte temp root are absent. R170's corresponding 550,074,013-byte
profile and 1,073,741,824-byte temp root are also absent. Original auth and
production hashes match. Bounded evidence is `r171-live-migration.json`, both
families' cleanup receipts, and the original failed `r170-live-migration.json`
under the execution checkout's `.pytest-runtime/static`.

Exact-head Python 3.14 CI for `2c7469c2` passed the seven repaired approval-input
cases, retry-context case and single-call prompt case. The complete artifact set
still contains 593 failures, four errors and 53 skips: it is not a regression
pass. The next test-only correction gives scripted HTTP fixtures the explicit
async wire required by the provider contract, preserving parser/usage/recovery
assertions and adding a negative case for a missing async counterpart. Scoped
Ruff/format passed; these new changes have not run locally and await CI. No
clio-core source or dependency changed.

### R158 retained mailbox and restart diagnostic

R158 used actual Codex/Luna and the production service on `75bafce8` / GACT
`401efcfe`; production code was identical to `fe705077`. The model received its
Question handle, freshly read a file while the answer was pending, and entered
an unbounded wait. Human pause retired its worker. All 1,005 subsequent public
human messages were accepted under the original Session assignment; Core retained
1,006 mail items at the paused checkpoint, with every new message pending and no
new recipient-input commitment. This is human-input retention, not the separate
positive pending-peer-capacity gate.

After answering and resuming, the actual model processed bounded batches and
completed the original assignment with the real Question answer, random end
marker, fresh sentinel and expected count. All 1,005 message IDs were acknowledged
exactly once across 22 original-assignment input records. The Question outcome
appeared once; no pending input or model worker remained. Core retained 1,009
mail items. Ten production query/pending reads took 4.37 ms total and made no
store calls; this measurement excludes transport/audit writes. A fresh data-only
projection restored the full retained history and acknowledgements in 59.26 s.

The whole family is **failed, not qualified**: the attempt exceeded its 900-second
diagnostic budget during actual service restart, and readiness independently
expired after its 120-second limit. Normal shutdown was signalled when the budget
overrun was observed at 938.69 s. No restarted-model/no-duplicate-wake acceptance
is claimed. The original controller also failed its cleanup HTTP read after the
service had shut down; independent retained-process handles confirmed both API
runs exited zero. All original tasks were terminal before restart. PID/creation
time, listener, private-Core and path audits found no owned live process before
disposal. The 818,499,745-byte profile and 1,073,741,824-byte temporary data are
removed; both exact roots are absent. Original auth and production hashes match.
Bounded receipts are `r158-live-mailbox-retention.json`, `r158-budget-expiry.json`,
`r158-cleanup-audit.json` and `r158-cleanup.json` under the execution checkout's
`.pytest-runtime/static`. No archive or Core-library change was made.

Exact-head CI `38965450538` supplies per-case XML for `75bafce8`. Of the 21 cases
containing the 24 migrated acknowledgement assertions, 17 passed and four failed
on Python 3.14. Remaining failures are not dismissed as stale tests. The retry
route performed its confirmed input write on the application loop; it now joins
the existing finite off-loop helper before returning, retaining input custody
across cancellation. The second fresh-message assertion now requires HTTP 202
and a handle; all its existing idle/delivery assertions remain. The running
message-count and queued-message creation-status failures remain unresolved.
These corrections await CI; no local pytest/vitest ran. The overall regression
baseline, restart performance, final tuple and final repeated races remain open.
Scoped Ruff/format, Linux Mypy for the retry route and all seven source guards
pass without changing guard budgets or assertions.

### Capacity and Question UI checkpoint

R159/R160 attempted an integrated assignment over the actual `75bafce8` CI XML:
11,786 passed cases, 609 failures, five errors and 53 skips on Python 3.14. This
was triage of retained evidence, not fresh test execution. A native background
parser would produce CSV/Markdown/SVG while a child independently reviewed six
real diagnostic samples and the parent requested the human's preferred focus.

R159 failed its browser preflight before model submission: the interactive driver
exited on stdin EOF, and the browser-connected diagnostic expired. The source API
and both browser attempts retired normally. R160 replaced that interactive driver
with harness-owned automatic browser launch. Actual Codex/Luna accepted the
Question, Shell and Subagent handles, then freshly read the CI source file while
the parser was running. The UI driver failed because its unscoped Question locator
matched both the evidence panel and the Open questions dialog. No complete
assignment, Question answer or report acceptance is claimed. Cleanup closed
admission, cancelled the original task trees and confirmed zero active tasks.
The actual parser process, browser children, API and private Core were absent
before disposal. Both profile/temp roots and the old 29,037,249-byte UI build are
removed; original authentication and production hashes match. Bounded receipts
and the inspected real Work screenshot remain under `.pytest-runtime/static`.

That screenshot independently exposed a product defect: compact Shell progress
displayed a raw `clio.terminal.chunk` envelope. GACT's formatter handled legacy
counter names but ignored the shared record's `completed`/`unit` fields. GACT
`0f9c00a4` now formats those canonical owner-reported counters before message
fallback, preserving legacy progress. Four new regression cases cover byte
output, download totals, indexing counts and missing units. They are built for
CI and have not run locally. The next actual-service repeat must verify the
canonical progress label and the completed CI-triage assignment at desktop and
phone widths; it will scope Question controls to their actual dialog. This is a
presentation correction, with no new task owner, backend or Core-library change.

### R161–R164 integrated UI and Question reservation

The repeats used clio-agent `41e8f171` and GACT `0f9c00a4`. R161–R163 failed
harness assumptions: two legitimate Shell labels required scoping to the running
row, the description was the model's assignment rather than a command filename,
and the Question offered choices rather than only a freeform textbox. These runs
are not acceptance passes. Their original work was cancelled and physically
retired before disposal.

R164 demonstrated canonical byte progress (`33 B output`), keyboard disclosure
of the original assignment and exact public handle, and choice selection retained
at desktop and phone widths. The actual Question answer returned HTTP 200 with
the correct owner, handle and selected value. The family nevertheless failed:
one interactions GET returned HTTP 500. The passive UI projection observed the
confirmed Question reservation before posting, then tried to parse its empty raw
status as a posted Question. The API now keeps that reservation discoverable as a
task while reporting `question_posting_unconfirmed` instead of presenting answer
controls. A regression covers the actual between-writes boundary and same-handle
posting. Ruff/format, scoped Linux Mypy and seven source guards pass; regression
execution and fresh live qualification of this correction remain pending.

The retry-context regression now awaits the original turn's terminal event within
its unchanged 30-second diagnostic, rather than treating an initial non-busy
snapshot as completion. Its context-identity assertions remain. No local
pytest/vitest ran. clio-agent CI `38969750109` completed with failures; no passing
regression baseline is claimed. GACT workspace CI `38972121458` passed, including
Windows/macOS/Linux debug builds and the fixture-backed native WebView job;
conditional publication jobs did not run. That CI is not live model acceptance.

All R161–R164 services, browsers, parser processes and private Core processes
retired before removal. Profile/temp roots are absent, and the 29,037,620-byte
reused UI build was removed after R164. Bounded per-run receipts and selected
screenshots remain under the execution repository's `.pytest-runtime/static`.
Original authentication and production hashes match. The `iowarp-core` library
and lock remain 2.3.1; only clio-agent integration and GACT changed.

### R165 actual integrated assignment passed

R165 passed on clio-agent `800858505ae3d0553cf561340e9121a7895c3cd6` / GACT
`0f9c00a47e0aac05b676a4c5fd13c34a6677b7c0`, Python 3.14.6 and unchanged
`iowarp-core` 2.3.1. Actual Codex/Luna received the Shell and Subagent handles,
then independently read the source while the parser ran. The production UI
answered its asynchronous Question at the original handle, preserved the selected
choice across 390/1440-pixel viewports, and showed canonical byte progress and
keyboard-accessible assignment/identity disclosure. No connected UI console or
page errors were recorded.

The original Session assignment `task_5343df970345468496af82a26a690bce` and
accepted child completed. Each Shell, child and Question result was included once
in the parent's confirmed inputs; neither session had pending input. The actual
model's final report contained the verified source head/run, all four counts and
three exact reviewed case IDs. The 614-row CSV and JSON/Markdown/SVG outputs
matched independently checked counts and hashes. Report review passed at both
widths. This triages existing CI evidence, not a new test run or passing baseline.

Both API and browser exited zero, and parser/private-Core/process/listener audits
were clear before disposal. The 574,463,413-byte profile, 1,073,741,824-byte temp
root and 29,037,620-byte UI build are removed; all three exact roots are absent.
The bounded 521,079-byte run receipt, UI/control/cleanup receipts and inspected
selected screenshots remain in `.pytest-runtime/static/r165-*`. Original auth
and production hashes match. This passes the scoped integrated assignment;
required CI, wider recovery/capacity gates and final-candidate repeated races
remain incomplete.

Between runs, three context-reference regressions were migrated without changing
their behavioral assertions: two fresh-message admissions require HTTP 202 plus
a task handle, and the route-only app uses the actual owner's Starlette State
instead of nesting its private dictionary. Scoped Ruff/format passes. These
changes await CI, and no local pytest/vitest was run. CI `38975839687` is testing
the production fix at `80085850`; its incomplete run is not a passing baseline.

### R166 fault-harness failure and confirmed message-count defect

R166 on `2cf82aa8` failed its 120-second fault-boundary diagnostic. The original
Shell ran normally: a reused helper section reassigned `server_code` after the
new native fault hook was constructed. No crash happened, so no recovery pass is
claimed. The corrected harness selects helper function definitions through AST,
asserts a single server definition, and records entry into the intended worker.
R166's API exited zero; all accepted work and owned processes retired. Its
552,129,538-byte profile and 1,073,741,824-byte temporary root are removed and
both exact roots are absent. Bounded failed-run and cleanup receipts remain.

A separate authenticated live read confirmed CI's running-session count failure:
`sess_b4156e17e8a4` reported `message_count=0` while its transcript already held
the accepted user message and its model was running. The transcript projection
folded the existing metrics aggregate but did not refresh session metadata until
finalization. It now derives that cache field from the same folded count after
Core confirmation, without loading an evicted message cache or introducing a
new count owner. Cache-write failure remains projection lag, not loss of the
confirmed input. The existing public running/cold-session regression retains all
its assertions. Scoped Ruff/format and Linux Mypy pass; regression CI and the
fresh actual-service repeat remain pending. No local pytest/vitest ran and the
Core library/dependency is unchanged.

### R167 native effect/result-loss recovery passed

R167 passed the scoped actual-model recovery experiment on clio-agent
`38a8794b21d227e302715a44ae4823d9c0ace394` / GACT `0f9c00a4`. Actual Codex/Luna
received original Shell `task_93ea8f42d1604709bc804548bcad4600`, performed a fresh
independent file read while it ran, and retained the original Session assignment
`task_5ae3550d27f54adfb313c9872cfb7f7c`. At the injected fault the production
workload had made its visible effect and confirmed physical cleanup, but the
registered worker had not returned its result to FastMCP/Docket; Core had no
terminal timestamp or stored task result. The isolated service exited 91.

After restart, the original memory-backed task was reported interrupted with
uncertain effects and `resubmitted=false`. The actual model read that original
result and the filesystem effect before deliberately submitting revised Shell
`task_38b5733fd20c4b1c833c101bac1045d2`. The revision explicitly referenced the
original handle in its command and effect metadata. It did not repeat the
original operation: the filesystem counted one initial effect and one
reconciliation. Both outcomes were committed once to the original assignment's
input history; the original assignment completed with both handles and the real
nonce. There were no pending messages. This does not claim first-class retry
lineage, persistent-native redelivery, external attention-then-final, UI recovery
acceptance or the final repeated races.

The post-restart API reported three messages, matching the three transcript rows.
An earlier count observation landed during the intentional service restart and
is unavailable; it is not count acceptance. CI still needs to exercise the
running/cold-count regression. The initial cleanup guard correctly held disposal
because Windows' venv launcher PID differed from the Uvicorn server PID. The
startup log proves the fault PID belonged to that owned service; process/listener
audits then proved retirement before removal. Final API exit was zero. The
552,751,094-byte profile and 1,073,741,824-byte temp root are removed, with both
exact roots absent. Bounded `r167-live-effect-recovery.json`, fault, effect and
cleanup receipts remain. Auth and production hashes match; Core remains 2.3.1.

Per-case CI XML at `80085850` confirms the new reserved-Question regression
passed on Python 3.12/3.13/3.14. The regression baseline remains failed. Retry's
terminal event can be followed by the pump's finite pending-input inspection;
its test now retains the event and non-busy assertions within one unchanged
30-second diagnostic. Separately, `runner_module_builder` did not commit the
stand-in model's input, unlike the host/scripted helpers. It now uses the same
production boundary before invoking the stand-in. Original single-call and
streaming assertions remain. These test corrections are not executed local
tests; scoped Ruff/format passes and fresh CI execution remains required.

### R168/R169 default assignment and queued delivery

R168 on `5930d933` completed all default-disposition delivery stages but its
controller failed an overbroad assertion banning every `wait_tasks` call. Actual
records show two `timeout_s=0` snapshots collecting already-completed Question
and Shell results. The separate `r168-behavior-audit.json` verifies the actual
default submits, original assignment, delivery guards and 1,152-byte output/hash;
it leaves the controller's failed verdict unchanged. Its profile/temp roots and
all owned processes were retired/removed before the corrected repeat.

R169 then passed the complete corrected experiment on the same production
source/GACT pair. Actual Codex/Luna received Shell
`task_ae845dfe3cb141daa2c6d718e49b7603` and freeform Question
`task_bad41145e89e6442aa8b18c0d1747a2baa138fa7145a3692edd41e9f9c932527`, read a
fresh sentinel, and submitted without an assignment disposition. Session
`task_74789496b51247e5be6a11e91d055f46` yielded while both tasks remained pending.
Ordinary human feedback woke that same assignment; the model freshly read the
steering file and yielded again. The Question answer independently woke it while
Shell was still running. Native completion then woke it a fourth time; it
collected the result and freshly read the output file. With no remaining work,
the fourth default submit completed the original assignment. All four submit
records omit the disposition or set it to null.

Fifteen confirmed input records retain the same assignment ID. Feedback, Question
answer and Shell outcome each appear once; no pending input or worker remains,
and no successor assignment or replacement workload was created. The actual
1,152-byte payload matches SHA-256
`9da82db2049f0330c05676f2192f10ac351054a986fce07e5ce361ac45e27f94` and the model's
final answer. While the original model was running, the public API reported the
correct message count of one. Final count was six. Per-case CI at `38a8794b`
also confirms the existing running/cold-count regression passed on Python 3.13
and 3.14; no result is inferred for unavailable artifacts or the whole suite.

R169's API exited zero. Process, producer PID/creation-time, private-Core and
listener audits passed before removing the 554,860,495-byte profile and
1,073,741,824-byte temp root. Both exact roots are absent. Bounded run/cleanup
receipts remain under `.pytest-runtime/static/r169-*`; auth and production hashes
match. This qualifies the scoped Codex default-delivery behavior, with no fresh
UI/Claude/final-race claim. The broader nine-family/frozen-candidate goal remains
active and incomplete; CI is still failing.

Between runs, the approval-input regression fixture was migrated to off-loop
Core mail/content reads. Its native-answer test now requires the fixture's
existing message projection to remain empty, preserving the no-extra-transcript
message contract instead of incorrectly requiring the fixture attribute to be
absent. All approval/output/media/acknowledgement assertions remain. Ruff/format
passes; the corrected cases are built for CI and were not run locally. Fresh
data-only migration, goal/Question interaction, external attention-then-final,
current Claude routes and final repeated races remain outstanding.

R152 on `f5d0ae42` still failed the strict one-worker physical-control gate.
R153 repeated the unchanged scenario with Core-free async/thread stack capture
and identified the actual bottleneck: both native Docket cancellation listeners
were awaiting `burner-redis 0.1.7` pub/sub `_queue_get` through `asyncio.to_thread`,
while the sole default I/O worker waited on Core. The native Shell worker and
body both had cancellation count zero; the body remained in subprocess wait.
The native cancel RPC had acknowledged without a delivery-error retry. Thus the
OS-control hop correction alone was insufficient: native notification receipt
was starved before the body received cancellation.

`r153-root-cause.json` records matching handles, native identity, actual frames,
backend version/source hash and the executor thread. The resource correction now
routes blocking task-history calls through one lazy application-owned writer I/O
thread. Existing store helpers use the pinned FastMCP SDK's I/O resource instead
of asyncio's transport pool. Core retains record authority; Docket retains native
execution and cancellation. Shutdown drains the writer and awaits actual thread
retirement. No Core library, dependency, execution policy or backend was changed.
Ruff/format, scoped Linux Mypy and guards pass; two resource regressions and a real
native cancellation regression are built for CI, not executed locally. Core
remains 2.3.1.
Both R152/R153 exited normally, all owned work settled after Core recovery, and
their exact disposable roots are removed. Bounded diagnostics remain; no bulk
profile or archive is retained.

R154 on `4ee9ee81` / GACT `401efcfe` passed the scoped actual Codex/Luna outage,
owner-notice and restart check. With the default executor limited to one worker,
pause acknowledged recording-unconfirmed in 4.07 ms; Shell output continued while
the child was held. Explicit cancellation acknowledged in 5.59 ms, and both the
actual Python parent and descendant exited before the private Core process
resumed. After recording recovered, the same child remained paused with unchanged
input IDs and no model worker. Resume completed the original child and parent;
fresh `get_task_result` calls on the original handles each have confirmed tool
observations. Pause/resume/cancel notices and the two terminal results each appear
once in their owning recipients' input records. No generic duplicate pause notice
was present. Service restart preserved those exact IDs with no pending input or
automatic duplicate turn.

The run needed an explicitly recorded pre-outage intervention: the model chose a
foreground Shell for its independent file read, which queued behind the held
native slot. Normal Stop withdrew that queued command as never-started while the
original background process continued. Feedback retained the original child
assignment; its actual file tool then read the sentinel while Shell still ran.
This intervention is part of the evidence, not an unchanged-scenario claim.

Bounded receipts are `r154-live-core-outage.json`, `r154-pre-outage-steering.json`,
`r154-scoped-audit.json`, diagnostics and cleanup receipts under the execution
checkout's `.pytest-runtime/static/`. Both service runs exited zero. Actual owned
processes/listeners were absent before disposal; the 584,170,704-byte profile and
1,073,741,824-byte temporary data were removed, with both exact roots absent.
No installed/authentication/default state or Core library changed. R154 is one
scoped pass, not final repeated-race or all-owner outage acceptance.

R155 on `9dfb4a25` exercised the corresponding actual external HTTP MCP owner,
using production FastMCP/Docket and the production confined Shell algorithm.
Pause returned in 3.67 ms and accepted work continued. Cancellation waited
13.33 seconds, returning only after Core resumed; both physical processes were
still present before recovery. The external owner awaited its intent write and
another queued snapshot read before issuing the SDK request. The correction now
authorizes from the confirmed passive view, defers recording through the existing
Core recovery resource, and sends against the original full SDK identity. Error
attention recording also cannot block the control. Ruff/format, scoped Linux Mypy
and all seven guards pass; a pending-writer external-owner regression is built
for CI. Fresh actual-model proof of this correction remains pending.

The external server subsequently confirmed its own cleanup, and both services
exited zero. CLIO honestly retained `task_state_uncertain` / raw `cancelled` with
no terminal timestamp, because a remote cancellation ACK is not physical-cleanup
proof. The harness's initial zero-active-task teardown expectation did not fit
that contract. Independent PID/creation-time, process-tree, listener, worker and
server-retirement evidence permitted removal of only this disposable profile;
the uncertainty is preserved in bounded `r155-retained-uncertainty.json`, the
original failed-run receipt and cleanup audit. Both exact temporary roots are
absent. No task was rewritten to terminal to satisfy cleanup or acceptance.

R156 on `bdcaba3b` passed the physical external-control gate: pause acknowledged
recording-unconfirmed in 16.85 ms; cancellation returned in 23.02 ms; both actual
processes exited before Core resumed. It failed the subsequent honest-state gate.
The remote terminal reply reached the confirmed writer before the deferred
cancellation intent, and the observer incorrectly published terminal `cancelled`
with `external_acknowledged` settlement and no recorded cancellation request.
The correction classifies every external raw cancellation as cleanup-uncertain,
independent of that write ordering. Late accepted control intent also retains its
request timestamp without changing an already-terminal historical outcome.
No new task authority, cancellation map, scheduler or driver was introduced.
A raw-cancel-before-intent regression preserves the backend evidence and requires
one attention notice, no final result and no delivery acknowledgement. Scoped
Ruff/format and Linux Mypy pass; fresh actual-model proof remains pending.

The failed R156 service and external server exited zero, their process trees and
listeners retired, and the actual shutdown snapshot showed no session workers or
busy reservations. The bounded `r156-retained-failure.json` preserves the incorrect
published state. Disposable profile cleanup proceeds only from those independent
physical-retirement checks; the failed acceptance result remains failed.

R157 on `fe705077` / GACT `401efcfe` passed the corrected scoped external-owner
case. Pause returned recording-unconfirmed in 3.37 ms and accepted work continued;
cancellation returned in 145.27 ms. Both actual processes and the external
workload's cleanup finished before private Core recovery. After recovery, the
original child remained paused with unchanged input IDs. Resume delivered the
attributed cancellation notice and one attention episode. Its fresh result read
reported `task_state_uncertain`, raw `cancelled`, pending true, settlement unknown
and explicitly nonfinal backend evidence. Its zero-timeout wait returned the
original handle pending/uncertain. No outcome notification or acknowledgement was
created for that handle. The original child explicitly completed its assignment
while retaining the unresolved external task.

The parent initially produced a plain final response and default-yielded with
uncertain descendant work. One recorded human completion follow-up went through
the normal mailbox under the same original root assignment. The model then used
`submit(assignment_disposition='complete')`. This cue is part of the experiment;
it is not a zero-intervention autonomy claim. The parent collected the actual
child result; all three attributed control notices were committed exactly once.
Service restart preserved all original input IDs and the full external backend
identity, with no pending messages or duplicate wakes. The external body executed
once across both service launches. The task remained honestly uncertain after
reconnection rather than being rewritten as a completed cancellation.

The audit is `r157-scoped-audit.json`; the parent cue, original run, retained
uncertainty and cleanup have separate bounded receipts in `.pytest-runtime/static`.
Both API runs and the external server exited zero. No model workers, owned
processes or listeners remained. The 554,129,856-byte profile and 1,073,741,824-byte
temporary data were removed, with both exact roots absent. R155/R156 disposable
roots are also absent, with their failures preserved. This is scoped external
control/uncertainty/delivery/reconnect acceptance, not full Q6/Q7 or final races.

Committed-head CI `38952642117` at `bca4e2d7` completed red. Python 3.14 shard 1
recorded 187 failed, 3942 passed and 21 skipped. Earlier `f5d0ae42` CI
`38950482103` recorded 188 failed, 3941 passed and 21 skipped in shard 1, and
216 failed, 3913 passed and 13 skipped in shard 2.
The new pending-writer pause case exposed two human pause notices: the generic
engine outcome plus the attributed intervention. Human synchronous controls now
use only the intervention notice; agent controls and asynchronous restart's
successor/failure outcome remain published. The existing one-notice regression
is retained unchanged; R154 now supplies scoped actual-model notice acceptance.
CI `38957377864` on `4ee9ee81` remains in progress: all three lint jobs and both
native lifecycle jobs passed; all nine interpreter/shard jobs remain running at
this snapshot, with no observed failure. It is not a passing regression baseline.

Subsequently `4ee9ee81` Python 3.14 shard 1 failed with 191 failed, 3940 passed and
21 skipped. The newly built native-I/O case had omitted its required confirmed
assignment; `9dfb4a25` fixes that fixture while retaining custody enforcement.
CI `38958744016` on that test-only correction is running. The common test turn
helper now expects the implemented new-message HTTP 202 acknowledgement and
requires its assignment handle, then retains the original event-driven completion
wait. Other regression failures remain unresolved; neither live evidence nor
these migrations constitute a passing CI baseline.

Current production-candidate CI `38961211259` on `fe705077` is running. All three
lint jobs, both native lifecycle jobs, filesystem contract, bundle-lock resolution,
Flowcept integration and flake-hunt passed; all nine interpreter/shard jobs remain
running at this snapshot, with no observed current-head failure. Earlier red runs
remain failures. No local pytest/vitest ran during these corrections.

Subsequent results on that same candidate are red: Python 3.14 shard 1 recorded
184 failed / 3949 passed / 21 skipped; shard 2 recorded 217 failed / 3912 passed /
13 skipped. Recurring failures include old HTTP-200 expectations for newly
accepted messages, incomplete permissions/task-history fixtures and direct
Core reads from the test event loop. These categories do not classify every
failure as stale. A focused migration updates 24 directly observed fresh-message
acknowledgements across 16 test files to HTTP 202, adding assignment-handle
assertions while retaining behavioral assertions and budgets. CI now writes and
uploads per-shard JUnit results so named cases can be proved executed; missing
reports fail rather than silently disappearing. Coverage artifacts, floor,
interpreter matrix and worker/shard budgets are unchanged. Scoped lint/format and
workflow parsing pass; no local tests ran and no production source changed.

R151 retained a stricter outage failure on frozen `f4a5d05f` / `401efcfe`
(production code unchanged from R149). Actual Codex/Luna root and child ran
native Shell with a descendant under a one-worker default I/O executor. During
the private Core suspension, child pause acknowledged in 3.62 ms and accepted
Shell output continued. Separate Shell cancellation acknowledged in 5.69 ms,
recording unconfirmed, but neither physical process stopped before Core resumed.
The shell workload had queued its OS-tree termination behind Core I/O in that
same executor. The scoped R149 pass with ordinary executor capacity remains
valid, but does not satisfy this stricter gate.

The correction removes that executor hop for the existing OS-container signal
and query calls. Process exit, output-reader retirement and Core cleanup receipts
remain awaited. No execution registry, scheduler, new pool or library change is
added. A real-process occupied-executor regression is constructed for CI, not
executed locally. Scoped Ruff/Mypy pass; fresh R152 qualification is pending.
R150's earlier helper-argument setup failure occurred before model submission.
Both failed families exited normally and their exact profiles/temp roots are
removed, with no owned process/listener residue (`r150-cleanup.json`,
`r151-cleanup.json`).

R149 passed the scoped actual-model Shell outage correction on frozen clio-agent
`2d7bc72d41d13051322b6a7284e60bad5247be17` / GACT `401efcfe`. Actual
Codex/Luna (`gpt-6-luna`, direct WebSocket bridge) again delegated Shell despite
the root-only fixture change; this does not prove direct-root Shell submission.
While the verified private Core 2.3.1 process was suspended for 15 seconds,
authenticated cancellation returned in 28.19 ms with recording unconfirmed.
The actual Shell process and its descendant were both absent before Core resumed;
the static API probe remained responsive. The same Core identity recovered, and
the model collected the original native cancelled result through `wait_tasks`
and a separate fresh `get_task_result`, each with a confirmed input record.
The original root assignment completed. The owning child's control-notice/input
readback was not captured before normal shutdown and remains unverified here.
This is one scoped cycle, not full N14/Q7 or the final repeated race matrix.

`r149-scoped-audit.json` records identities, timestamps, RPC latency and actual
collection commitments. All owned tasks settled, normal API/native shutdown
exited zero, original auth/source were unchanged, and the exact new profile and
temp roots were removed. `r149-cleanup.json` confirms absence and no owned
process/listener residue. Exact production-head CI `38947497486` had eight
successful jobs and ten running at the post-family checkpoint; regression
outcomes and overall CI acceptance remain pending.

The R148 correction is implemented in clio-agent only; `iowarp-core` remains
2.3.1, with no dependency or library changes. Confirmed task/ownership reads use
a short projection lock independently of Core I/O. Restore builds a data-only
replacement view and publishes it only after complete replay. Verified native
cancellation and conversation pause/subtree controls close admission and act
before recording; their acknowledgements explicitly report recording unconfirmed.
The existing application recovery worker confirms the intent/effect and parent
notice later. No new scheduler, task authority or delivery owner was introduced.
Shell cancellation also avoids the storage lookup and shared I/O executor for
its verified identity checks. Four pending-writer/restoration regressions are
constructed for CI; they have not been executed locally. Scoped Ruff, Linux
Mypy (ten production files), and the removal/size/class/vocabulary/instrumentation
guards pass. R149's scoped results are recorded above; R148 remains failed.

R148 on frozen `578d2e91` / `401efcfe` exposed a real Core-outage control
dependency. Actual Codex/Luna initiated native background Shell work with a
recorded process and descendant. The root delegated despite the direct-execution
mission, so this is not direct-root acceptance. The external harness verified
the private Core PID, creation time, binary and profile/config identity, then
suspended that daemon for 15 seconds. A static API `/docs` request succeeded
during the suspension (about 21 ms), but the authenticated cancellation request
did not return, and both physical worker processes remained alive. Cancellation
returned confirmed about 15.51 seconds after submission, only after Core resumed.

The same private Core process recovered. Native work then settled cancelled,
the model collected the original result, all owned tasks retired, and normal
API/native shutdown exited zero. `r148-failed-outage-proof.json` preserves exact
identities/times/metrics and the failed gate; `r148-cleanup.json` confirms both
disposable roots absent with no owned processes/listeners. Original auth,
production source and iowarp-core 2.3.1 were unchanged.

Source shows multiple prerequisites for the control effect: authorization reads
share the Core writer lock, human intervention waits for intent recording, and
native cancellation waits for its Core snapshot before sending native cancel.
Existing outage catches handle failed writes, but do not let controls proceed
past a still-pending write. The correction must keep last-confirmed authorization
available, let the verified owner act before pending recording, and reconcile
attributed notices through the existing Core writer/recovery path. No new task
authority or execution scheduler is justified by this finding. R148 does not
prove a general API freeze; its actual static probe remained responsive.

The A2UI persistence audit found the same loop-blocking transcript write in the
private-source sign-in destination. The dispatcher now awaits the existing
off-loop helper around that finite owner operation. Ownership validation,
idempotency, client-only sign-in handling and credential restrictions are
unchanged. Existing public tests cover three providers plus foreign-owner and
extra-parameter rejection; none of their assertions was changed. Scoped
Ruff/format, Linux Mypy and the existing size/class/removal/hidden-swallow guards
pass. Required regression execution remains delegated to CI.

CI `38936588153` subsequently reported current-head shard failures. Python 3.14
shard 1 has 188 failures/3,940 passes/21 exclusions, versus 191/3,937/21 on the
previous head. The held-result recovery assertion correctly exposed a test
setup omission: a new TaskHistory is empty until its explicit startup restore,
as the production lifespan performs. The regression now calls that real restore
before asserting recovered acknowledgements; all its existing assertions remain.
Other failures include an A2UI private-source login path still writing transcript
atoms on the application loop and older waiting-user/turn-admission fixtures.
These remain outstanding; the renderer-error correction is not a claim that all
A2UI store callers or required CI have passed.

R147 on frozen clio-agent `30a769f2` / GACT `401efcfe` passed actual Claude
`claude-haiku-5-5` child Question/lifecycle qualification. The model created one
child and one Question; both parent and child yielded under their original
assignment handles. Human pause held the child without a model worker. Its
Question answered successfully while paused, but no answer input was committed
until resume. The parent was busy when Stop was requested; accepted child work
was not cancelled. Resume let the child collect its original answer and fresh
file text. The parent woke, collected the original child result and completed.

The independent `r147-scoped-audit.json` requires one answer commitment to the
child, one child-result commitment to the parent, and separate attributed human
pause/resume notices committed exactly once to the original parent's model
input. Both assignments completed without a cancellation request. This proves
the scoped Claude route, not all Q3/Q4 variants, UI or final repeated races.
Original auth and production hashes remained unchanged. Normal API/native
shutdown exited zero, and `r147-cleanup.json` confirms both disposable roots
absent with no owned processes/listeners.

R146's earlier setup remains failed: its explicit blueprint declaration of
`spawn_agent_task` was invalid. The corrected fixture retains its original child
hierarchy and automatic delegation controls. R146 submitted no model work;
normal service shutdown and `r146-cleanup.json` confirm its disposable state is
also removed. No production change was made for that harness configuration.
CI `38936588153` is running on `30a769f2`: nine non-shard jobs successful, nine
test shards running and no observed current-head failure at this checkpoint.
The prior failed CI remains failed; pending shards are not acceptance.

R145 on frozen clio-agent `0755ba0a` / GACT `401efcfe` passed two actual
Codex/Luna production-service recovery cases. The harness exited the isolated
API immediately before the answer's recipient-input write (exit 86), then
immediately after its confirmed write but before returning to model execution
(exit 87). The first answer remained unacknowledged; the second exact input
record remained confirmed. Both original assignments recovered, collected their
original Question answers, read the real sentinel again and completed. Each
retains one Question invocation and one answer-delivery record. The after-write
input is byte-equivalent to its recovered typed record. No replacement Question,
assignment or accepted operation was submitted. This is one case per boundary,
not final five-repeat race acceptance or Core-outage/uncertain-effect evidence.

The final API/native-lifespan exit was normal. `r145-scoped-audit.json` retains
the identities/input/results; `r145-cleanup.json` confirms profile/temp roots
absent, no owned processes/listeners, and unchanged production source and user
auth. R143/R144 remain failed setups as described below.

CI at `527a302e` reports 191 failures/3,937 passes/21 exclusions on Python 3.14
shard 1, and 232 failures/3,905 passes/19 exclusions plus one error on shard 0.
These are per-shard counts, not suite acceptance. One confirmed route failure
is A2UI client-error ingestion persisting transcript records directly on the
application loop. Its correction awaits the existing off-loop helper for the
surface read and every record/transition write. The regression now requires all
three rejected ghost-surface reports to retain both received/failed records
without starting a turn. A held-result regression also now writes an actual
observation in its recipient context instead of supplying unrelated task-content
storage, and checks acknowledgement recovery. No assertion or guard is weakened;
these regressions are delegated to CI rather than claimed locally executed.
Scoped Ruff/format, Linux-platform Mypy for the changed production module, and
size/class/removal/hidden-swallow guards pass. The first Windows Mypy invocation
reported six POSIX-API diagnostics in unchanged imported infrastructure modules;
that invocation remains failed. No type or guard configuration was changed.

R143/R144 did not execute the intended recipient-input crash scenarios. The
generated harness omitted process initialization, then omitted its service-run
list. R143 failed before launching a service. Automatic approval review rejected
its guarded cleanup as "blocked by policy"; the command did not run. The exact
`.pytest-runtime/live/r143-input-crash` and `.r143-live-tmp` residual roots under
the D qualification checkout are now manual-only: never retry, bypass or
delegate their removal. The rejection receipt is `r143-cleanup-rejection.json`.
R144 started an isolated source service but submitted no session or model work.
Its verified source API and private Core process were retired; the no-follow
audit and `r144-cleanup.json` confirm both disposable roots absent and no owned
processes/listeners. These are failed harness setups, not product acceptance.
Production source and iowarp-core 2.3.1 were unchanged.

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
