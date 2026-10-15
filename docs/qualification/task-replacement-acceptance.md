# Tasks replacement acceptance ledger

Revision: R2. Starting source: core `5475042feda49c1354f9f88b19051cb53d7fa740`; GACT `32044a387472b1495f60a24c862c6b9e4292abc3`. All evidence from earlier engines is a source/test lesson only, not replacement acceptance.

Status values: **blocked**, **failed**, **passed**. Initial production wiring is present; rows remain blocked until fresh replacement evidence is recorded. Removing an old test never removes its required behavior below. Source paths are relative to core unless marked GACT. Test doubles belong only in tests; live rows require actual production implementations and models.

Each evidence entry must record candidate identity, invocation/handle, timestamps, raw outcome and bounded receipt path. Required unavailable/skipped cases remain blocked. Harness deadlines are diagnostics:120s native/Core,600s models,900s capacity/recovery. Expiry requires owned cancellation and physical settlement before another family. These are not product deadlines.

| ID | Required behavior | Source/test lesson at starting commit | Prerequisites | Required evidence / expected outcome | Status / current evidence |
| --- | --- | --- | --- | --- | --- |
| F01 | One typed snapshot for all seven kinds; immutable ownership and missing legacy descriptions | gact/task_projection.py; agent_tasks.py; mcp_task_records.py; question_tasks.py | Core writer and typed schema | Fresh public query/resolve tests and actual model Q1 | blocked — fresh replacement evidence pending |
| F02 | Confirmed content-first submission and input writes; no put_many transaction assumption | gact/core_task_journal.py; tests/test_gact/test_task_context_commit.py | Real Core; fault injection in tests | Before/after commit crash receipts, persisted content and replayed fixed input | blocked — fresh replacement evidence pending |
| F03 | One passive Core task and recipient index; bounded hot reads | gact/core_task_journal.py; task_projection.py | Indexed replacement | Read-work measurements with retained history over 1000 messages; startup replay measurement | blocked — fresh replacement evidence pending |
| F04 | Data-only migration twice; stable handles/aliases/lineage/results/mail/Questions/subscriptions; no replay | gact/mcp_task_store.py; assignment_history.py; user_question_ledger.py | Committed legacy fixture formats | Two migration passes, same identities and pending notices, zero backend submissions | blocked — fresh replacement evidence pending |
| F05 | Ambiguous aliases/delivery stay unknown; historical relay stays readable without runtime | tools/mcp_task_records.py; gact/relay_timeline.py | Data-only migration | Collision and missing-description fixtures; no invented receipts or special relay owner | blocked — fresh replacement evidence pending |
| N01 | SDK inline/pre-task re-entry preserved; accepted handle distinctly typed | tools/task_receipt.py; mcp_task_extension.py | Pinned SDK transport adapter | Native and inline MCP contract tests; actual model handle before settlement | blocked — fresh replacement evidence pending |
| N02 | Exactly one ToolTask.result driver, no copied poll/lease/deadline loop | tools/mcp_tasks.py; mcp_wait_ladder.py; task_driver_lease.py | Application-owned SDK observer | Static removal guard, SDK contract tests and wait expiration with work continuing | blocked — fresh replacement evidence pending |
| N03 | Observed session delegates transport; request-local Mcp-Name; auth/options preserved | tools/mcp_task_extension.py; mcp_runtime.py | TransportOptions.session_class | Supported transports, incompatible subclass rejection before effects and pinned-private contract tests | blocked — fresh replacement evidence pending |
| N04 | Strict raw terminal result validation against captured schema; malformed/errors retained | tools/task_receipt.py; tests/test_tools/test_task_receipt.py | Identity-bound observer | Backend malformed/changed/coerced schema tests and raw result evidence | blocked — fresh replacement evidence pending |
| N05 | Immutable task input binding, partial/persisted answers, lost update/reconnect without repeat prompt | gact/task_input_questions.py; tools/mcp_tasks.py | Actual external input-required server | Distinct hyphenated identities, reused-key content rejection and partial/lost-update answer receipts | blocked — fresh replacement evidence pending |
| N06 | Trusted hidden submission reference and unique incarnation; revocation and admission rechecked | tools/native_task_tool.py; task_call_context.py | Registered Docket worker | No forged reference/schema exposure; crossed task/digest denied; late entry cannot reopen withdrawal | blocked — fresh replacement evidence pending |
| N07 | Independent Shell/storage native pools, default 10 and configurable memory/persistent backend | tools/native_task_host.py | Two application-owned native lifespans | Saturated Shell while storage starts; no mounted-gateway execution bottleneck | blocked — fresh replacement evidence pending |
| N08 | Acceptance custody distinguishes rejection/recording-unconfirmed/uncertain; no auto tools/call replay | tools/task_submission.py; gact/task_submission_custody.py | Faultable real submission boundary | Stop and lost-RPC reply evidence, single original submission identity | blocked — fresh replacement evidence pending |
| N09 | Foreground Stop physically cancels Shell; background and Question continue | tools/servers/shell_server.py; gact/turn.py | Native Shell integration | Process-tree markers and final cleanup; immediate handle for background | blocked — fresh replacement evidence pending |
| N10 | Attempt-specific cleanup/withdrawal; external ACK alone not physical settlement | tools/native_task_host.py; native_task_tool.py | Worker incarnation and native cancellation | Queued/started/stale-receipt/unknown cases with actual physical evidence | blocked — fresh replacement evidence pending |
| N11 | One attention episode then separate final; uncertain wait returns pending without terminal/ack | gact/task_controls.py; task_delivery.py | Core publication and observer | Uncertainty repeated without wake spam; eventual final still delivered | blocked — fresh replacement evidence pending |
| N12 | Original provider jobs reattach without transfer scheduler or submission replay; preserve provider submission receipt across lost replies | gact/storage/globus_download.py; storage/store.py; task_recovery.py | Available approved external provider | Original job ID and surviving job outcome; unavailable provider blocks row Provider receipt/native-job rows stay reconnectable; do not classify them using blanket local-transfer interruption. | blocked — fresh replacement evidence pending |
| N13 | Pending-only recovery probes at 1,2,4...30; health success alone clears nothing | gact/core_task_journal.py; task_recovery.py | Core/native outage controls | Idle outage and owner-local recovery receipts; no probing when empty | blocked — fresh replacement evidence pending |
| N14 | Core outage rejects durable admission; trusted pause/cancel acts recording-unconfirmed | gact/human_task_intervention.py; core_task_journal.py | Verified active owner; fault injection | Physical control plus provisional recording and later matching-hold reconciliation | blocked — fresh replacement evidence pending |
| N15 | Shutdown closes admission and awaits owned cleanup/worker retirement without hidden cutoff | gact/server_boot.py; turn_runner.py; tools/native_task_host.py | Isolated runtime with owned work | Shutdown process/worker observations, unresolved visibility and no unrelated process kill | blocked — fresh replacement evidence pending |
| W01 | Download retains approved paths/revisions/provider identity and real bytes/hash cleanup | gact/storage/transfers.py; downloads.py; github_revisions.py | Owned source test data | Actual source/destination byte counts and SHA256, cancellation cleanup before terminal; Globus payload/submission-ID persistence and lost-response regression On restart, lost local native work becomes interrupted and stale materialization remains marked; no permanently queued source hold. Rebuild source-operation cancellation REST through shared task control. | blocked — fresh replacement evidence pending |
| W02 | Indexing enumerates folder metadata off-loop and atomically publishes complete manifest | gact/storage/indexing.py; source_filesystem.py | Owned folder and previous manifest | Actual entries/counts; failed/cancelled/interrupted preserve previous manifest | blocked — fresh replacement evidence pending |
| W03 | Equivalent active indexes deduplicate within session/security scope before submission | tools/servers/storage_server.py:index_inputs | Core reservation and storage native root | Concurrent equivalent requests reuse one handle; changed security/options do not | blocked — fresh replacement evidence pending |
| W04 | Shell retains confinement/output bounds/spill references and explicit timeout | tools/servers/shell_server.py; shell_output.py; runtime/task_process_tree.py | Permitted confined source Shell route | Independent algorithm tests and actual output/process-tree evidence | blocked — fresh replacement evidence pending |
| A01 | Session stable; assignment finite; root/child one engine; original description retained | gact/session_run_tasks.py; turn_spawn.py; assignment_history.py | Conversation engine and Core | Session handle before inference; child yield/download/wake under same assignment Retain session-exclusive strong-reference ownership, startup loop capture, loop-affine reservation, revision gates and release-callback ordering. Structured submit retains declared defaults, required-field errors and signature-derived schemas. | blocked — fresh replacement evidence pending |
| A02 | Yield/pause/resume/steering/recovery preserve assignment; later eligible work creates linked successor | gact/session_run_tasks.py; subagent_restart.py | Core fixed context boundaries | No completion-only successor, no copied transcript; historical handles never retarget | blocked — fresh replacement evidence pending |
| A03 | Restart requires settlement; successor inherits predecessor work rights subject to revocation | gact/subagent_restart.py; task_subagent_owner.py | Explicit cancellation and session lineage | Uncertain restart refuses launch; inherited cancellation affects active original handles | blocked — fresh replacement evidence pending |
| A04 | Model permits release before tools/waits; capacity-one children and same-depth peers progress | gact/turn_spawn_executor.py; turn_spawn.py; turn_forward.py | Per-call inference budget | Constrained actual model nested/peer run with no whole-turn pool deadlock | blocked — fresh replacement evidence pending |
| A05 | Session-owned sync worker; stopping until physical exit; no second worker after waiter cancellation | gact/turn_forward.py; turn_runner.py; providers/codex/direct_engine.py; providers/claude_code_sessions.py | Engine worker ownership | Constrained default executor, Stop/retirement race and worker-count measurements Claude connect-slot cancellation must return phantom acquisitions; no default-pool unbounded queue/lock waits. | blocked — fresh replacement evidence pending |
| A06 | Subtree cancellation closes admission first and includes inherited/delegated/background work | gact/task_subagent_owner.py; turn_spawn.py | Active child plus descendants | Actual descendant process/provider settlement and attempted late spawn denial | blocked — fresh replacement evidence pending |
| C01 | Authorize before lookup/filter/count/page; tree and human/config grants separate rights | gact/task_permissions.py; task_controls.py | Core grants and identity | Hidden handles not disclosed; observe-only redacts description/answer/output | blocked — fresh replacement evidence pending |
| C02 | Indexed mixed query/observe/wait/result; unbounded/zero/positive semantics and independent failure | gact/task_controls.py | Core revisions with atomic snapshot/register/recheck | Mixed real tasks, cursors, matching output, timeout leaves members running | blocked — fresh replacement evidence pending |
| C03 | Owner/subscriber delivery independent; subscriptions require read+observe; revocation rechecked | gact/task_subscriptions.py; task_delivery.py | Core relationships and shared input commit | Peer collection cannot consume owner; revoke before injection suppresses disclosure | blocked — fresh replacement evidence pending |
| M01 | One full-history mailbox per session; max0/unset unlimited, pending peer-only limit includes staged | gact/agent_mailbox.py; tests/test_gact/test_session_mailbox_v3.py | Core recipient index | More than1000 messages retained; explicit retryable rejected admission versus pending accepted | blocked — fresh replacement evidence pending |
| M02 | Human input/controls and accepted results exempt; controls never blocked by capacity | gact/human_task_intervention.py; agent_mailbox.py | Full pending peer mailbox | Pause/cancel physically acts; attributed notice reaches parent | blocked — fresh replacement evidence pending |
| M03 | All producers signal TurnRunner; busy next iteration, idle/postStop auto wake, gates hold | gact/turn_runner.py; loop_inbox.py; composer_runtime.py; goal.py; scheduler_runtime.py | One admission decision | Closing-turn race; no parallel turn; pause/input/veto retains, disabled autonomy/future queues unchanged | blocked — fresh replacement evidence pending |
| M04 | Goal dependencies never hide feedback/Question answers; progress alone never wakes | gact/agent_mailbox.py:pending_session_inputs; task_completion_wake.py | Goal/Question engine integration | Actual busy/idle goal with Question and progress-only output | blocked — fresh replacement evidence pending |
| M05 | Recipient-input commitment sole ACK; before crash pending, after crash reconstruct | gact/core_task_journal.py; task_delivery.py; turn_start_offloop.py | Real Core and fixed iteration input | Automatic/explicit collection races and before/after commit crashes | blocked — fresh replacement evidence pending |
| P01 | ask_user short FastMCP control posts durable Question immediately, no Docket worker | gact/async_user_question.py; question_tasks.py; user_question_ledger.py | Question commands plus UI | Model works after asking; mixed wait; Stop keeps open, cancel dismisses | blocked — fresh replacement evidence pending |
| P02 | Permission and external-input safeguards remain; child Questions route correctly | gact/elicitation_forwarding.py; user_question_pause.py | Actual permission/input channel | Real answer/cancel/partial input handling with parent/child identity | blocked — fresh replacement evidence pending |
| U01 | Compact clickable Work/Observability/Runs, progressive disclosure, honest stopping/lost visibility | external/gact-tui at32044a38 | Replacement service/UI | Desktop/phone actual interactions and physical cancel outcomes; zero page errors | blocked — fresh replacement evidence pending |
| U02 | Authenticated session grant/revoke UI; no model intent or assignment grant expansion | gact/routes/agent_tasks.py; task_permissions.py | Existing authenticated controls | Read/observe/message/control independently allowed/denied and revoked before injection | blocked — fresh replacement evidence pending |
| D01 | Capable root/child/marketplace prompts and tool descriptions explain async/wait/yield/wake/uncertainty | prompt_packs/builtin/runtime/clio.runtime.tasks.md; gact/agents/task_guidance.py | Replacement contracts and capable marketplace roots | Catalog/prompt guard plus actual model actions | blocked — fresh replacement evidence pending |
| D02 | Website walkthroughs use real replacement-service desktop/phone screenshots | site and GACT actual UI | Q9 accepted replacement | Readable walkthroughs with bounded selected media; no old-engine screenshot acceptance | blocked — fresh replacement evidence pending |
| Q1 | Codex/Luna all seven kinds: handle running then independent model action; valid inline MCP | R2 finite live matrix Q1 | All relevant owners available | Source/runtime/model/invocation/handle/timestamp/transcript/backend outcome | blocked — fresh replacement evidence pending |
| Q2 | Codex/Luna mixed progress, cursor/pattern, any/all/expired wait, failure and uncertainty | R2 finite live matrix Q2 | Q1 and shared controls | Real pending work continues; honest per-member outcomes | blocked — fresh replacement evidence pending |
| Q3 | Codex/Luna and Claude distinct delivery routes, goal/Question/child combinations | R2 finite live matrix Q3 | Usable actual provider profiles | Busy/idle/postStop/pause input evidence with no ordinary duplicate | blocked — fresh replacement evidence pending |
| Q4 | Codex/Luna and Claude child/control routes and inherited subtree settlement | R2 finite live matrix Q4 | Q3 and child lifecycle | Same child handle; human notices and physical descendant outcomes | blocked — fresh replacement evidence pending |
| Q5 | Independent sessions and two actual declared workflows | gact/workflows.py; R2 Q5 | Authenticated grants and existing runner | Discovery/replies/observe/wait/subscription/denied control; provenance root/step/session links | blocked — fresh replacement evidence pending |
| Q6 | Actual external MCP/provider input/reconnect/surviving job | R2 Q6 | Available actual MCP and approved provider | Original immutable task/input/job identities; partial/lost-update answers | blocked — fresh replacement evidence pending |
| Q7 | Isolated Core/native outage, migration twice, input crash and lost result after effects | R2 Q7 | Owned isolated runtime; restart permissions | Honest uncertainty, agent inspection and deliberate linked retry; attention then final | blocked — fresh replacement evidence pending |
| Q8 | Native pool isolation, capacity-one children/peers, constrained executor and resource cleanup | R2 Q8 | Independent native roots; actual models | No starvation; worker exit before next turn and bounded owned residue | blocked — fresh replacement evidence pending |
| Q9 | Production service/GACT desktop and phone Questions/grants/cancel | R2 Q9 | Integrated frozen core/GACT pair | Rendered interactions with correct physical outcomes and no UI errors | blocked — fresh replacement evidence pending |
| R1 | Stop/acceptance repeated five times on final candidate | R2 race matrix; related owner lessons above | Frozen tuple and corresponding Q gate | Five fresh passes; any skip/failure blocks | blocked — fresh replacement evidence pending |
| R2 | Late-start/cancel repeated five times on final candidate | R2 race matrix; related owner lessons above | Frozen tuple and corresponding Q gate | Five fresh passes; any skip/failure blocks | blocked — fresh replacement evidence pending |
| R3 | Busy-to-idle arrival repeated five times on final candidate | R2 race matrix; related owner lessons above | Frozen tuple and corresponding Q gate | Five fresh passes; any skip/failure blocks | blocked — fresh replacement evidence pending |
| R4 | Collection/automatic delivery repeated five times on final candidate | R2 race matrix; related owner lessons above | Frozen tuple and corresponding Q gate | Five fresh passes; any skip/failure blocks | blocked — fresh replacement evidence pending |
| R5 | Recipient-input commit recovery repeated five times on final candidate | R2 race matrix; related owner lessons above | Frozen tuple and corresponding Q gate | Five fresh passes; any skip/failure blocks | blocked — fresh replacement evidence pending |
| R6 | Subtree cancellation/admission repeated five times on final candidate | R2 race matrix; related owner lessons above | Frozen tuple and corresponding Q gate | Five fresh passes; any skip/failure blocks | blocked — fresh replacement evidence pending |
| Z01 | Removal complete; denylist production guard; Astra and Claude approve before rebuild | R2 removal manifest and caller inventory | Local deliberate-break commit | Both independent read-only removal reviews; broken head not pushed | pass — independent Astra and actual Claude Code removal approvals at4804dd6f; reports retained; no runtime acceptance implied |
| Z02 | Focused tests sequential/one worker; scoped lint/format/types/guards and exact-head CI | R2 completion gate | Coherent draft replacement candidate | No weakened assertions/resource budgets; required skips fail | blocked — fresh replacement evidence pending |
| Z03 | Freeze actual core/GACT/dependency/schema/runtime tuple before final acceptance | Core gitlink; R2 freeze requirement | Final integrated UI and pointer | Recorded freeze, applicable requalification after any change, exact tuple go/no-go | blocked — fresh replacement evidence pending |
| Z04 | Owned processes/ports/data registered before each family; settled and disposable state removed after | R2 cleanup contract; previous disk-pressure failures | Verified owner identity; no prohibited paths | Bounded cleanup receipts; unknown custody blocks next launch; no new archives | blocked — c1/c2/c3/c4 review caches removal was rejected by automatic review; manual-only, no absence proof. Focused test setup roots were retired by their fixture; replacement pending |
| Z05 | October14 publication only after all gates, release procedure and immediate go/no-go | R2 gated release contract | All required rows pass and qualified tuple preserved | Published version/channel/tag/branch/artifact verification; otherwise exact blocker and no release | blocked — fresh replacement evidence pending |

