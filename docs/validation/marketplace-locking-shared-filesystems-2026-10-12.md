# Marketplace installation locks and shared filesystems

Source inspection on 12 October 2026; no Aurora or NFS test was executed.

## What the implementation guarantees locally

`gact/default_registry_migration.py::registry_install_lock` resolves
`<blueprint-install-root>/.clio-default-registry.lock` and acquires a cached
`filelock.FileLock` with `timeout=0`. It yields false immediately on a lock
timeout. Nested calls in one thread share an instance and remain reentrant.
The lock coordinates cooperating writers to that installation root. Separate
installation directories use separate locks.

`gact/blueprint_install_revision.py` uses this lock and the process-local
`BLUEPRINT_MUTATION_LOCK` while staging, swapping and recovering installed
blueprint revisions. The recovery and installation paths can raise
“Another CLIO process is changing this marketplace; retry shortly” on contention.
The message has no holder identity and can also describe competing threads.

During preparation of an isolated Windows service, discovery temporarily
returned a disabled base-agent row carrying that diagnostic. Startup later
installed all 14 default packs from the local marketplace checkout, including
enabled APPL-CORE and base-agent entries. The logs do not establish which thread
or process held the lock. The service was subsequently stopped, with no OPAL
model turn submitted.

This exposes a diagnostic/readiness concern: temporary bootstrap contention can
look like a broken or disabled agent while installation is still progressing.
The exact holder and a startup-state presentation fix remain unverified.

## NFS scope and limitations

The inspected environment has filelock 3.20.0. Its Linux implementation uses
`fcntl.flock(LOCK_EX | LOCK_NB)`. Its Windows implementation uses `msvcrt.locking`.
Newer filelock documentation may describe different implementation details;
check the deployed dependency before drawing conclusions from it.

In that inspected Unix backend, `ENOSYS` raises an unsupported-filesystem error.
Other `flock` errors leave acquisition unsuccessful and can surface through the
generic timeout path. A busy message therefore does not by itself distinguish
an actual holder from every filesystem locking failure.

Linux supports remote NFS flock locking by emulating it with whole-file fcntl
locks. Mount configuration can instead make flock local to each client; see
the [Linux flock NFS semantics](https://www.man7.org/linux/man-pages/man2/flock.2.html)
and [NFS mount options](https://man7.org/linux/man-pages/man5/nfs.5.html).

Consequently, if multiple nodes mutate the same installed blueprint directory
on NFS, this lock can coordinate them only when remote locking works across
those clients. A local-only lock would allow competing writers on different
nodes. The process-local Python lock cannot compensate for that. CLIO currently
does not verify this mount property or provide cross-node holder diagnostics.

The lock is advisory coordination for installations, not a distributed
scheduler or a guarantee that every filesystem read sees a complete registry
revision. Linux retaining the lock file after release is expected; the file's
existence does not establish that a lock is held. Do not unlink it to bypass
contention.

## Evidence still needed from the owning environment

Before claiming shared writable installations are qualified, record the actual
filesystem, NFS version and mount options, then verify exclusion using two
clients of that mount. One holder must exclude the other; release or holder
termination must permit a later acquisition. Concurrent installation and
discovery must preserve valid snapshots and a truthful busy/ready presentation.

Use a dedicated disposable installation root for that validation, preserve its
receipts, and leave deployed registries intact. No such remote validation is
performed or claimed by this audit.
