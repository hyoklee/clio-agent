# Initial implementation review actions

## Shipped output-getter compatibility

During individual test classification, Astra verified that
`get_agent_task_output` shipped in v0.9.2 and remained in v0.9.5-beta.5.2.
R2 therefore requires its one-cycle delegate, rather than deletion as an
unfinished branch internal. The correction uses the existing compatibility
builder, common authorized result operation and `_collected` recipient identities.
New default catalogs and newly emitted digest retrieval instructions use
`get_task_result(handle)`. Existing bounds/references replace the old unlimited
inline promise. No registry, task owner or extra acknowledgement path returns.

Pure digest assertions remain; old getter/registry scenarios are replaced by
real-Core alias/result/authorization/pending/collection tests. Their current
status is authored and unexecuted. This small production delta still needs source
review and affected checks; af8e4b6c approval does not automatically cover it.

Focused proof so far: original-reservation Stop/retirement and automatic-promotion
Stop regressions passed individually. The evidence case first refused an unpinned
fixture reference; it is being corrected to select/pin an actual snapshot.
Original failed attempts remain recorded. Runtime roots b1-b4 were absent afterward
and process audits found no matching residue. Core2.3.1 emitted nanobind reference
count diagnostics, including after a passing case; long-lived resource-growth
acceptance remains unverified. These focused results do not pass Q3/Q7/Q8 or any
final five-cycle race gate.

## Initial source approval

Astra independently approved core af8e4b6c / GACT ce993164 / marketplace 9257bba
for initial production-source qualification. The complete source-only verdict is
retained in task-replacement-initial-review-astra-13.md. No source edits, tests,
imports or services were performed by that review. Claude's renewed verdict is
still blocked by host authentication. Test migration and fresh qualification
continue; CI and Q1-Q9/R1-R6 are not passed by this source approval.

## Review 12 correction candidate

Astra's frozen f029d12b review returned three actionable source findings. This
candidate corrects them in the existing conversation owner, mailbox and renderer:

- Stop reaches an assignment-less admission reservation before asynchronous
  preflight completes. Automatic promotion rechecks suspension before publication
  and again through normal eligibility. Stop retirement is pinned to its original
  reservation; a later task-result wake is not silently cancelled.
- Busy typed-input rendering uses the existing admitted-snapshot resolver. Stale
  evidence is labelled as-of acceptance while unavailable/private evidence is
  still refused.
- Final rendered text and media count toward the notification batch budget.
  Excess accepted items remain Core-pending. One oversized indivisible human input
  is admitted alone, including the initial head. Explicit collections already
  represented by tool observations remain separate. No base64 clipping or partial
  message acknowledgement; existing whole-request media/context limits still apply.

Astra separately approved this batching policy in a focused read-only decision;
that is not implementation acceptance. Four regressions were authored and remain
unexecuted. Static production checks, independent implementation review, fresh
behavior tests, exact-head CI and Q1-Q9/R1-R6 live acceptance remain distinct gates.

## Review 12 authentication prerequisite

Frozen core f029d12b is under renewed Astra source review. Actual Claude Code returned an OAuth-expired refresh failure before any model inference; no source verdict was produced. The normal host CLI also reports loggedIn=false/authMethod=none. Original credential hash remained217e114a during this attempt. A human login refresh was requested asynchronously; implementation and test construction continue independently. Do not patch task code for this provider prerequisite. Stop cloning refreshable OAuth credentials for future reviews: use the existing host login after it is repaired, no-session-persistence, read-only tools and bounded in-repository receipts, without another credential copy or temporary review cache. Attribution of the earlier host login change is unproven. Both failed-review owned processes ended; automatic removal was rejected before execution, and exact c12 root is manual-only.

## Review 11: corrected source remains NO-GO

Frozen core 057b93bd / GACT ce993164 / marketplace 9257bba was independently reviewed by Astra and actual Claude Code. Both accepted the review-10 source corrections and the removal direction, but found remaining integration defects. Their complete bounded receipts are retained. Neither executed runtime acceptance. Claude exited0 with no remaining owned children; original authentication changed during the review and cannot be claimed unchanged. The isolated copy differs from the current original; other Claude processes are active. No credential restoration is performed.

Required correction set, within existing owners:

