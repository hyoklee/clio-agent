# R33: bounded reads and recoverable disclosure

Reviewed production: core `a529569d` / GACT `458313c3`; core `504fc232` /
GACT `d0e03b5a` add test-only corrections. Both independent R32 reviewers
accepted the ownership direction and rejected source readiness. Astra's combined
adjudication and pagination conditions are retained in the qualification reports.

## Existing-owner changes and removals

| Finding | Existing owner correction | Removed behavior |
| --- | --- | --- |
| Revoked collection strands later human input. | A typed `TaskAccessDenied` leaves the protected observation uncommitted; the existing ContextReader placeholder permits independent input. | Catching legitimate revocation as a fatal input-recovery failure. Malformed content/Core errors stay strict. |
| Unsubscribe invalidates an authorized explicit read. | SessionMail excludes withdrawn notices from acknowledgement while retaining the independently authorized observation. | Treating notification withdrawal as result-read revocation. Owner delivery is independent. |
| Query/observe data can outlive disclosure rights. | The trusted local result wrapper carries read/observe requirements through the short FastMCP RPC into the existing recipient-input commit. | Unguarded query/observe tool observations. JSON fields cannot activate this metadata. Query/observe never collect answer media or acknowledge completion. |
| Lifetime query/count scans. | TaskHistory builds passive ordered session/tree/grant streams from latest Core observations. Query seeks immutable ordering, deduplicates streams and bounds examined candidates per page. | Full history joins/sorts and mandatory exact filtered counts. Sparse pages may be empty with a cursor. Unknown totals are null. |
| Segment finish scans historical tasks. | The existing passive active-tree index supplies current pending work. Fresh cancellation records active membership under serialization; recovery retains its original historical-time predicate. | Repeated finish-time history scans, without changing historical cancellation membership. |
| Content I/O holds the global writer lock. | Existing result/observation owners freeze immutable references, read outside the lock and recheck current disclosure rights before returning. | Serializing unrelated writers behind slow result reads. No result cache or additional worker owner. |
| Question retry compares mutable definitions. | QuestionCommands retains the immutable accepted request reference in the existing submission field. | Comparing annotations/resolution against the original creation request. Changed request content is still rejected. |
| Malformed durable input repeatedly retries. | Existing admission marks the exact revision held with `invalid_queued_input`. | Hint-only automatic retries of that input. Unrelated valid feedback remains eligible. |
| Known workflow failure looks like unavailable work. | The existing runner records failed-step identity and ordered accepted/not-launched references; GACT displays that evidence. | False missing-visibility labels for steps never launched, and an unreachable wait-timeout branch. |
| Task controls invalidate an obsolete cache namespace. | Cancellation and agent controls invalidate shared task pages and owning observability. | The unused `runs` query-key namespace. Model trace Run entities remain unchanged. |
| Collection publication claims to be read-only. | Wait/get-result declarations describe their common notification publication and use effectful annotations. | A false MCP read-only promise. Shared deterministic publication still closes the terminal-before-notice race. |
| APPL evaluator recognizes only the alias. | Accept canonical `wait_tasks` and the shipped alias, preserving the required subsequent loader verification. | Rejecting equivalent canonical collection evidence. |

Passive indexes contain keys/references, not a new mutable task authority. Startup
replay builds them once from complete latest records. The sole history writer,
recipient-input acknowledgement, conversation owner and native workload owners
remain in place. SessionMail now owns explicit collection commitment; StepRecorder
delegates to it rather than duplicating that construction.

## Construction, containment and acceptance

The initial correction and regression batch is constructed before execution.
It covers sparse pages and bounded candidate work; peer stream overlap/revocation;
late parent identity/replay; immutable Question retries; unsubscribe after reads;
non-consuming Question snapshots; revoked query/observe recovery with later human
feedback; concurrent content reads/revocation; malformed retained input; workflow
provenance; trusted metadata across actual short SDK calls; and shared UI caches.

Use `D:/Libraries/Documents/projects/clio-agent-task-qualification` for dependency,
static and behavior execution. All writable state remains beneath that repository.
The launcher is `uv run --frozen --no-sync python -B scripts/run_tests.py <case> -n 0`.
Contributor instructions and nested probes use this early bootstrap too. No Core
deployment or behavior execution runs from the C source checkout. Manual-only
roots, rejected cleanup and unrelated live services remain untouched.

Marketplace CI against moving `develop` remains a compatibility signal, not frozen
candidate acceptance. Final qualification records the exact core/GACT/marketplace,
dependency and runtime tuple and executes against that tuple. This correction does
not add relay qualification or restore its special lifecycle.

R33 behavioral tests, fresh source approval, F03, exact-head CI and Q1–Q9/R1–R6 are
not yet accepted. Existing component passes do not qualify this changed source.
Run the constructed cases individually/sequentially with one worker, renew both
independent source reviews and complete the required live matrix before release.
