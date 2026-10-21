# R40: external input attribution and transport retirement

Parent core: `1db2742d`; GACT `41660185`; marketplace `43af7a01`.

Apply Astra's pinned-SDK adjudication inside the existing ExternalTasks owner:

- Stdio/SSE calls use invocation-bound connections with freshly constructed
  transports. Reject sharing a live transport; do not use Client.new to claim
  transport isolation. Shared HTTP/modern input propagation is retained.
- Bind confirmed immutable submission context before sending the RPC. Callback
  session identity must match; accepted-task input cannot fall back to inline
  attribution. Preserve original captured schema and server/auth/task identities.
- Move the existing connection construction into external_task_connections.py.
  Connection-local exit stacks replace the application-wide callback accumulation.
  This module adds no task records, scheduler, execution driver or polling loop.
- The connection retains its live RPCs and accepted SDK observers. Retire an
  exclusive transport after recorded inline/rejection/terminal evidence and actual
  RPC/observer exit. Keep uncertain acceptance and unconfirmed adoption custody.
  Closing observation does not confirm external cancellation cleanup.
- Shutdown awaits existing openings/RPCs, retires observers and closes remaining
  clients. Explicit close also retires SDK stdio keep-alive subprocesses.
- Reject task replies whose task ID, full backend or submission reference differs
  from their captured binding before publishing an observation.

Constructed regression: two actual legacy stdio servers and real Core, concurrent
questions with missing caller ContextVars, separate invocation attribution, reverse
answer ordering, stored inline results and process-birth-based retirement checks.
The existing malformed-output case additionally rejects a foreign task reply while
preserving the original record and eventual captured-schema failure.

Scoped Ruff/format and Linux Mypy pass for the five changed Python files. The
800-line, removal, class and swallow guards remain unchanged. Behavioral tests,
SSE/HTTP/input recovery, F03, CI and all live gates remain unexecuted/pending.
The 37 coupled legacy-test files still need migration; this is no completion claim.
