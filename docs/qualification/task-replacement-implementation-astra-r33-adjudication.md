# Astra R32 findings adjudication and R33 construction

Read-only source adjudication of core `504fc232` / GACT `d0e03b5a`. This is architecture/source feedback, not acceptance of the uncommitted R33 implementation or runtime qualification.

## Review turn 01a13e5d-5850-78b3-905c-5a61935390a0

**Yes—this conforms to R2 and is preferable to adding query-specific caches or count owners.** R2 requires filtered pagination, authorization and bounded indexed reads; it does not require an exact total. [Contract](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/docs/design/task-replacement-plan.md:58).

I would approve it with these conditions:

- **Scope the candidate index first.** A model’s session/tree query must not walk every task belonging to the human. Authorized peer discovery can combine existing grant-scoped streams, deduplicating handles.
- **Bound candidates examined, not just rows returned.** Sparse filters can otherwise scan an entire history to fill one page. Permit a short or empty page with a continuation cursor when the scan budget is exhausted; clients must not interpret that as exhaustion.
- **Use stable cursor ordering.** Retain an immutable ordering key such as `(created_at, handle)`, bind the cursor to caller/scope/filters, and resume after the last examined candidate. Recheck current rights on every page. A merely base64-encoded cursor must not expose unauthorized task identities.
- **Return exact totals only when the index exactly represents the authorized, filtered, deduplicated result set.** Otherwise return `null`. Fully owned does not make an unfiltered cardinality correct for an additional status/tool filter.
- **Treat pages as live views.** Status and grants may change between requests; avoid implying a frozen snapshot or invalidating every cursor on routine progress updates.

There is a concrete wire change: [GACT currently requires an integer total](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/external/gact-tui/packages/core/src/v3/task-repository.ts:61), and Runs renders “Showing X of Y.” Make the schema nullable and display **“X tasks loaded”** plus continuation when the total is unknown. Never coerce `null` to zero.

Keep tests for authorization, filters, stable ordering, deduplication and cursor progress. Replace exact-count assertions only where an exact count is no longer promised, and cover sparse pages and revocation between pages.

This addresses the query/count portion of F03 within the existing passive-index owner. Segment-finish scans and read-lock contention remain separate findings. No implementation or execution performed.

## Review turn 01a13e59-b8c2-7800-8f21-384921ee4394

**Architecture: GO. Source: still NO-GO. Release qualification: still blocked.** Fable supports the ownership design, but several findings need narrowing.

I verified that `504fc232` / GACT `d0e03b5a` changes only tests relative to the reviewed production pair.

| Finding | Adjudication and correction |
|---|---|
| **Revoked or withdrawn collection blocks later input** | **Release blocker.** My earlier finding stands. Revocation and unsubscribe are legitimate operations; neither should strand unrelated conversation input. Correct this in `StepRecorder` / `SessionMail`, preserving the sole recipient-input acknowledgement. |
| **Lifetime scans** | **Valid source defect against F03.** Query pagination and segment finish repeatedly examine retained history. Use narrow existing indexes and cursor traversal. Cancellation recovery must preserve membership **at the original request time**; replacing its historical predicate with today’s active set would be incorrect. |
| **Core I/O under the global lock** | **Valid contention risk, not demonstrated deadlock or measured failure.** Include it in F03. Capture immutable references under serialization, perform bounded reads outside it where safe, and recheck authorization before disclosure. |
| **Question creation compares mutable definitions** | **Valid owner-contract defect.** Compare the immutable accepted request, excluding later resolution and explicitly owner-added annotations. Continue rejecting changed prompt/schema/ownership. The report overstates reconnect impact: external elicitation already reuses an existing posted Question without calling `create` again. |
| **Workflow failure displayed as unknown** | **My earlier finding remains.** Later steps with no handle are “not launched,” not missing task visibility. Project the existing runner’s recorded failure and step provenance. |

The proposed **typed access denial** is the right correction. [ContextReader already protects uncommitted observations](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/context_reader.py:148). Keep the original observation protected and uncommitted, show that placeholder, and allow unrelated eligible input to commit. Catch a specific authorization outcome—not `ValueError` generally. Malformed references, digest/content inconsistencies and Core failures must remain strict failures.

For **unsubscribe**, narrow the treatment further: withdraw the subscriber notification without invalidating an independently authorized explicit result read. Do not acknowledge the withdrawn notice or consume the owner’s notice.

The remaining Fable findings classify as follows:

- **Admission exceptions:** a defensive/error-reporting gap as presented. The cited non-string payload is not shown reachable through validated normal submission. Valid-input setup failures need visible, exact-input holds; malformed durable data must not be silently skipped or repeatedly retried.
- **Eager assignment creation:** **not an ownership violation by itself.** Acceptance already returns a durable queued handle for ordinary human messages. Promotion uses the same conversation owner, while TurnRunner retains execution admission. Cover failed promotion/withdrawal explicitly; do not introduce another assignment manager.
- **Unreachable workflow timeout branch:** maintenance cleanup. Preserve unbounded waits and owner-enforced explicit deadlines.
- **`runs` versus `tasks` cache key:** real, small UI defect. Correct the invalidation; Runs’ own cancellation already invalidates `tasks`, and polling limits the stale-view interval.
- **Marketplace relay pack:** **reject the finding as stated.** `cluster-operator` lacks its executable manifest; discovery requires `AGENT.md`. Historical expert files do not restore relay execution.
- **Evaluator and marketplace CI:** test-evidence issues. Recognize canonical `wait_tasks` alongside the retained alias. CI against moving `develop` cannot qualify the frozen candidate.
- **Missing peer/restart/intervention cases:** qualification gaps, not proof those implementations fail. They remain required before release.
- **Missing human references:** withdraw that report limitation given the supplied `HUMAN-REFERENCES/` manifest/hash receipt.

**Keep collection’s shared notice publication for now.** My earlier race judgment is unchanged: a terminal snapshot can exist before its notification. Publishing deterministically before collection captures receipt identities prevents a later automatic notification from delivering the same result again. [The existing path](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:67) uses the common publisher and creates no second acknowledgement.

Its `read_only` annotation deserves correction or clarification because publication can wake recipients. Moving publication is acceptable only if the existing commit boundary fully replaces that race protection; simply deleting it is a regression.

No edits, tests, services or cleanup were performed. The newly rejected cleanup root, its files and its parent remain untouched and manual-only.
