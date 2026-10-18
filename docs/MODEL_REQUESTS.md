# Model request concurrency

A single conversation can delegate agents or run background model work. The agent
concurrency control limits workers at each nesting depth; it does not represent
the number of requests an inference account can accept.

CLIO separately limits HTTP model calls to **eight per endpoint origin and
credential in each CLIO process**. All models, fresh LM instances, copies,
conversations and agent depths share that budget. A waiting parent holds no model
slot after its request ends, so its children can run. Codex and Claude Code keep
their existing provider-specific connection management.

Extra calls wait in order. Cancelling waiting work removes it without sending a
request. An active call releases its slot after DSPy's stream/transport cleanup.
Waiting appears as a CLIO notice and keeps the turn watchdog alive without
pretending the model has emitted thinking or answer text.

Set these values in the existing user or workspace `config.yaml`:

```yaml
limits:
  lm_max_concurrent_requests: 8
  lm_request_queue_s: 120
  lm_transient_retries: 2
```

The same controls have environment fallbacks: `CLIO_LM_MAX_CONCURRENT_REQUESTS`,
`CLIO_LM_REQUEST_QUEUE_S` and `CLIO_LM_TRANSIENT_RETRIES`. Zero concurrency means
Unlimited locally; the provider's quota still applies. Zero retries disables
automatic recovery. Queue waiting is bounded independently of generation time.

For an HTTP 429 explicitly naming `max_parallel_requests`, CLIO shares the
provider's Retry-After/reset hint across waiting callers. After DSPy's ordinary
retries, one additional recovery may run if no text, thinking or tool call has
streamed and the reset fits within the queue deadline. A reset beyond that
deadline is reported immediately for the current call. Other 429 categories
retain DSPy's existing retry behavior.

A final concurrency refusal records CLIO's local admitted/queued counts. Admitted
calls include the refused call and retain their slot during DSPy's ordinary
retry backoff; this is an upper bound on simultaneous outgoing requests. The
server's account-wide count can include other CLIO processes, other clients or
requests the server has not released. A 429 alone cannot establish which occurred.
This queue is process-scoped, not a cross-machine quota coordinator. Stream audit
records `lm.request.queued`, `lm.request.capacity_refused` and
`lm.request.capacity_wait` without credentials or request bodies.
