# Replacement construction checkpoint

## October 14 initial implementation candidate

The review-10 corrections are implemented in source. This is the next initial implementation candidate for independent review, not runtime acceptance or a release candidate. Astra and actual Claude have not reviewed this corrected tuple yet. Their earlier verdict on core 98a7a5ee was NO-GO.

The corrected source restores normal-turn, spotter, context-reference, MCP input-helper, producer and visual Question callers through the existing owners. It removes the old elicitation bridge/correlation/inline-answer authorities. Root and child assignments still use Conversations; native execution stays in FastMCP/Docket; Core remains the observation, mailbox and recipient-input authority. Cohesive owner algorithms were split into smaller modules without new stores, schedulers or lifecycle decisions. Legacy cluster-operator discovery was retired rather than converted into another relay implementation.

Source checks: full production-tree Ruff lint and formatting pass; scoped Mypy passes on 138 changed/new production files; application-module import passes without starting lifespan; all nine source guards pass; whitespace passes. The file-size and hidden-swallow baselines were lowered only. Native transport construction now passes observer arguments to its explicit top-level session class. Ordinary and queued human-message acceptance again plans resource deliveries using the retained resource algorithm, and document reviews use the same human-message acceptance path.

GACT source tuple: ce99316446848ddd269b1bf782ff2c87cc9db14a. Marketplace source tuple: 9257bba5953b012ba796299df4c633e698dbaddc. GACT scoped Oxlint, Prettier, six guards and TypeScript pass; no new build or rendered UI acceptance is claimed. Core records these feature pointers. The corrected production source is held fixed for the next independent reviews; test construction follows as a batch, with cases subsequently run individually/sequentially using one worker.

Fresh replacement runtime acceptance remains unverified. Q1-Q9, R1-R6, migration/recovery/capacity, actual models, external input/reconnect and real-service desktop/phone media still require the finite ledger's proofs. Earlier-engine runs and the failed/interrupted previous regression batches do not qualify this candidate. The full production-tree Mypy check is being recorded separately from the passing scoped check.

The persistent implementation/review goal remains active. Tasks are excluded from the separate human release. No merge, tag, release, installed update, authentication/default change or release-branch edit has occurred. Protected human design files retain their recorded hashes and remain unstaged.

Owned cleanup exceptions remain in task-replacement-cleanup-receipts.json. Rejected/manual-only paths are not reused or retried. No product qualification service/model/controller is running; static check processes are finite and tracked. Independent review processes will receive fresh owned, bounded state with explicit cleanup receipts.

## October 14 correction candidate

Both independent reviews of core `9b0a91ecc4b6ea2be014dca3fa7f9de32d4f3c70` / GACT `f1b099cdf479a4e2516391a525efeba17799cd65` returned **no-go**. Their receipts are `task-replacement-initial-review-astra-8.md` and `task-replacement-initial-review-claude-8.json`. Claude reviewed runtime and grant bindings, not the complete UI. Neither review qualifies runtime behavior.

The subsequent source correction pass addresses Download self-rejection; ordinary feedback during draft selection/dismissal; native/provider cancellation retry; provider reservation and reattachment retry; predecessor-attempt cleanup evidence; explicit collection of held results; common descendant admission; restart's internal settlement wait; legacy withdrawals, attribution and input proofs; stable Linux process-birth proof; and SDK worker/reconnect coupling. Cancellation captures its descendant membership before worker retirement and retains work that becomes terminal during that retirement. External acknowledgement alone remains insufficient cleanup evidence. The released spawn-time strategy is restored through the conversation owner, independently of trusted blueprint scope; its broken old wrapper is removed.

Fresh regression cases have been written as a batch for shared controls, migration, Questions, native ownership/cancellation recovery, conversation cancellation/strategy, process identity, stream queues and session-worker retirement. They have **not executed**. Scoped Ruff lint/format, Mypy on 14 changed production files, diff whitespace and the removal guard pass. Mypy initially reported 83 errors, then two, before the final zero-error result; these checks led to explicit SDK/JSON/null guards and typed callbacks rather than suppressions. Required CI, Q1–Q9, R1–R6, migration and uncertainty/final runtime gates remain blocked pending fresh evidence. This is initial source for renewed independent review, not accepted implementation or release readiness.

Session deletion still uses the cold Core replay path. In-process replay revisions now remain monotonic. Startup/deletion cost and bounded hot reads must be measured before deciding whether a smaller passive-index invalidation is required; no checkpoint framework has been added.

The completed c8 Claude review exited zero, both owned PIDs are absent, and original authentication hashes matched. Its 10-file/7,152-byte cache removal was rejected before execution. Exact `D:/Temp/clio-task-implementation-review-9b0a91ec-c8` is human-manual-only, alongside c1–c7. No absence is claimed and none may be retried or bypassed.

## Earlier construction checkpoint

The human instructed implementation to continue, then explicitly requested no further testing until the initial implementation is complete. Write new coverage as a batch afterward, run it sequentially with one worker, and then qualify with actual models and production service/UI. No checks ran during the earlier construction described below. Earlier focused passes cover earlier committed slices only.

