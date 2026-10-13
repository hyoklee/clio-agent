# Marketplace installation locks and shared filesystems

Source inspection on 12 October 2026; no Aurora or NFS test was executed.

## Assessment

The current implementation is unsafe for a supported deployment in which
multiple CLIO nodes can mutate the same blueprint installation directory.
This is a source-based finding: ordinary, documented NFS configurations can
defeat cross-node exclusion, and several installation lifecycle paths have
additional crash and concurrency gaps. This does not establish that a deployed
registry has already been damaged. No remote fault injection was performed.

The deployment design should therefore avoid a shared writable installation
root. Give each CLIO instance its own writable local snapshots and share pinned
marketplace sources or published immutable artifacts as read-only inputs.
This is a proposed mitigation, not an implemented configuration change.

## What the lock currently does

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

## Concrete failure paths found in source

| Failure | Consequence | Source evidence |
| --- | --- | --- |
| NFS locks configured as client-local, or coordination lost during a storage failure | Two nodes can enter installation or recovery concurrently. `_ACTIVE_REVISIONS` is process-local, so another node can treat a live transaction as abandoned and delete its staging directory or roll back its destination. | `default_registry_migration.py::registry_install_lock`, `blueprint_install_revision.py::_recover` |
| Process death between moving an old default pack to backup and moving its replacement into place | The installed pack is absent. Exception handlers do not run after abrupt termination. Default migration uses `.clio-registry-staging` without a journal; the revision recovery code only scans `.<root>-revisions`. | `default_registry_migration.py::replace_pack_atomically`, `blueprint_install_revision.py::recover_install_revisions` |
| Discovery overlaps a directory swap | Discovery releases the recovery lock before enumerating and parsing installed trees. It can observe a missing pack, a mixed set of old/new packs, or a path that disappears between enumeration and reading, even when writer locking works. | `agent_blueprints.py::discover_agent_blueprints`, `blueprint_install_revision.py::InstallRevision.apply` |
| Uninstall overlaps another process's install, bootstrap or uninstall | Uninstall does not acquire the installation file lock. Its deletion and subsequent read/modify/write of the tombstone ledger can race another process, lose removal decisions, or allow resurrection. The route's thread lock only coordinates its own process. | `agent_blueprint_refresh.py::uninstall_agent_blueprint`, `blueprint_reload.py::apply_blueprint_change` |
| Uninstall ledger is corrupt or unreadable | Reading it returns an empty set, which can authorize automatic reinstall of packs the user removed. Atomic JSON replacement alone does not protect read/modify/write against competing processes. | `agent_blueprint_refresh.py::read_uninstalled_tombstones`, `write_uninstalled_tombstones` |
| Storage is unavailable, locking is unsupported, or permission/I/O errors occur | Some lock failures can look like contention. `timeout=0` bounds lock contention waiting, not the filesystem calls needed to open, resolve, inspect or rename paths. Hard NFS mounts may retry storage requests indefinitely. | Installed filelock 3.20.0 Unix backend; `registry_install_lock`; Linux `nfs(5)` |

`write_json_atomic` fsyncs the replacement file, but does not fsync the containing
directory after replacement. Staged blueprint files and directory renames also
lack an explicit durable-publication protocol. Power-loss/server-restart
durability therefore needs a specified contract and failure testing; the current
exception rollback tests do not establish it.

## Hardening plan, in order

1. **Contain shared-storage risk.** Make local, instance-owned writable blueprint
   snapshots the supported default. Detect the actual mount for both global and
   workspace installation roots, including bind mounts. Refuse automatic
   mutation on known unsupported shared filesystems and explain the affected
   path and remedy. An unknown mount is not proof of distributed safety. A
   shared home directory must not silently select shared writable installs.
   `CLIO_AGENT_CONFIG_DIR` can relocate the existing global root; workspace
   installs resolve separately and need their own handling.
2. **Use one mutation protocol.** Put bootstrap, default migration, explicit
   install/reload, uninstall, tombstones and recovery under the same lock order
   and transaction boundary. Distinguish contention, permission failure,
   unsupported locking and storage I/O failure. Record operation ID, host,
   process, root and elapsed time separately from the lock inode, because the
   deployed filelock backend truncates that file during acquisition attempts.
   Treat holder metadata as diagnostic only; never infer ownership or permission
   to break a lock from a PID, timestamp or lock-file age.
3. **Publish immutable generations.** Stage and validate complete snapshots,
   then publish one generation reference. Readers and active turns resolve a
   generation once and retain it for their lifetime. Keep the last good
   generation until readers release it. Uninstall decisions belong to the same
   committed generation. This removes the missing-directory interval and mixed
   registry reads instead of relying on every reader timing its lock correctly.
4. **Make recovery conservative and durable.** Replace the unjournaled default
   migration swap with the common transaction machinery. Define file and
   directory flush ordering for each supported platform. Retain/quarantine
   ambiguous journals and backups, validate expected generations/checksums
   before restoration, and preserve uninstall decisions when ledgers cannot be
   read. Keep usable verified snapshots available while reporting degraded
   readiness. NFS acquisition and recovery must not run on a UI request path
   where an unavailable mount can stall discovery.
5. **Qualify failures explicitly.** Add genuine multi-process crash tests on
   local supported filesystems, then have the owning infrastructure run the
   cross-node matrix below. A successful one-time lock probe is evidence about
   that mount at that time, not a distributed coordination guarantee.

If a shared writable registry remains a requirement, use a controlled publishing
service with permissions that prevent clients from mutating its storage
directly. Multiple publishers require storage-enforced fencing so an old writer
cannot commit after losing ownership. A timestamp lease, a PID file, an NFS
`mkdir` lock, or moving the lock file to local disk does not provide that
guarantee. These are design requirements, not claims about features already
present in CLIO.

## Acceptance matrix

Run only against dedicated disposable roots on the owning infrastructure.
Preserve journals, checksums, operation receipts, host identities, mount details
and exact build/dependency versions for every case.

- Two processes on one host and two clients on the real shared mount attempt
  bootstrap/install/reload/uninstall together, including different runtime and
  marketplace revisions during rolling upgrades.
- Kill the writer after staging, journal publication, each old/new rename,
  tombstone publication and commit. Restart twice to check idempotent recovery.
- Exercise client-local locks as a deliberate negative case, unsupported lock
  operations, permission denial, full disk/quota, and damaged journals/ledgers.
- On infrastructure reserved for destructive qualification, exercise network
  interruption, client death, server restart/failover and lock recovery. Confirm
  that a resumed stale writer cannot publish over a newer committed revision.
- Discover blueprints and keep an active turn reading throughout updates and
  failures. Readers must retain one complete generation; no user edit or
  uninstall decision may disappear. Failures must identify the operation and
  leave recoverable evidence, and busy startup must not be presented as a
  permanently disabled agent.

The audit did not change runtime locking, run test suites, or reconfigure any
local or remote service. Implementation and the acceptance matrix remain work
to complete before shared writable installations can be supported.