## Candidate freeze and go/no-go

The independent removal reviews identified the following retained behavioral requirements explicitly. They close documentation gaps rather than add new coordination features or live-matrix families.

| ID | Required behavior | Source/test lesson at starting commit | Prerequisites | Required evidence / expected outcome | Status / current evidence |
| --- | --- | --- | --- | --- | --- |
| F06 | Preserve general missing-context restoration from recorded operations/transcript; no successor copying | StepRecorder.carry_over; tests/test_gact/test_context_recovery.py:199 | Core context lane | Original independent recovery scenarios plus linked-assignment fixed-context checks | blocked — fresh replacement evidence pending |
| W05 | Artifact workspace single-writer proof fails dirty on ambiguity; preserve child artifact return/digest | gact/artifacts/versions.py:_workspace_single_writer; agent_task_artifacts.py; independent artifact/digest tests | Common Core lineage/task views | Conflict/single-writer safety, child artifact attribution and bounded digest/verbatim-result behavior | blocked — fresh replacement evidence pending |
| W06 | Retain source-path bounds, changed-selection/access denial, human source ownership and credential-free outputs | 5475042f tools/servers/storage_server.py prepare_download/execute_storage/storage_result/validate_task_owner | Native storage boundary | 1–1000 relative paths, permission/ownership checks, worker revalidation and no credential disclosure | blocked — fresh replacement evidence pending |
| N16 | Preserve inline MCP transport/error safeguards while deleting task-driver coupling | 5475042f AsyncMCPToolExecutor.call_tool_result; typed_mcp_call_error; spawn diet | Replacement native/inline client routing | Uncertain mutating retry denial, MRTR exhaustion typing, first-call diet learning and namespace ownership Retain direct/proxy MRTR and legacy refusal, activity-staller cancellation and progress-reset behavior for inline RPC safeguards; task acceptance has no whole-call backstop. Remote aliases cannot self-declare read-only. | blocked — fresh replacement evidence pending |
| A07 | Preserve workspace leases, off-loop cold setup, native model attachments, context propagation and turn notices | 5475042f turn_forward.py deleted helpers; native_input_kwargs; turn_start_notices | Single conversation worker/engine | Existing attachment/context/lease/setup behaviors through root and child replacement route Ordinary first-agent construction remains off-loop with the process ARC and selected provider; no relay wrapper. | blocked — fresh replacement evidence pending |
| A08 | Retain existing producer/context/provenance features through the one new owner | Spotter watcher, skill spawn/commission, goal redrive, failed-init retained feedback, parent reasoning, @agent_run, ancestor paths, session export/descendants and deletion | Core lineage/mailbox; retained domain algorithms | Focused public-behavior regressions; no old registries, status admission or context-history copying Rebuild agent-audience elicitation through Core Question commands and the one conversation engine; retain schema firewall/decline/fallback attribution. Child messages reject reserved keys/empty text and refuse cancelled or gone targets honestly. | blocked — fresh replacement evidence pending |
| P03 | Retain atomic answer-versus-expiry arbitration and input routing attribution | 5475042f user_question_ledger claim/stamp helpers; permission/external-input regressions | Core Question commands and existing safeguards | Explicit deadline/input races, schema validation, immutable sender/owner routing and closed-answer/A2UI denial Also cover A2UI idle/busy/resolve-question routing, uncorrelated409, composer Question answers with attachments, plan-exit approval/revision and deferred-hook permission resumes. | blocked — fresh replacement evidence pending |
| M06 | Migrate pending legacy human steers without inventing input acknowledgements | 5475042f composer_runtime.recover_pending_feedback; message_intents.json | Data-only startup migration | Stable identities, pending feedback retained, twice-idempotent migration and no replay Strip branch-only transfer task_handle/owner_session_id/invocation_id during data migration, before strict storage decoding. | blocked — fresh replacement evidence pending |
| M07 | Preserve future-composer edit/order/revision/promotion/pause behavior over Core | 5475042f MessageIntentStore queued-message methods and existing composer UI tests | Single Core mailbox and TurnRunner | Public queue operations, stale revision refusal, explicit promotion and independent pause retained; deleting undelivered input withdraws it, committed input cannot be silently withdrawn; no JSON pending-steer authority Retain idempotent POST replay, one revision-race promotion retry, typed terminal-head failure without spin, pending-Question promotion gates. Old default100 future-message and lifetime idempotency caps are removed; the reviewed Core limit applies only to undelivered peer messages, human input is exempt. | blocked — fresh replacement evidence pending |
| N17 | Preserve native queue identity and all URL/QUEUE/CONCURRENCY environment overrides | 5475042f NativeTaskHost.__init__; CLIO_TASKS_{SHELL,STORAGE}_{URL,QUEUE,CONCURRENCY} | Independent native roots | Memory defaults clio-<root>-<incarnation>; persistent defaults stable clio-<root>; explicit configured queue unchanged | blocked — fresh replacement evidence pending |

