# Find, access and analyze scientific data

## Discover an appropriate collection

Start from the user's research question: phenomenon/variable, place or station,
time interval, resolution and desired output. Use known references and infer what
the context establishes; ask only for ambiguity that changes the selection.

1. Inspect `connected_data_status` for approved resource selections and
   `open_references`, catalogs in `ndp_catalogs`, and services in `ndp_endpoints`.
2. Resolve a requested publisher with
   `connected_data_ndp_organizations(query="earthscope")`. Use its returned `id`
   and `endpoint_id`, not a guessed organization slug.
3. Search with `connected_data_search_ndp(query=..., organization=...,
   endpoint_id=...)`. Query matches metadata, not every value in the underlying
   data. Start broad enough to learn naming conventions, then refine using actual
   station codes, titles, descriptions and formats.
4. Inspect candidate resources. Distinguish measurement files, derived products,
   images, notebooks, service descriptions and live/replay links. Check scientific
   coverage; a familiar station name does not guarantee the requested variable or
   time interval. Offer a small useful selection when there are several candidates.

Each agent search page holds up to 50 datasets. Use the returned `next_offset`
with the same query/publisher/Endpoint, stopping when enough suitable data is found
or pagination ends. Do not call the first page the entire catalog. Use total
counts as metadata, not proof that every resource is accessible. Catalog publishers
are not account groups, and filtering by one does not grant protected access.

Use central discovery for published collections. Use an approved Endpoint's local
catalog for unpublished/local holdings or services. If central search fails,
diagnose its actual error and narrow/retry as appropriate; a local catalog is a
different scope, not a transparent substitute. Don't scan every Endpoint or
download a whole collection just to populate choices.

## Attach only the selected resources

Use actual returned IDs:

A source contains exactly its selected resources, not every resource in the
dataset. If another measurement or README is needed, connect that returned
resource set and use the new connection's source ID. An existing source for the
same dataset may contain a different selection; a missing selected path is not
an upstream availability failure.

```text
connected_data_connect(
  provider="ndp", root=DATASET_ID, label=DATASET_TITLE, mode="read_only",
  configuration={"endpoint_id": CATALOG_ENDPOINT_ID,
                 "resource_ids": [SELECTED_RESOURCE_ID]})
```

`CATALOG_ENDPOINT_ID` comes from the dataset search. It is not necessarily a saved
service connection ID. Public data can work without sign-in. If sign-in is needed,
follow `connect-data` and the saved NDP account's private `login_action`; after the
user returns, recheck status and retry the same connection. An account can be
connected while a particular resource still denies access. Report observed
issuer/role errors without inferring or changing group membership.

Connection starts indexing, not a full download. Wait using the durable task handle
and normal task result tools. Then `connected_data_open(source_id=SOURCE_ID)` lists
approved relative paths (200 per page). Retain attachment `revision`, `linked` and
`folder` when supplied; pass them back on listing/reads so a changed selection
cannot silently substitute a different revision.

The completed index supplies the linked manifest; it has not fetched file bodies.
Keep `linked=true` for this index. Do not switch to `linked=false` until a Download
has completed, and do not pass the linked revision to a downloaded read. To read
through the link, open the selected path
with `connected_data_open(source_id=SOURCE_ID, path=RELATIVE_PATH, ...)`.
Use its immutable `resource_id` with
`workspace_resource_read` or `workspace_resource_inspect`. Linked paths are virtual
references, not shell mounts.

## Materialize and analyze

For Python or shell analysis use
`connected_data_download(source_id=SOURCE_ID, selected_paths=[RELATIVE_PATH])`.
Wait for completion and use the returned materialized path. Do not guess a source
folder path or resubmit an accepted download. NDP originals stay intact; create
separate derivatives in the workspace. A downloaded historical copy is not a
current upstream read after disconnection.

Use the returned downloaded input path directly for reads, even when CLIO stores
it outside the workspace root. Shell `access_paths` requests broader folder
permissions; it is not needed to read these approved inputs and cannot authorize
writes to protected source snapshots. Keep scripts, outputs and temporary work
under the workspace. If selected measurements lack the necessary coverage, inspect
alternative resources in the collection before treating that as a collection-wide
gap. Record exactly which instruments and intervals were examined.

Choose analysis from actual data, not format assumptions:

| Data | Checks before computing |
| --- | --- |
| Time series | Measurement time vs capture time, timezone/epoch encoding, cadence, gaps, duplicates, component names and units. GNSS components may differ in scaling and reference frame. |
| HDF5 / NetCDF / array output | Group/variable names, dimensions, coordinate conventions, units, fill values, chunking and requested subset. Inspect metadata before reading an entire large array. |
| Spatial/station records | Coordinate reference, channel/network/station identifiers, geometry and station epochs. Metadata rows are not waveform or displacement samples. |
| Service or stream response | Actual payload schema, status/control events, measurement timestamps and whether data is replay or current acquisition. See `services-and-streams.md`. |

Use existing installed readers and the relevant analysis/visualization skills;
don't execute downloaded notebooks or deserialize executable objects merely to
read measurements. Preserve input dataset/resource IDs, source revision and content
hashes, query filters, units and transformations with the results. Register useful
reports, tables and figures as artifacts, and visually inspect figures before
calling them reviewed. The user may need only a comparison, not a dashboard.

## Interpret failures

- **No matches:** broaden terms, inspect publisher naming and coverage, then refine.
  Distinguish an empty successful result from a failed search.
- **503 / timeout:** preserve the query and actual error; bounded retry or narrower
  paging can help. Do not report an empty catalog or reconnect the account as a
  generic remedy for a server outage.
- **Sign-in required / 401 / 403:** separate saved account state, destination/issuer
  compatibility and resource/Endpoint authorization. Successful browser SSO alone
  is not the private CLIO grant.
- **Only a preview/service link:** explain what it supplies and follow the service
  route when needed. Do not manufacture a data-file URL from its filename.
- **Partial download or changed revision:** inspect the accepted task's result and
  exact source identity. Keep verified files; resolve the changed input before
  claiming the full selection was analyzed.

Finish with the scientific result, selected collection/coverage and usable output
artifacts. Separate found metadata, obtained bytes and checked analysis in the
evidence; none substitutes for the next.