1. Restore the trusted MCP App model-context carrier; reserve server-owned metadata from public clients.
2. Preserve canonical typed human/composer messages in Core and render attachments and reference content before recipient-input commitment for initial, busy and recovered arrivals. Do not consume a JSON summary instead of actual media. Keep expensive hydration/hash work outside the global writer lock; recheck the staged immutable item at commit.
3. Withdraw pending inputs on explicit message deletion and undo/rewind. Do not treat arbitrary projection replacement as deletion.
4. Canonicalize authorized goal dependency aliases before self-check, deduplication and persistence.
5. Preserve SDK transport options and compose the known cooperative CLIO capability session with observed task replies; reject incompatible classes before submission.
6. Restore terminal Question events understood by the shipped Go TUI, and preserve the legacy to-do GET route by giving the new common query a distinct route.
7. Move queued reference preflight outside the Core lock, retaining revision and authorization rechecks at publication. Map Question cancellation conflicts through the usual HTTP error contract.

The principal review-11 corrections were committed in f029d12b and Astra's review-12 source trace confirmed them. This is not runtime acceptance. The central input correction is one canonical Core payload and existing model-input renderer, not another inbox, execution owner or history store. Required tests include busy/multiple queued media, MCP App context, Core-only recovery, withdrawal before commit, alias self-dependency, capability advertisement and preflight concurrency. Initial implementation is not accepted, and no fresh product tests/models have launched.


## Correction candidate after review 10

These are source corrections awaiting independent acceptance and fresh behavior evidence:

| Finding | Existing owner correction | Required evidence |
| --- | --- | --- |
| Shutdown admission and in-flight reservation | Close TurnRunner admission before the first shutdown await; serialize physical thread start and retirement | Shutdown/arrival and Stop/retirement races |
| Revocation does not wake indefinite waits | Core grant observations signal recipient listeners; shared controls recheck rights | Revoke while waiting and before injection |
| Visual Question contract/correlation | Restore surface/action fields, canonical aliases and UI question correlation through QuestionCommands | Actual visual answer/cancel and legacy alias behavior |
| A2UI consumes before input commitment | Project delivery acknowledgement from the confirmed recipient-input record, including recovery repair | Paused answer and input-commit crash recovery |
| Missing production callers and old elicitation owners | Rebuild spotter, references, producer/finalization and one tool-less MCP answer helper through Conversations/Core | Normal turns, helper/human races and caller gates |
| Task updates/status mismatch in UI | Core-committed task event invalidates session state; preserve Stopping/uncertainty and physical cancellation states | Real service desktop/phone controls |
| Broad source validation gaps | Full production Ruff/format, lowered guard baselines, coherent resource planning and actual default native Client | Fresh tests and SDK upgrade contracts |

The helper's fixed Question association and the catalog retirement follow the focused Astra decisions. Neither focused decision accepts the entire implementation. No behavioral gate is marked passed from these changes.


## Focused catalog adjudication after review 10

Astra's read-only turn `01a13b2c-afe4-7cb0-83ff-67be6ed3ab22` confirmed retirement
of the legacy `cluster-operator/AGENT.md` as the narrower R2 correction. Discovery
requires that filename; a README warning or unsupported `enabled: false` field
would not disable the old executable grants. The manifest is deleted with Git
recovery, without an archive or a replacement relay implementation. Workload
skills remain explicitly historical reference. The shipped-pack inventory follows
the actual retirement. This changes discovery after normal refresh at the new
marketplace revision; it neither uninstalls existing snapshots nor converts their
configuration. It creates no relay qualification gate. This focused decision is
not acceptance of the complete implementation.

## Review of 9b0a91ec / f1b099cd

Astra and actual Claude independently returned no-go. The next correction candidate uses the existing owners rather than adding another task layer. Source corrections are present; the new regression batch remains unexecuted and these rows are not acceptance passes.

