# Replacement regression migration

Behavioral execution remains deferred until initial implementation and bulk
regression construction are complete. Removing architecture-bound cases cannot
remove a required behavior from the acceptance ledger.

## First retained-algorithm batch

| File | Replacement/removal | Retained requirement |
| --- | --- | --- |
| test_gact/test_hook_invariants.py | Replace removed mailbox readers with actual confirmed Core pending/header reads and input acknowledgements. No test case removed. | M01/M03/A08: bounded Stop-hook redrives remain durable; reads never acknowledge them; infrastructure failure never redrives. Keep the independent hook matching, permission, ordering and cap algorithms. |
| test_tools/test_mcp_execution_era_visibility.py | Remove only the obsolete special RelayTransportClient classification case. | N03/N16: preserve the seven independent server-handshake/status/semantic-event cases; generic connection classification remains in test_mcp_connection_era.py. R2 explicitly removes special relay transport. |
| test_tools/test_mcp_dual_emission_consume.py | Remove the special relay federation/serve-owned wait fixture and its one integration case. | N16: preserve nine independent twin-detection/distinct-content cases and actual FastMCP inline calls. Historic nested payload data remains a decoder/algorithm fixture, not a live relay owner. Generic native/external acceptance is covered separately. |

Scoped Ruff/format and Linux Mypy passed on these three files, including a second
Mypy pass with untyped legacy bodies checked. No pytest or live route was run.

The AST-only recheck reduces the original 37 known files importing removed
production modules to 34. This is not a complete collection claim: the initial
inventory excludes missing imported symbols and imports of deleted test fixtures.
For example, test_document_artifacts.py still references test_core_task_mailbox
and old mailbox helpers. Its autosave-versus-explicit-review lesson must be
retained when that fixture is rebuilt; it has not been migrated or executed.

R37 source review remains NO-GO with two Astra findings pending correction;
Claude's independent review of the same frozen tuple is running. No acceptance
row, release or installed-state claim follows from this migration batch.
