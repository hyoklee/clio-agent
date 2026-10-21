# R39 legacy MCP input design adjudication

Frozen inspected core: `27b3a381`; source-only advice, not implementation or runtime acceptance. Reviewer chat: Review task architecture plan. Turn: `01a13fd5-458c-7632-bea1-eb2370afdde4`.

**The invocation-bound connection approach is sound, with one correction: stdio needs a fresh transport as well as fresh client state.** Keep the change inside `ExternalConnection` and its existing retirement path.

1. **Do not use `Client.new()` alone for stdio isolation.** It shallow-copies the client and shares its transport. The pinned [`StdioTransport`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/.venv/Lib/site-packages/fastmcp/client/transports/stdio.py:105) caches the actual SDK session, including callbacks. Two clones can therefore reuse the first connection’s handler; closing either transport can disconnect both. This corrects my earlier recommendation. The existing [`direct_client_factory`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/tools/mcp_task_routing.py:381) already constructs a fresh transport per invocation—reuse that construction path and preserve its configuration.

2. **Give each isolated connection removable ownership.** Currently [`connection()`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/external_tasks.py:160) registers every client’s exit callback on the application-wide stack. Calling `close()` early would still leave those callbacks retaining completed clients until shutdown.

   For invocation-bound connections, let `ExternalConnection` own the entered client directly, or a small connection-local exit stack. Keep it in the existing `connections` dictionary only while live. Close it once, then remove that exact entry and release its submission/client references. Do not register each invocation’s stack on the application stack—that preserves the same accumulation. Shared HTTP connections can retain their current ownership.

3. **Retirement must wait for both submission and observation to finish.** Existing [`_retire_resources()`](/D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/external_tasks.py:577) checks the task driver but not the originating `tools/call` RPC. An accepted task can finish while that RPC is still returning its adoption receipt.

   Retain the single submission RPC on the invocation-bound connection. Close only after its outcome is durably recorded, that RPC has exited, accepted-task drivers have exited, and no adoption recording remains unresolved. Schedule closure outside the SDK callback. Serialize close/reconnect only for that connection.

4. **Use the same retirement owner for every completed path.** Inline success and confirmed rejection currently bypass task retirement. Attach their cleanup to the existing `_record_or_defer(..., retire=...)` mechanism so persistence failure retains ownership and a successful retry releases it. Also release connections when discovery or admission fails before dispatch. Bind the immutable submission only after its confirmation and before sending `tools/call`; reject elicitation before binding or after retirement begins.

   For external work, keep the existing distinction between a recorded terminal server reply and verified physical cleanup. Cancellation may deliberately retain `terminal_at=None` and uncertainty. Requiring `terminal_at` for every external connection would retain completed observation sessions indefinitely; closing observation must not erase that uncertainty.

5. **Application shutdown closes the remaining live connections.** Include openings and submission RPCs in shutdown coordination, alongside existing drivers, before closing their clients. Use `TaskAwareClient.close()` for an exclusively owned stdio transport: SDK context exit alone leaves its default `keep_alive=True` subprocess running. Preserve the existing refusal to close with unconfirmed adoption.

This needs no new registry, queue, or poller: the existing connection dictionary owns live resources, and Core retains history. HTTP and modern input driving can remain unchanged.

Source review only; no edits, tests, or launches.