Not frozen. No replacement acceptance has run. No release is authorized until every required row passes and both independent implementation/removal reviews are resolved. Freeze includes core, actual GACT gitlink, dependencies, schema and runtime. Record impact and repeat affected gates after any later change.

## Owned qualification state

No replacement live acceptance has run. Two focused guard-test invocations failed in global setup before their test bodies: the first private Core could not bind its long Windows path; the short-root retry started Core, then encountered the deliberately removed workflow binding. Their fixture roots are absent and their processes have ended. These are setup failures, not acceptance passes. See task-replacement-cleanup-receipts.json. Prior prohibited/manual-only roots remain excluded; the c1 review cache is now also manual-only after automatic-review rejection.

## Replacement construction — first Core slice

Removal approved independently at4804dd6f. The initial replacement defines the shared TaskSnapshot/owner/backend/content/input/mail/grant records, a GACT writer using the confirmed ARC/Core lanes, passive latest/pending indexes and Question commands. Content precedes references; a recipient-input context record is the acknowledgement. A prewritten input locator alone acknowledges nothing. Canonical replay repairs passive indexes; failed writes hold new durable admission until reconciliation. No workload scheduler, task driver, automatic turn admission or duplicate Question store is installed.

Fresh production-Core test cases cover index-write failure, crashes before/after recipient input commitment, pending-only peer limits and exemptions, independent recipient collection, withdrawal, missing legacy description, more than1000 retained messages and Question answer/cancel arbitration. They remain UNEXECUTED while the deliberate-break product imports are unresolved. The existing conftest is not bypassed. Scoped Ruff/format/Pyright pass for these new modules/tests; this is not runtime or model acceptance. Q1–Q9 and R1–R6 remain blocked.

