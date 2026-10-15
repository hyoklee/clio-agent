# Shared blueprint registry coordination

Core already decides conditional scalar writes under the owning blob's write
token. Blueprint coordination uses those operations through Python; it adds no
Admin service, native ownership ledger, task type or protocol.

## Deployment and scope

Every cooperating writer must run this implementation and connect to the same
authoritative Core deployment, with successor failover disabled. The shared
filesystem must support atomic exclusive hard links, rename and flushed file
writes. This mechanism does not turn independent Core deployments into a
consensus system or protect against an external editor ignoring the guard.

Enroll the **installed registry directory**, not an individual installed pack:

```console
clio blueprints setup --root /shared/clio/agent-blueprints
clio blueprints status --root /shared/clio/agent-blueprints
```

For draft publication, also enroll the parent of the authoring blueprint folder
when that source is shared. Publication holds both registry and source guards in
stable identity order. Install/update/bootstrap/migration, revision recovery,
uninstall/tombstones, relocation and draft writes use the same engine.

Setup stores a registry UUID and Core authority UUID in
`.clio-coordination.json`. Different mount paths therefore use one Core key.
Keep the marker on the shared root; do not copy it to an independent registry.
Unenrolled roots retain their existing filesystem-only scope. Enrollment is
explicit because a local runtime cannot prove that another computer connects
to the same authority. An enrolled root never silently falls back when Core is
missing or its Python bindings are too old.

## Ownership and publication

The first owner uses `kPutIfAbsent`. Later owners replace the `free` record with
`kPutIfVersion`. Each claim includes a random nonce, host and PID. Release uses
the exact native version and writes a `free` record; deleting the blob would
discard version history and permit stale releases, so it is never deleted.
Failed conditional-write versions are diagnostic only; a new attempt reads
again. No heartbeat, deadline, expiry or automatic stealing exists.

Before mutation, the owner flushes a filesystem receipt and publishes it by
an exclusive hard link. This publishes complete JSON, never a partial receipt.
The existing filesystem lock remains held. Other writers refuse any retained
receipt, including when Core has forgotten its corresponding record. Every
publication boundary checks the authority, receipt, nonce and Core version.
Core RPC uncertainty is never retried as another mutation.

Successful completion clears Core ownership before removing the receipt.
Ordinary validation rejection releases the claim. Filesystem, runtime or
ownership uncertainty retains the receipt and existing revision backups.
Directory revision recovery must obtain the same claim first; it cannot roll
back a former owner's in-progress swap merely because time elapsed.

## Inspect and recover

Status reports the filesystem owner even when Core cannot be reached. A receipt
does not prove the owner crashed: it can represent an active writer. Stop the
writer on its owning computer and inspect interrupted journals/backups before
clearing it. Then use the exact nonce shown by status:

```console
clio blueprints recover --root /shared/clio/agent-blueprints \
  --expected-owner OWNER_NONCE --owner-stopped
```

Recovery refuses a changed nonce, an active local owner PID, an occupied
filesystem lock or a different Core owner. It changes ownership only; it does
not claim that an interrupted deck/source/install transaction completed. The
next guarded installer can process its retained revision journal.

If Core lost its authority and there is no filesystem or Core owner, use
`--expected-owner none --owner-stopped` for an explicit rebind. The registry UUID
stays the same. Other enrolled roots keep their old authority until separately
inspected and rebound. No restart-safe numeric fencing or automatic distributed
failover is claimed. Filesystem/power-loss durability is bounded by the deployed
filesystem's guarantees.

## Qualification

Core PR #1273 reverts the separate ownership service. Core PR #1274 exposes the
existing conditionals and versioned reads, bypassing unversioned read caches.
Its real TCP-client process tests cover contention, stale release, exact bytes,
versions and runtime death. Agent tests use test-only conditional storage with
real temporary filesystem guards/journals. These are distinct from cross-node,
shared-filesystem acceptance, which has not been performed. Hosted CI must pass
for the exact heads; no local app/native test or installed package change was
made during this implementation.