Independent source reviews of core `8fbd41308bc5b961049fe441781d48b368aebb8e` both returned **no-go**. Calling that implementation ready was premature: required provider bridge lines were missing and described task snapshots failed validation. The initial source and review corrections are now in place for a fresh independent review. This is a construction checkpoint, not accepted implementation or runtime completion. No checks or live acceptance have run during this construction phase.

Initial review tuple: GACT `3efef4afffb235bb2ee1873358591478ce63895c`; marketplace `3299065f3ee7f827f734d311d39b15bf7460ab42`. Core records both feature pointers. Dependency/runtime evidence remains the previously recorded FastMCP/fastmcp-tasks 4.1.0, MCP 2.0.0, Docket 0.26.2 and Python 3.14 source environment; it is not a final acceptance freeze.

`wait_agent_tasks`, `observe_agent_tasks` and `cancel_agent_tasks` are explicit-request compatibility delegates. New default inventories expose the shared controls. Remove these aliases after one released compatibility cycle; retained historical trace decoding is separate.

## New construction, not yet validated

- Core submission references, attempt/incarnation cleanup receipts, hierarchy/grant/subscription indexes and full mailbox update records use the existing confirmed writer. No execution registry is installed.
- Independent native roots register Shell, Download and Indexing workers. Application-owned SDK clients retain result/input observation and original-identity recovery. The existing workload algorithms are retained. Physical cleanup and raw backend status remain separate.
- Shared task access/query/observe/wait/result/cancel code reads the common Core representation. Exact-handle subscriptions remain recipient-specific. Output chunks link to Core content; ordinary polling creates no model tool calls.
- One session mailbox stages input without acknowledging it. Recipient-input confirmation remains the acknowledgement, including explicit collection.
- TurnRunner reserves the session across model work, tools/waits and actual thread retirement. Producers persist and signal; it has no copied payload inbox or independent task lifecycle.
- Root/child assignments use the production conversation program, session-exclusive turn admission and model-call-only inference permits. Declared workflow steps, parallel children and skill-launched children use those same assignments and shared waits. Restart and recovery reference retained Core context instead of copying transcripts.
- Every product built-in crosses the application FastMCP boundary. Question posting is immediate; shared waits collect answers. Permission and external-input presentation retain their safeguards. Parent notices use the same Core mailbox.
- Composer, human feedback, peer messages, task outcomes, goals, schedules, hooks and approvals persist inputs and signal the same TurnRunner. Input commitment expands through the existing context reader/compactor. Stopped, paused, yielded and completed assignments remain distinct.
- Startup migration decodes legacy records without old owners or submission replay, retaining aliases, results, Questions, mail, grants, subscriptions and proven input acknowledgements.
- REST and GACT source wiring covers common controls, compact task rows, Questions, session grants/revocation, source-operation ownership and visible pending queue errors. These UI changes have not been built or rendered.
- Correction-review findings about pending draft choices and explicit asynchronous refinement now have source changes. Their continuation tests are deferred with the rest of the new coverage.
- Initial-review corrections cover native async provider streams, recoverable input commitment, legacy withdrawals/subscriptions/message intents and proven acknowledgements, owner cancellation/restart settlement, and SDK reconnection. A host-only native leg can reconnect a verified existing provider job after confirmed local process loss; it cannot submit provider work and refuses ambiguous publication or former overlapping attempts. Its narrow clarification still needs Claude's independent review and actual acceptance evidence.

Corrected source-review GACT pointer: `f1b099cdf479a4e2516391a525efeba17799cd65`. Marketplace remains `3299065f3ee7f827f734d311d39b15bf7460ab42`. The resulting core commit records these pointers. This remains a local review tuple, not a final acceptance freeze.

## Review and acceptance still required

1. Finish the source corrections recorded in the initial review actions, then send the corrected committed source to Astra and actual Claude for independent review. Both initial reviews are retained; neither accepts this implementation. No source review substitutes for runtime acceptance.
2. Build fresh public-behavior tests as a batch. Execute cases individually/sequentially with one worker, then scoped formatting, lint, types and existing guards. No prior-engine evidence qualifies this source.
3. Resolve review/check findings, integrate target changes and record the resulting dependency/schema/core/GACT/marketplace tuple before exact-head CI and the finite Q1–Q9/R1–R6 live matrix.
4. Qualify real models, external input/reconnect, failure/recovery, capacity, physical cancellation and desktop/phone UI. Repeat each required lifecycle race five times on the final candidate. Required unavailable/skipped cases remain blocked.
5. Replace predecessor website captures with selected real replacement-service media. Record go/no-go; no release until every required gate passes.

## Ownership and cleanup

No replacement qualification service/model/controller is running. The c5 actual Claude Code review exited0, original authentication hash was unchanged, and its cache contained7files/52527logicalbytes/0links. Its guarded removal was automatically rejected before execution. Exact C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/.clio-review-c5 is now manual-only; never retry/bypass deletion and do not claim absence. c1–c4 and all earlier prohibited/manual-only roots remain excluded. The rejection was notified once. Keep only bounded receipts and selected documentation media; do not recreate deleted recovery exports or create archives.

Protected human design files remain outside the implementing agent's changes. Installed Desktop, auth, defaults, released pins and unrelated work remain preserved.