This was the initial construction status. The review-correction checks below supersede its unexecuted-test statement for the covered components; the integrated application remains unfinished.

Application installation, native SDK/roots/workloads, shared authorized controls, conversation assignments/admission, migration, UI/prompts, final frozen CI/live qualification and publication remain outstanding. No replacement model/native qualification process has launched. Review processes exited; c1/c2/c3 cache removal commands were automatically rejected, and their exact roots remain manual-only.

## Replacement construction — SDK and native-root slice

The follow-up Variant Question check serializes parent-admission validation with the confirmed Question write. Both ordinary draft and module-variant choices passed through the production Core owner, including refusal after the parent cancellation intent. These are focused construction checks, not model acceptance. Their pytest processes exited and private runtime roots were absent afterward; nanobind exit diagnostics remain recorded in task-replacement-variant-final-checks.json.

The SDK adapter now binds a confirmed submission context before tools/call, intercepts native acceptance into a local typed receipt, shields adoption across caller cancellation and retains unfinished adoptions in its application-owned client. Other results use the SDK parser. ToolTask.result owns task driving; the adapter adds no polling loop. A supported transport-options wrapper observes existing SDK replies and guards input updates. Captured version/schema validation precedes successful terminal publication. Independent Shell/storage native roots retain URL/queue/concurrency configuration and default10-worker capacity; no application lifespan or workload is installed yet.