| Finding | Correction | Fresh evidence still required |
| --- | --- | --- |
| Downloads reject their own queued operation | Validate before reserving a new transfer; verified native redelivery reuses its operation | Actual native Download and bytes/hash checks |
| Choice selection/dismissal acknowledges unrelated feedback | Run the conversation program on ordinary feedback after resolving the choice | Choice plus feedback and reverse-order choices |
| Native/provider cancellation has one RPC attempt | Retain owner-local cancellation delivery retry in existing Core recovery | Failed RPC, original-identity retry, actual cleanup |
| Provider reservation/reattachment failure loses recovery | Keep exact pre-dispatch context/reservation and original provider identity pending; no uncertain call replay | Core outage and surviving job reconnect |
| Restart's own-session wait is refused | Trusted owner settlement wait does not impersonate a model waiting on itself | Restart after cancellation, no successor before settlement |
| A previous native leg cannot publish its cleanup receipt | Existing incarnation can confirm its own receipt independently of the newer leg; unknown previous attempts remain unknown | Attempt/incarnation fault cases and continuation |
| Historical tasks block cancellation, or live tasks disappear during Stop | Persist cancellation membership at closed admission; exclude only earlier outcomes | Terminal reply during worker retirement and recovery |
| Held result collection fails after observation persistence | Exact explicit collection commits its authorized durable observation through the recipient-input boundary | Held result collection/automatic delivery race |
| Cleanup continuation and body use different admission rules | Native workers use the conversation owner's ancestor/session cancellation predicate | Cancellation admission race and cleanup-only continuation |
| Legacy migration drops/over-acknowledges records | Fold current wire fields, retain unmappable rows in Core, finish interrupted withdrawals, require actual input proof | Migration twice, orphan/claimed/cancelled data |
| Released spawn strategy lost | Validate before child creation; retain immutable normalized strategy; delete broken old adapter | Invalid strategy, replay refusal, LM/user builder cases |
| Private native identity and reconnect construction leak across owners | Move SDK identity and ToolTask reconstruction to the pinned client adapter | Actual pinned SDK contracts |
| Linux epoch birth comparison can drift | Use boot identity plus monotonic process start; legacy proof remains uncertain | Clock shift/PID reuse cases and platform qualification |

The focused Astra follow-up confirmed that `external_acknowledged` must not count as physical settlement. It also established spawn strategy in released tags from `v0.9.5-beta.1` through `v0.9.5-beta.5.2`; preserve that public behavior without restoring the removed spawn engine.

## Earlier review of 8fbd4130

Reviewed source: core `8fbd41308bc5b961049fe441781d48b368aebb8e`, GACT `3efef4afffb235bb2ee1873358591478ce63895c`, marketplace `3299065f3ee7f827f734d311d39b15bf7460ab42`. Both Astra and actual Claude completed independent read-only source reviews and returned no-go. Corrective source construction is in progress; it has not been checked or qualified. No acceptance row is passed by these reviews.

| Finding | Existing owner and correction boundary | Required fresh evidence |
| --- | --- | --- |
| A1: admission/start write fails without scheduling recovery | Conversation owner and existing application recovery callback; retain Core-pending input and recheck admission after confirmed recovery | Core fault before busy write and before input commitment; pending input later admitted once |
| A2: module variants bypass shared input commitment | Existing parent model-input boundary; commit the parent's fixed input before branching, retain distinct branch contexts, and commit later Question continuations without consuming unresolved choices | Two outstanding choices answered in reverse order; ordinary feedback, explicit refinement and no repeated admission while a choice remains open |
| A3: native observation exits after lost visibility | Existing native SDK observer and Core recovery registration; reconnect the original identity/captured schema, without a second polling loop or submission replay | Actual visibility loss, later SDK outcome, one attention episode followed by final delivery and orderly shutdown |
| A4: uncertain descendant leaves parent cancellation unfinished | Existing conversation cancellation operation; retain its reconciliation until required owner cleanup actually settles | Uncertain descendant recovers and confirms cleanup; parent then settles; no new descendants escape |
| A5: legacy withdrawals and subscription changes are not folded | Data-only startup migration; apply latest legacy mail/relationship state and preserve attribution before indexing | Migration twice; withdrawn work never wakes; disabled subscriptions stay disabled; stable identities and proven input acknowledgements |
| A6: surviving provider job has no reattachment path | Native storage workload/provider algorithms and original persisted provider identity; resolve the concrete recovery path before coding. Do not add a transfer scheduler or another execution owner | Actual provider job survives local interruption, reconnects by its original ID without resubmission, and verifies real bytes/manifests/outcome |
| A7: restart looks up the wrong cancellation-job key | Existing conversation control resource map; use one cancellation identity | Restart awaits known cancellation/worker retirement, or honestly reports uncertainty without launching |
| A8: subscription injection ignores revoked observe right | Existing shared mailbox authorization and recipient-input commitment; recheck read plus observe | Revoke observe after publication while retaining read; no output injection/acknowledgement; owner delivery remains independent |
| Construction audit: new declaration module reused a denylisted old module path | Move the new tool declarations to a responsibility-specific module; retain the guard against the removed old authority and keep explicit compatibility delegates separate | Existing removal guard plus catalog tests; no old task owner, import or default agent-only control returns |

