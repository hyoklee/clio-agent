# R38 Astra source adjudication

Frozen source: core `27b3a381d7c2da939a57e308c4f0e1cf87c3fe4e`, GACT `416601856a1e828f658fd59fe6bc5bc4f1129f05`, marketplace `999fdafa9d0f1214e3f9f4f98a6d4d4a8f8f3751`.

Reviewer chat: Review task architecture plan. Turn: `01a13fcc-7a6b-7103-89db-1f0203ca0098`. Read-only source adjudication; no execution or qualification claim.

At R38 (`27b3a381`), **the premature retirement finding is confirmed. The elicitation finding needs a transport-specific qualification.** I checked installed MCP 2.0.0 and FastMCP / fastmcp-tasks 4.1.0.

1. **Native registrations are removed before physical settlement.**

   [`_retire_resources`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/native_tools.py:694) accepts a raw terminal backend reply plus driver/RPC exit, then removes `_calls` and `_identities` even when `terminal_at` remains unset. The SDK can report `cancelled` before cleanup finishes.

   This has concrete consequences: subsequent matching observations fail as “Unbound native task reply”; another cancellation reports uncertainty because acceptance custody disappeared; and [`settle_shutdown`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/native_tools.py:171) no longer includes that handle in its `_calls` settlement-wait loop.

   **Minimal correction:** retain acceptance and observation registrations until canonical settlement sets `terminal_at`, keeping the existing driver/RPC-exit checks. The existing cleanup callback already retries retirement. No additional registry or polling loop is needed.

   This does **not** prevent every late settlement: [`_settle`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/native_task_settlement.py:96) can recover the captured contract from durable submission data after `_calls` disappears.

2. **Inline elicitation loses attribution on some receive-loop paths.**

   CLIO sets `host.inline` in the submitting coroutine and reads it in [`external_task_inputs._input`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/external_task_inputs.py:137). Whether that works depends on dispatch:

   | SDK path | Submitting context available? |
   |---|---|
   | Legacy stdio callback | **No.** Separate receive loop, ordinary memory streams. |
   | Legacy SSE shared receive stream | **No per-call guarantee.** It carries the reader’s context. |
   | Streamable HTTP request-scoped response stream | **Yes.** The pinned SDK explicitly propagates sender context. |
   | Modern inline `InputRequiredResult` | **Yes.** The SDK invokes the input driver in a task inheriting the caller’s context. |
   | Accepted background-task input | Uses the existing synthetic task-ID/input-key correlation. |

   The important counterevidence is the SDK’s [`sender_ctx` dispatch](/D:/Libraries/Documents/projects/clio-agent-task-qualification/.venv/Lib/site-packages/mcp/shared/jsonrpc_dispatcher.py:671) and [HTTP context propagation](/D:/Libraries/Documents/projects/clio-agent-task-qualification/.venv/Lib/site-packages/mcp/client/streamable_http.py:611). A blanket “receive-loop callbacks cannot inherit context” finding would be incorrect.

   **Existing correction point:** [`TaskObservationTransport` / `ObservedTaskSession`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/tools/task_transport.py:44), with the callback’s `ClientRequestContext(session, request_id, meta)`. However, that request ID identifies the **elicitation**, not its originating tool call. Server-side `related_request_id` controls routing; it is not automatically transmitted as parent identity over stdio. An outbound-ID map alone therefore cannot fix legacy attribution. Those paths need a verified echoed origin identity or a session explicitly bound to one invocation; the existing `TaskAwareClient.new()` supplies a fresh-session mechanism.

These are bounded corrections within existing owners. No implementation or tests were run. The Fable R38 report was not yet present in this checkout, so this adjudicates the described observation rather than its final wording.
