# Known services in the connection switcher

The sidebar switcher used only remembered connections. The desktop-managed
local service is intentionally excluded from that list because its endpoint
and bearer token are launch-scoped. Local-to-Aurora switching therefore worked,
but Aurora-to-local switching had no destination row. Connection settings used
the same incomplete inventory, while the opening page already used the shared
known-services hook.

The sidebar and connection settings now use that existing hook. It includes
remembered services, the current managed service and reachable infrastructure
deployments, without persisting the managed service address. The switch callback
accepts the managed row's launch credential. The active service still receives
its live availability probe; inactive rows retain their shared availability.
Settings labels the combined inventory Known services and offers Forget only
for remembered entries.

## Review

Manual browser review used the production navigation, connection provider,
known-services hook, switching hook and settings page with explicitly labelled
sample services and a preview-only native/repository fixture. It covered:

- Local to Aurora and back through the sidebar menu.
- The local destination shown while Aurora was active.
- Local reconnection from connection settings.
- Return using the current local launch credential.
- Only Aurora retained in remembered addresses, with no local credential write.
- Keyboard activation, selection and Escape dismissal.
- Light/dark presentation and a 900-pixel desktop viewport without overflow.

Final review had no browser page errors. Early preview failures were corrected
fixture issues: a missing health integration list and a missing fixed-width
container around the contained sidebar. They were not production failures.

Captures are in the existing visualization directory:
`C:\Users\jaime\.codex\visualizations\2026\10\08\01a11d11-9c09-7051-915b-2d70dba80656`.
Files: `connection-switch-local-2026-10-12.png`,
`connection-switch-aurora-2026-10-12.png`,
`connection-switch-aurora-light-2026-10-12.png`, and
`connection-settings-known-services-2026-10-12.png`.

Frontend type checking, scoped lint and existing file-size/component-reuse/
presentation guards passed. Unit and navigation-integration regressions were
added; suites remain unexecuted at the user's direction. No OPAL turn was
submitted. This review does not establish live Aurora connectivity.

## Installation

The web/offline and native desktop builds passed. The desktop was installed in
CLIO Develop after checking every workspace's sessions and all four recorded
runs were idle/error or terminal. After restart, health returned HTTP 200 and
the retained parent stayed idle. Build metadata records
`known_service_switcher_fix: true`. The review browser and frontend server were
stopped, and Cargo cleanup removed 5.6 GiB of temporary build files. All changes
remain local and unmerged; no agent runtime change is included.

Installed desktop SHA-256:
`3a6d6063d20f878ad20d0c5649da80b972a8cfcc3beee069e1f792663dc39764`.