On2026-10-13 the human identified [stable FastMCP4.1.0](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.1.0). The inherited beta choice had no established technical requirement. The source dependency tuple is now FastMCP/fastmcp-tasks4.1.0, MCP2.0.0 and Docket0.26.2. PyPI metadata requires Docket>=0.26 for Tasks4.1; the lock resolves the required upgrade and Python3.15-only beartype marker without changing unrelated Python3.14 dependency versions. Read-only wheel inspection found ToolTask's driver and TransportOptions unchanged; acceptance/parse hooks and native extension differences were inspected. The plan records the change for independent review.

Scoped Ruff/format/Pyright and the removal guard pass. These checks used the existing beta environment with --no-sync, so they do not establish stable-runtime compatibility. Fresh adapter contract cases are written but UNEXECUTED while deliberate-break product imports remain unresolved. Stable runtime installation, contract execution, integrated service/model evidence and all Q/R acceptance rows remain outstanding. No replacement qualification process, port or data root has been created by this slice.

## Requested three-hour checkpoint

Production edits paused at a7f2c86f, GACT unchanged32044a38. Both independent reviews finished: task-replacement-checkpoint-review-astra-4.md and task-replacement-checkpoint-review-claude-4.json. They support the separation of passive Core records, native execution and Question commands, while identifying source defects. These reviews are not approval of the current foundations or runtime acceptance.