The corrective source now includes the missing provider stream code, reference-form descriptions, writer-driven recovery, immutable SDK reconnect, retained cancellation reconciliation, shared restart waits, delivery-right rechecks, folded legacy mail/subscriptions and message intents, legacy input acknowledgement mapping, and parent input commitment before draft branching. It also includes task-level Stopping, honest recovery UI states, failed-spawn cleanup, explicit rejection classification, reconnect cancellation retry, all-root shutdown attempts, narrower dependency gating, recoverable Question posting and removal of obsolete workflow timeout configuration. These changes have not been checked or live-qualified.

Provider recovery uses a narrowly scoped host-only native continuation after verified local process loss. Its worker cannot submit cloud work. Original job/source/path custody and local publication phase are checked, ambiguous publication or multiple former execution attempts require inspection, and each former incarnation needs its own cleanup proof. The provider clarification and Astra's source decision are retained; independent Claude review of this correction is still required.

Commit the corrected source and resend it to both reviewers. Build fresh public-behavior coverage as a batch and run it sequentially with one worker. CI and the finite live matrix remain required after source review; no release is authorized by an improved source verdict. Startup replay/migration cost remains a measured acceptance gate; do not introduce a checkpoint framework before measuring it.

The c6 review produced no result before its diagnostic timer stopped it; its underlying failure cause is unproven. The c7 retry completed successfully with a no-go source verdict. All owned review processes have exited and authentication hashes matched. Removal of exact `D:/Temp/clio-task-implementation-review-8fbd4130-c6` and `D:/Temp/clio-task-implementation-review-8fbd4130-c7` was automatically rejected before execution. Both roots are human-manual-only. Never retry, bypass, move or reuse them.

Claude additionally found invalid description-reference validation; missing provider stream/lock code; failed-spawn cleanup; incomplete Core-writer recovery; blocking Core reads; absent task-level Stopping; uncertain-versus-rejected submission classification; cancellation retry and shutdown gaps; overbroad goal dependency gating; orphan external-input Questions; obsolete workflow timeout settings; and SDK private configuration outside the adapter. These belong to the existing writer, conversation owner, workload, SDK adapter and input boundary. Source changes alone do not close their evidence requirements.


## Compatibility review of ad560ef2

Astra returned NO-GO with one P1 and seven P2 findings; the complete read-only
verdict is task-replacement-compatibility-astra-14.md. The correction keeps the
same owners: initial assignment details include pins before the first snapshot;
observation cursors prioritize omitted members; matching uses the already-read
integrity-checked logical chunk and returns bounded attributed match excerpts;
all timeout paths retain recovery metadata; public batch schema accepts a
blueprint without agent; the shipped spawned array retains independent failures;
transcript events use committed rendered text; result fragments occur only once.
No execution state store, scheduler, poller or permanent fallback is introduced.

Before these source corrections,15 focused cases passed individually/sequentially
with no skips:2 busy snapshot/rendered-batch cases and13 compatibility cases.
The initial observation attempt failed on its fixture's description presence
marker; test-only7768ec40 corrected that. Receipts remain, including the failure.
D:/tr2-1014-b5 and b6 are absent and no matching owned processes remain. Core
nanobind retained-instance diagnostics remain unresolved resource evidence; no
live/model, CI or resource-growth acceptance is inferred from these passes.

The eight reviewer regressions and additional evidence-selection/inference-budget
migrations are authored as a batch but unexecuted. Actual Claude Code review
still requires repaired host login; no credentials were copied or overwritten.


Astra15 found one remaining P2: pattern excerpts and cursor/budget advancement
used different ranges. The correction charges the actual excerpt, advances
through the confirmed match, and stops that search page after the match. Prior
filtered bytes remain readable through search_start_cursor. Fresh continuation
coverage follows both READY and a truncated nine-character match with an older
chunk, checking no repeated match and the aggregate budget.

Eleven focused cases passed on000355ef before the newly migrated Core-folder
inference-budget case failed at fixture discovery (its body did not execute).
The second parameter was not run. The single real-Core ARC fixture now has an
explicit public fixture name and can be reused outside test_arc without duplicate
implementations. The failure receipt is retained; D:/tr2-1014-b7 is absent.

The remaining-test audit additionally found the released ask_user parser-residue
validator had been dropped with its old owner. Its algorithm is restored in the
sole QuestionCommands input-validation path, with actual FastMCP-boundary tests;
this is no global model recovery rule or alternate question owner.
