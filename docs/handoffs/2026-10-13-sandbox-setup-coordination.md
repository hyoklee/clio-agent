# Shared Windows native verification

The native Windows sandbox verifier had a durable result but no process-level
ownership around creating it. Two CLIO processes starting without a matching
receipt could both run the same filesystem and network checks. The startup,
Infrastructure and CLI entry points already share the provisioning engine;
this change coordinates its native verification across processes for the same
user configuration directory.

Verification now acquires a local file lock and rereads the receipt before
starting work. A follower reuses the owner's successful or unavailable result.
Contention reports a waiting stage. Waiting is bounded at 35 seconds, against
the verifier's existing 30-second subprocess deadline. If the owner is still
busy, setup returns a specific busy reason and does not start legacy account,
helper or ACL preparation alongside it. The operating system releases ownership
when a process exits; an unfinished verification cannot publish a success.

This addresses a source-confirmed duplication path. It is not a claim that this
path caused the user's earlier 81.65-second shell command. The retained command
audit attributed 35.22 seconds to overlapping legacy workspace grants and left
the other phases unresolved. Those measurements and the previous native-runtime
selection fix remain in the protected-execution handoff.

Regression coverage uses separate real processes and an isolated test receipt,
with test-only verification functions. It covers sharing both verdicts, bounded
contention without overwriting receipts, recovery after owner death and refusing
legacy repair while native verification remains busy. No local tests, native
probes, application rebuilds/reloads or model workloads were run for this change.
Hosted CI supplies qualification. Core and the separate task-system work are
unchanged.
