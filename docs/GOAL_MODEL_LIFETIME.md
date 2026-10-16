# Goal iteration and model connections

The goal sequence is work, then an awaited completion check, then the next work
turn. These stages do not intentionally run as three simultaneous model requests.
An idle conversation also does not itself issue a model request.

Registered work agents borrow a session-owned model client across forwards,
including successive goal iterations. Rebuilding an agent module does not rebuild
its provider client. Each forward receives a lightweight DSPy view with isolated
usage history and request settings over the same connection pools. Its current
model hooks still run. Different sessions and registered agents have separate
owners; an idle session does not create clients or issue requests.

Credentials are resolved before every forward. When credentials, endpoint, model
or generation settings change, the owner replaces that scope's client and closes
the old pools after their last active user. Changing settings never closes another
in-flight request. Session deletion and application shutdown retire owned work
clients; cancellation and failed work release their leases. Shutdown rejects late
workers trying to recreate an owner after it has closed.

Goal checkers remain ephemeral: clients they create close immediately after the
check, including failures, timeout and cancellation. A checker that borrows an
existing session or Fleet client does not close it. Hook-created temporary clients
and forwards without an app session retain operation-scoped cleanup. History and
usage remain readable after cleanup.

The regression tests use real local HTTP connections and count active requests,
open sockets, connection creation and the actual Authorization headers separately.
Twenty-one work/check cycles reuse one work pool and close twenty-one owned checker
pools. All 63 requests run sequentially. Six additional idle sessions issue no
requests. Credential replacement, configuration changes during a lease, request
cancellation, separate session pools, deletion and shutdown are tested too. An
inherited client can retain one reusable idle socket while its active request count
is zero. An open keep-alive connection does not itself prove an inference request
remains active.

The reported AMSC `max_parallel_requests` 429 does not expose the gateway's
individual reservations. This fix addresses the confirmed client-lifetime gap;
its relationship to that protected gateway's count requires gateway-side evidence
or a fresh run on the affected machine. No concurrency cap or retry policy changes
are part of this correction.