Before more construction, correct withdrawn/already-acknowledged input admission, recover input commitments independently of passive indexes, preserve accepted identity through client shutdown cancellation and recording failure, and enforce Question answer shape. Claude also identified event-lane content pollution, input identity scoping, grant revocation monotonicity, submission digest verification, transport delegation and output-schema dialect handling. Evaluate its versioning/index/transition recommendations against the explicit ban on another generic lifecycle owner; do not add a new coordinator or silently skip undecodable authorization/delivery history. Review the remaining bounded-read/cursor/lineage/publication concerns when building the already-planned controls and migration.

Propagate the stable dependency tuple through feature installer/release source and required checks before Z03 freeze. Preserve historical released-version documentation and installed state. Cover4.1 authentication ownership and HTTP idle expiry explicitly. The checkpoint automation is PAUSED after both requests. Claude exited0, its process is absent and original authentication is unchanged. Its owned c4 cache has7files/715928logical bytes/no links; guarded cleanup was automatically rejected before execution and its exact root is now manual-only. No removal retry, absence claim or qualification launch occurred.

## Review corrections and fresh component checks

Resumed on the human's instruction. Core content now uses its own non-event kind/scope. Input commitment checks withdrawal, prior recipient acknowledgement and one input per assignment/iteration under the existing writer lock; IDs are session-scoped. Canonical preparation events make context commitments discoverable after complete passive-index deletion. Confirmed writer failures include post-persistence highway failures. Original task identity/backend binding and historical terminal outcomes cannot be replaced. Grant revocation requires a new grant ID to regrant. Supported record versions are explicit; unknown records fail closed rather than silently losing acknowledgements or revocations.

The SDK adapter checks the actual argument digest before dispatch, shields adoption during shutdown and retains accepted identities after recording failure. Retrying adoption repeats recording only, never tools/call. Transport identity/auth/close delegate; multi-server proxies are refused before connection in favor of per-server native clients. Raw output uses its declared supported JSON Schema dialect, without promoting format annotations to assertions.

Further removal found and deleted the surviving registry-based workflow runner and two obsolete imports hidden behind aliases. The denylist now catches aliased retired symbols and the old pending-ask writer. Blueprint parsing remains independent. ARC model helpers import the model implementation only when used; all normal pytest Core/network/hygiene fixtures remain enabled. Variant choices now use QuestionCommands and exact common handles; the old pending-ask/turn-start-notice/supersession policy is removed. Ordinary draft-tool Questions no longer force a turn ending or root-history replacement; module variants retain their domain selection continuation. This source integration is not yet live-model acceptance.

FastMCP/fastmcp-tasks4.1.0 and Docket0.26.2 are installed in the owned feature environment; MCP2.0.0 is retained. Source installer/release roots and GACT2924500f match the stable SDK tuple and DSPy3.4.0. Historical released-version examples and the synthetic parser fixture intentionally retain their original beta strings. No installed Desktop/auth/default/released branch changed.

Sequential exact-node checks passed with one worker and no skips: the foundation/adapter/guard families, seven source-install/bundle checks and variant Question-owner cases. Bounded receipts are task-replacement-foundation-checks.json, task-replacement-installer-checks.json, task-replacement-adapter-final-checks.json, task-replacement-variant-question-checks.json and task-replacement-variant-final-checks.json. The first dependency case failed before its body on the surviving workflow import; after removing that path, the normal retry passed. Every controller reports no private runtime-directory residue before the next case. Real-Core cases emitted nanobind retained-instance/type/function diagnostics at interpreter exit; these are recorded and not claimed solved. No product services or model acceptance ran.

The integrated candidate is not frozen, globally built, pushed or qualified. Application-owned native resources/observers/trusted workers, shared authorized controls, assignment/admission integration, migration, UI/prompts, CI and the fresh live matrix remain outstanding. Full-history startup replay is permitted and must be measured before optimization; retain passive latest indexes for the forthcoming hot read layer. Do not add a quarantine framework or universal execution state machine to address review suggestions.


## Shipped compatibility correction after initial source review

The finite mapping is in `docs/runtime/task-compatibility.md`, with independent
source decisions in the `task-replacement-*-astra.md` compatibility receipts.
This is one correction slice; it introduces no execution owner or driver.

