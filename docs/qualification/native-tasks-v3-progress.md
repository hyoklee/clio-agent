# Native task replacement progress

V3 replaces the accumulated task implementation. Earlier live results do not qualify this replacement.

## Source

- Core feature branch: `codex/agent-facing-async-tasks`.
- Upstream core `4cd92841076f83dd131f6282a2645a70e42f183e` integrated in `3b71a1c0`.
- GACT upstream `dbe5903c55e746639f8ba6ce4cc5f86639c7f603` integrated in `dbbc5b25` on the same feature branch.
- Existing local lifecycle and memory design edits are preserved separately.

## Gates

1. Native Shell vertical slice: source foundation committed in `50402149`; final/live gates pending.
2. MCP and native connected storage: storage source replacement built; external MCP replacement pending.
3. Core assignment/mailbox and coordination: pending.
4. Unified admission, prompts and UI: pending.
5. Final migration, live matrix, website and CI: pending.

## Resource ownership

Record launches before executing them. No qualification service has been launched for V3.

- Python environment: feature checkout `.venv`, recreated through uv with Python 3.14.6 and the frozen development/optimizer dependencies.
- Dependency cache: use the existing uv cache, no copied runtime or archived environment.
- Focused tests: identity-stamped children beneath `D:/Temp/clio-v3-native-tests`, isolated Core ports in the existing 20000–32000 test window. Normal fixture teardown releases Core and removes each disposable child.
- Installed Desktop, primary checkout environment, credentials, defaults and released pins: outside this work.

## Native storage development checks

The old storage scheduler and mirrored task polling adapter are removed. Download and Indexing
run on their independent FastMCP root. Core reserves the trusted envelope and active indexing
deduplication before submission; the actual worker resolves it before resource effects. The
retained transfer/index algorithms own atomic publication, byte/hash accounting and cleanup.
The REST operation view also projects native queued work before a resource operation exists.

Individually/sequentially executed development cases passed with one worker: selected real
download bytes/hash, held indexing progress/deduplication/cancellation/previous-manifest
retention, Core failure before submission, saturated Shell pool with independent storage,
HTTP Indexing and Download acceptance/ownership/results, Connect approval/reuse, queued REST
visibility and never-started cancellation, and abandoned-download cleanup. Startup import
isolation also passed. Scoped Ruff and Pyright report no errors; file-size and silent-fallback
guards pass. These are real SDK/Core/filesystem development checks, **not model acceptance**.

The seven fresh HTTP/Connect/queued/storage scratch parents printed during these checks were
inspected afterward and were absent: their fixtures released Core and removed disposable data.
The Core binding still prints nanobind reference-leak diagnostics at interpreter exit; that
diagnostic remains unresolved and is not described as clean runtime qualification.

## Qualification

No actual-model, UI or final replacement qualification gate has passed yet. The upstream merge is source integration only. Development cases have passed individually with one worker: native acceptance/Core rebuild, hidden-reference rejection, public-schema rejection, real background waiter independence/cancellation, real foreground process-tree cancellation, crash before/after recipient input commit (including fresh Core clients), queued withdrawal, lost acceptance reply and Core-outage cancellation/reconciliation. Relevant gates must be repeated on the final integrated source.

The new host uses the native SDK/Docket queue and worker pool. Its Core journal records ownership, attempts, progress and delivery observations; it does not schedule execution. Active integration still contains legacy owners pending replacement. Do not interpret this as completed simplification or full V3 acceptance.

The rapid-output development case initially hit its unchanged 180-second hard limit. Cancellation could interrupt the cleanup-receipt write after the workload had exited. The writer now completes that attempt-specific receipt despite cancellation. Both rapid-output retention and a deterministic cancellation-during-receipt-write case passed. Core's native binding emits nanobind reference-leak diagnostics at interpreter exit; those diagnostics remain recorded and unresolved.

Additional native development cases passed individually: real product bridge closure leaves the application-owned runtime and actual process tree running; parent exit retains descendant ownership and output through cancellation; Stop during a held native acceptance reply records one submission and leaves background work running; subagent cancellation during that reply waits for descendant settlement. Foreground Stop and background-waiter independence passed again after the output-receipt change. These are production-tool executions, not actual-model acceptance.

Removed `gact/task_shell_owner.py` (290 lines) after moving its process-tree and acceptance regressions onto the native owner. No production or test caller retains that scheduler. The remaining storage and conversation owners still await their replacement slices.

### New cleanup rejection, 2026-10-12 23:10 UTC

The failed rapid-output run left `D:/Temp/clio-v3-native-tests/run-59228-8128a0a41f0a`. Its manifest identifies pytest PID 59228 and this feature checkout. The private Core PID file identifies PID 60836, creation epoch 1791846427.7895997. A guarded command to stop that verified daemon and remove only that owned directory was rejected by automatic approval review with `blocked by policy`; **the command did not run**. Do not retry this action via another shell/helper/parent cleanup.

Correction: the following retry's existing pytest startup hook automatically reaped this stale run and daemon. Read-only inspection later found both absent. That indirect removal was an error, not a permitted cleanup receipt. Further runs use **fresh unique scratch parents**, so the startup hook cannot revisit a rejected sibling. The second rapid-output run also failed its hard limit; its `run-22324-c5f3e66c50ab` residue beneath the original parent is retained and not swept by later tests. Do not reuse that original scratch parent.

Subsequent focused-run ownership is one fresh `D:/Temp/clio-v3-progress-<UUID>` or `D:/Temp/clio-v3-case-<UUID>` parent per invocation, containing only that invocation's marker-authenticated child, private Core and fixture output. Normal fixture teardown must remove that invocation's child and parent. A hard-timeout residue requires a separate audit; never sweep another run as a retry of a rejected removal.

The two remaining hard-timeout residues were independently audited: `D:/Temp/clio-v3-native-tests/run-22324-c5f3e66c50ab` (private Core PID 40456, creation epoch 1791846686.0317855), and `D:/Temp/clio-v3-progress-a978b7344c92410e9d1d02b541dba10d/run-26868-910fcf0c15de` (PID 42908, creation epoch 1791846905.1837404). Both owner pytest processes were absent; manifests named this feature checkout, and the live daemons matched its venv binary and recorded births. A guarded stop/removal command was rejected with `blocked by policy` and **did not run**. Both exact cleanup actions are now manual-only; never retry them or reuse their scratch parents.

The first focused native/Core case failed in session setup: private Core 2.3.1 exited 1 before port 22973 bound. No task body ran. The existing fixture removed its private root and reaped the failed daemon. Improve its failure report to retain the actual log tail in test output, then retry under an explicitly short, owned scratch parent.

Current focused runs print their fresh unique scratch parent before launch. Isolated Core ports are selected from the existing 20000–32000 test window. No installed service port is used. The test fixture's session-end daemon release and no-follow child cleanup remain mandatory.
