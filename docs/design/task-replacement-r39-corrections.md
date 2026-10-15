# R39 construction

Parent core: `27b3a381`. GACT remains `41660185`.

This is implementation/regression construction, not runtime acceptance.

| Finding | Existing owner and correction | Required proof |
| --- | --- | --- |
| Raw native cancellation discarded acceptance before physical cleanup | NativeTools retains its SDK call/identity until canonical `terminal_at`; remove the now-redundant later terminal check. | Actual native SDK status after cancellation while cleanup is held, repeated cancellation and shutdown settlement. |
| A fresh cancelled reply retained stale lost-visibility uncertainty during known cleanup | The native settlement owner validates captured output and full same-runtime custody across every incarnation, then restores nonterminal cleanup progress. Unknown incarnations, invalid output and foreign identity remain uncertain. No shared-wait change or new driver. | Constructed real-worker recovery/wait cases plus negative custody/schema/incarnation cases. |
| Nullable spawn tests used deleted execution fixtures | Rebuild over the actual FastMCP control boundary and confirmed Core owner; retain explicit-empty placement rejection. | Null/type validation before discovery/acceptance and no accidental child execution. |
| Document autosave coalescing was lost with the retired inbox | Withdraw older undelivered producer notices through the existing Core mailbox, retaining bodies/history. Staging repeats that rule after interrupted withdrawal; staged old input cannot commit. Stable document-version identities prevent retry duplication. Explicit human review is never coalesced. | Constructed normal/faulted acceptance, replay twice, full retained history and stale-input commit rejection. |
| Factorio promised an absent typed child-input control | Use finite consultation output, the parent's actual Question tool and messaging to the retained child session; distinguish linked assignment from historical result. | Shared shipped-agent prompt assertions; subsequent live child/Question gates remain mandatory. |
| Independent provider/presentation tests imported retired paths | Preserve generic preflight/provider cases and actual wait presentation. Remove only the explicitly retired relay-discovery startup case. | Scoped checks plus later focused execution. |

The legacy stdio/SSE inline-input attribution defect remains open. Astra's SDK
adjudication requires invocation-bound sessions with fresh transports, retained
submission/observer custody and removal of completed connection resources. A
client clone alone shares stdio transport/session state and is insufficient.
Do not treat the partial native corrections as acceptance of that route.

AST inventory: 1,093 test files inspected; 37 still import missing modules,
deleted test fixtures or exact retired symbols. This is not pytest collection or
proof that other call signatures work. Complete the coupled regression migration
before behavioral execution. F03, exact-head CI and Q1–Q9/R1–R6 remain pending.

All writable static/runtime state remains in the D qualification repository.
R38 review process 24400 is absent. Its bounded report/model receipt is retained;
automatic review rejected removal of its 348,521-byte disposable runtime, which
is now manual-only. Earlier rejected paths remain excluded.