| ID | Required behavior / retained lesson | Fresh source and test | Prerequisites / evidence / expected result | Status |
| --- | --- | --- | --- | --- |
| C01 | Shipped spawn names, blueprint/strategy preparation, local placement and per-member failures | `task_declarations`; `test_spawn_tool_compatibility` | Real Core; same preparation path; explicit relay refusal; no child for invalid evidence | Unexecuted |
| C02 | Finished child evidence is pinned and authorized before creation and input commit | `assignment_evidence`, `session_mail`; `test_assignment_evidence_contracts` | Real Core; original assignment committed intact; before-commit/forged evidence cannot be read | Unexecuted |
| C03 | Shared result pages stay on exact committed content through successor recovery and grants changing | `task_result_content`, passive recipient-input index; `test_assignment_evidence_contracts` | Reconstruct exact JSON; cross-session denial; no source completion publication/acknowledgement | Unexecuted |
| C04 | Observe retains omitted task rows and every output byte without another producer event | `task_observations`, `task_output_pages`; `test_task_observation_compatibility` | Bounded pages, late output while draining; cursor cannot disclose another task namespace | Unexecuted |
| C05 | Honest SSE cursor migration, actual workflow state and output-only pattern search | Shared observation plus compatibility delegate; `test_task_observation_compatibility` | Numeric resume refused; string continuation works; match beyond first page; metadata is not output | Unexecuted |
| C06 | Shipped getter/wait/message delegates preserve authorization and collection receipts | `task_declarations`; `test_task_output_compatibility` | Real Core; terminal/pending/unknown/read denial and input commitment | Unexecuted |

Scoped source Ruff/format and Linux Mypy passed before behavioral execution.
Removal, size and class guards passed; noqa-hidden swallow count remained 493.
These are construction checks, not live/model acceptance. Earlier failed fixture
runs remain in their individual receipts; they are not erased by this correction.


## Retained-behavior correction packet R19

Astra R17 and actual Claude R18 found production gaps after the compatibility source review. The finite C1-C8 owner/removal map and reviewed decisions are in `docs/design/task-replacement-corrections-r19.md`. The initial source packet is implemented for same-session context recovery, closed-plan Question repair, stale visual answers, assignment-bound pause/resume, workflow checkpoints and deliberate retry, declared execution deadlines, and nonfinal uncertain-result inspection with passive cancellation rechecks.

C1-C8 behavioral gates are **unexecuted**. Legacy coupled-test migration, exact-head CI, Q1-Q9 and R1-R6 remain outstanding. No earlier executor/model evidence qualifies this replacement. Human continuation through unsettled cancellation is an optional R2 amendment awaiting a direct human choice; strict settlement remains in force meanwhile. Review source copies R17/R18 and R19 were removed after their processes settled; bounded reports remain, with no archive.


## R21 source-review correction packet

Both R20 source reviews returned NO-GO. The complete finite correction map is `docs/design/task-replacement-corrections-r21.md`; source checks are in its matching static receipt. New context, pause/deadline, workflow identity/handoff, passive cancellation, late settlement and approval-repair regression cases retain the original behavior obligations. They are unexecuted. No test deletion, passing static check or source review waives Q1-Q9, R1-R6, migration, CI or live/model acceptance.


## R23 initial source corrections

Both independent R22 source reviews returned NO-GO; reports and the approved correction seams are retained. `docs/design/task-replacement-corrections-r23.md` records the combined finite packet: exact failed cancellation delivery, per-step orphan closure, legacy workflow identity and recovery isolation, closed-transport retry retirement, external attention deduplication, immutable Question decisions and conversation epochs. The matching static receipt has source hashes and successful scoped checks. Fresh regression construction is unexecuted; prior local tests, CI and model runs do not qualify this packet. Required Q1–Q9/R1–R6 and migration gates remain outstanding. No merge, release or installed-state change occurred.

## R26 independent Fable review and boundary corrections

Actual Claude Code `claude-fable-5-1` independently inspected frozen core
`14cd98be` and GACT `ce993164`, using a neutral two-paragraph brief. Its verdict
was NO-GO. The report identifies real UI, health, query and thread-retirement
defects; its claim that the ledger was absent resulted from review packaging,
not missing committed source. The next package includes this ledger. Astra's
read-only adjudication confirms the consequential defects and rejects another
architectural replacement. Neither review approves the current corrections.

The finite source/removal map is
`docs/design/task-replacement-corrections-r26.md`. The existing Core writer now
exposes named history operations, validates owner vocabularies and rejects
private-map access in production callers. Narrow queries use existing indexes
and target lineage. Health checks have a transport-only bound. Root-context,
migration, startup-recovery and historical-placement corrections retain honest
uncertainty. GACT uses one operational-state decoder and restored read aliases.

Scoped static evidence is recorded in the R26 receipts. Constructed migration,
route, thread-retirement and retained-behavior cases remain **unexecuted**.
F03 measurements, accepted independent source reviews, required CI and the
entire fresh Q1–Q9/R1–R6 matrix remain outstanding. The feature candidate is
not release-qualified. No product qualification service or model was launched
during this correction packet; the completed review source and processes were
removed, with bounded receipts retained.

## R27: independent verdicts and finite input/control corrections

