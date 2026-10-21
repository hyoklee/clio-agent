# NDP metadata cache and background refresh

## Previous behavior and change

Dataset pages had a React Query memory cache, fresh for one minute and collected
after five inactive minutes. Organizations had a five-minute UI memory cache
and a short backend publisher-name cache. The UI caches did not survive reload,
and reopening fresh entries could suppress background revalidation.

The real picker now restores organization lists and previously loaded catalog
pages from IndexedDB before issuing its live query. Existing memory entries are
shown immediately as well. Reopening, changing searches/filters or opening the
organization picker triggers revalidation. Counts and rows remain visible with
a Refreshing indicator. A failed refresh preserves the last successful metadata
and exposes retry; successful refreshes replace the snapshot, including a real
empty result. Data selection remains independent of disclosure and refresh.

Storage is asynchronous and scoped to metadata queries. Keys incorporate the
existing connection scope (endpoint and credential fingerprint), NDP account,
organization/Endpoint, group filter and query. Infinite-query snapshots retain
loaded pages and their cursor parameters. Unidentified signed-in accounts skip
disk persistence rather than using a shared fallback account identity.

The cache accepts snapshots up to seven days old and limits each payload to
8 MiB, twenty snapshots and 32 MiB total. Expired entries are ignored on read and
pruned during writes. Eviction uses IndexedDB key cursors to inspect age/size
without loading all payloads. Invalid schema, blocked storage, oversized data or
quota errors degrade to the ordinary live query; they do not fail the picker.
The backend still validates attachment IDs and actual data access. Neither NDP
login tokens nor scientific file bytes enter this metadata cache.

## Actual UI review

UI `gact-pele-diagrams-1786`, port 5219, connected to the unchanged real backend
on 8209. The affected session was
`http://127.0.0.1:5219/workspaces/ws_fd8714446f0d/sessions/sess_fe140dd3c979`.
No catalog response interception, fabricated UI or image generation was used.

1. Queried the actual catalog and opened the organization picker. It displayed
   152 options, including All organizations.
2. Closed Attach and reloaded the browser tab, creating a fresh application and
   query client. Reopened the actual Attach > NDP flow.
3. The immediate DOM showed **30 of 6,235 datasets Refreshing…** with thirty
   collapsed dataset rows and zero resource checkboxes, while the live catalog
   request remained in flight. Saved data survived the reload.
4. Opened organizations. All 152 options were already present while the UI showed
   **Refreshing organizations…**. Revalidation completed without losing the list.

Real screenshots are in `D:/CLIO-Develop/ndp-cache-20261019/`:

- `catalog-restored-refreshing.png`: saved catalog rows during the live refresh.
- `organizations-restored.png`: immediate restoration/refresh frame.
- `organizations-restored-settled.png`: settled popup after refresh/animation.

No upstream catalog records were changed to manufacture a difference. Changed
results and network failures were exercised in controlled automated tests;
the real browser review establishes persistence and concurrent refresh display.
No files were attached or downloaded, and no model run was submitted. The user’s
backend, Core, credentials and conversations were not restarted or replaced.

## Automated checks

Thirty-one focused tests pass: eighteen existing picker/row checks, seven bounded
IndexedDB storage tests and six cache/picker integration tests. They include:

- A fresh query client restoring persisted rows before a deferred network result.
- Replacement and persistence of changed metadata without dropping a selection.
- Restoring multiple pages and refreshing the actual cursor chain sequentially.
- Cached catalog and organization choices remaining usable after refresh errors.
- Organization retry replacing the last list with changed results.
- Account separation and unidentified-account handling.
- Schema/age rejection, count/byte limits, oversized updates and unavailable storage.

`fake-indexeddb` is a test-only dependency. Production uses actual browser
IndexedDB. Web type checks, lint, formatting and frontend guards pass. The
existing browser fixture suite was not rerun; the live browser review above is
separate evidence. Changes are local to the preview; nothing merged or released.