Fable R26 ran as actual `claude-fable-5-1` over core `8f40aa8d` / GACT
`557aecd3`, with the acceptance ledger included. It supports the architecture
in principle and judges the replacement genuinely simpler, but returned NO-GO
for source defects. Astra independently returned NO-GO and adjudicated Fable's
findings. Its any-wait recommendation would change the shipped contract and is
not adopted. The correction maps omitted from Fable's package are committed;
the next package includes them without prior reviewer reports.

The combined finite map is `docs/design/task-replacement-corrections-r27.md`.
Initial source corrections and bulk regression construction are complete for
collection revocation, RPC-only cancellation limits, REST pagination,
defer-on-validation and resolved cancellation attention. Scoped static checks
pass for fourteen changed source files. R27 behavioral cases are unexecuted
and neither reviewer has approved these changes yet.

The R26 boundary family executed eleven selected cases individually and
sequentially with one worker. All passed after moving a test assertion's Core
read off-loop; the original failure remains recorded. Receipts are
`task-replacement-r26-boundary-checks.json` and
`task-replacement-r26-boundary-retry-checks.json`. Both disposable parents are
absent. The read-work case retained 1,004 tasks and measured 6.631 s startup
replay, two exact snapshot reads and nine active snapshot reads. This does not
qualify unrelated-session growth or the complete F03 gate.

Static import inventory still identifies thirty-nine legacy test modules with
retired imports; it includes unrelated historical imports and is not permission
to delete their retained behavior. Required test migration, CI, Q1–Q9 and
R1–R6 remain outstanding. No model/product qualification service, release or
installed-state change occurred in this packet. Fable exited successfully;
its source, process group and bounded remote receipt are absent after retrieval.

## R28: one disclosure check for immediate and delayed input

Astra R27 found two remaining shared-input defects on `5eab9ef8`: delayed mixed
collection could omit permission rechecks for an unsubscribed peer, and a human
trigger could be mistaken for a task-result notice. Read authorization now lives
in `SessionMail.commit`, using the persisted observation's read handles and
notification IDs. The separate immediate-recorder check is removed. Four real
Core recovery cases cover granted/revoked peers, with and without queued human
feedback; immediate subscribed-peer cases also remain passing.

The actual native SDK check exposed `ping` returning Method not found under the
pinned runtime. Health probing now uses supported tool discovery, retaining the
RPC-only bound. The first failed SDK case is retained in the R27 receipt. Ten
affected R28 cases subsequently passed individually/sequentially with one worker,
including actual native work remaining active across a cancelled RPC and settling
after deliberate release. The disposable parent is absent. Source lint/format,
generated-reference/removal/size checks and Mypy pass; the initial type-check
failure and its correction remain in separate receipts.

Fable R27 independently supports the architecture but identifies pre-input
re-admission after hook denial/setup failure. Astra confirms the narrower defect,
including hook-defer release ordering. Its bounded existing-owner correction is
under review and not implemented in this packet. Source approval, legacy test
migration, CI, Q1–Q9 and R1–R6 remain outstanding. These component checks are not
model acceptance or a release-qualified candidate.

## R30: hold exact failed inputs and reuse the Question owner for hook approvals

Astra's R29/R30 bounded source reviews endorse holding the exact uncommitted
trigger and replacing turn-defer permission state with QuestionCommands. The
old turn-defer transition/resume helpers and text reconstruction are removed;
the removal guard denies their return. Permission cards/routes delegate to
Question decisions. PreToolUse enforcement remains its existing owner.

The replacement captures immutable input/assignment/epoch correlation, freezes
human decisions before effects, preserves typed input/media without rewriting
its body, and retains control-only outcome mail without an automatic owner wake.
An authenticated retry supersedes only the server-bound held input. Veto/setup
failure and Stop cannot overwrite a revised/approved input. Approval rechecks
control and input identity at acceptance; deferred completion rechecks its
captured epoch after retirement. Legacy unbound approvals remain unresolved.

The first fifteen component cases passed individually/sequentially, one worker,
with no skipped case. Evidence is `task-replacement-r30-behavior-checks.json`;
its disposable Core parent is absent. The final audit added explicit atomic
approval and retirement checks. Fresh affected cases on that final correction
are constructed but unexecuted. Earlier fifteen-case evidence is not final-head
acceptance of the later correction.

Initial size/type-check failures and their corrections remain in the R30 static
receipts. No guard, assertion, timeout or resource budget was weakened. Final
source checks and independent implementation reviews remain required. Legacy
test migration, CI, F03, Q1–Q9 and R1–R6 remain outstanding; no live-model/product
qualification service, release or installed-state change occurred in this packet.

## R32 construction: retirement, input recovery and common Runs

Independent R31 source reviews remain NO-GO until the new candidate is reviewed.
Corrections and a complete focused regression batch are constructed in the existing
owners; the replacement map is `docs/design/task-replacement-r32-corrections.md`.
No new execution registry, scheduler or delivery acknowledgement was introduced.
Core input ownership now survives Stop/retirement for exact cancellation and
trusted retry. Question media recovery and frozen completion gate repair use the
existing recipient-input and Question boundaries. Runs lists shared task snapshots,
including cross-session pagination and supported controls; removed relay APIs are
not restored.

Test state and native Core deployment are restricted to the owned D: repository.
The early launcher contains dependency-import writes and inherited Core settings;
cleanup requires verified process identity and retirement. No pytest, model,
native Core or browser qualification ran during this construction packet.
Source formatting/lint, Linux-target Mypy and the six frontend guards pass.
TypeScript, focused execution, refreshed reviews, CI, F03 and Q1–Q9/R1–R6 remain
pending. Constructed tests and earlier component evidence are not final acceptance.
