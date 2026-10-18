# Organizations, datasets, storage and publication

Use this reference for catalog changes, from registering already hosted data to
publishing selected CLIO artifacts or updating an existing research collection.
`references/worked-examples.md` contains several adaptable examples.

## Resolve intent and scope

Identify the requested destination, organization, collection grouping and audience
from the request and existing project context. One dataset may hold many resources;
independent collections may need separate datasets. An existing collection may
need an update instead. Do not convert every artifact into a dataset, or force
all artifacts into one record regardless of intent.

Reuse `connected_data_status.ndp_endpoints`. Discover the chosen Endpoint's actual
operation IDs, query/path parameters and JSON schemas with
`connected_data_ndp_endpoint_operations`. Use
`connected_data_ndp_endpoint_request` for supported JSON changes. Paths below are
examples of NDP operations, not a promise every deployment implements them.

Central discovery, an Endpoint's local catalog, `pre_ckan` staging, and federation
publication are different destinations. If several writable Endpoints fit, resolve
the intended owner before writing. A similarly named publisher elsewhere is not
the same organization.

## Resolve or create an organization

Request `GET /organization`, using `server="local"` when advertised. Match actual
IDs/names and display titles. If a name filter misses, inspect the list before
deciding the organization is absent; spelling errors do not authorize creation.
Global catalog publishers do not prove a matching local writable organization.

When asked to create an organization, inspect `POST /organization`, check for an
existing match, then use the requested name/title and appropriate scope. A typical
body is `{"name":"coastal-lab","title":"Coastal Lab","description":"..."}`.
Read/list back the returned identity. Creating catalog ownership does not create
an authorization group, add members or grant roles. Role administration requires
an independently supported, explicitly requested workflow.

Reuse private NDP account authorization for protected Endpoints. Anonymous
connections may need normal connection approval for `authentication="ndp"` at the
exact URL/SSH destination. For 401/403, distinguish a signed-out account from an
issuer/audience or role denial; report the actual error rather than retrying login
indefinitely. Use `connect-data` for sign-in, never credentials in tool arguments.

## Decide where resource bytes live

| Input | Action |
| --- | --- |
| Already hosted scientific files/services | Inspect their actual stable resource locations and access requirements, then register them in place if requested. Avoid unnecessary copies. |
| Local selected artifacts | Resolve immutable artifact version IDs, names, sizes and SHA-256. Store the bytes through an approved destination before registering locations. |
| New analysis outputs | Register outputs with `create_artifact`, select the intended versions, then use the local-artifact path. |
| Existing dataset resources | Inspect the current record and resource IDs; retain their identities and unrelated metadata during changes. |

For local artifacts, inspect the Endpoint's storage capabilities and available
buckets. `connected_data_ndp_upload_artifact(endpoint_id, artifact_id, bucket_name,
key_prefix)` requires advertised multipart `POST /s3/objects/{bucket_name}` and
object GET operations. It snapshots the exact version, checks existing bytes before
a retry, uploads when missing, and verifies a read-back. Preserve its verified
receipt and returned `resource` descriptor. It does not create a bucket; generic
JSON requests do not substitute for multipart upload. `POST /s3` catalog
registration, when present, describes an object; it does not upload it.

The tool handles artifacts up to 512 MiB; larger inputs need an approved bulk
transfer workflow. Missing object storage is a capability gap, not a reason to
install it implicitly. Use already approved hosting when suitable, or resolve the
missing destination. Don't create a record pointing at untransferred local files.

Do not use expiring signed URLs, credentials, `file://`, local CLIO preview URLs or
an SSH host's loopback address as shared resource locations. Keep access conditions
with the data. A verified S3 URI is meaningful only with the intended Endpoint's
storage configuration; it does not imply anonymous or federated availability.

## Create a dataset

Before POST, search the destination's local catalog for the intended slug and
organization. `GET /search` uses array-valued terms, for example
`{"server":"local","terms":["coastal-observations-2026"]}`. Inspect exact returned
identities rather than accepting the first text match. An existing record may
mean retry, update, or a genuinely distinct collection; resolve that distinction.

Build the discovered `POST /dataset` body from real resource descriptors:

```json
{
  "name": "coastal-observations-2026",
  "title": "Coastal observations 2026",
  "owner_org": "RESOLVED_ORGANIZATION_ID",
  "notes": "Coverage, variables, units, methods and provenance for this collection.",
  "private": true,
  "resources": [
    {"url": "VERIFIED_STABLE_LOCATION", "name": "observations.nc", "format": "NETCDF"}
  ]
}
```

This is an illustrative shape, not a fixed resource count or required scientific
description. Use the schema and actual contents. The display title and stable
lowercase slug are different fields. `owner_org` is the publisher, not a role.
Include supported tags, license, version and provenance metadata when established
by the research project; do not invent units, licenses or access claims.

Preserve the requested visibility. If new results have no audience specified,
choose private when supported and state that choice in review/result. If the
Endpoint cannot honor it, resolve that before creation. Catalog visibility and
object access controls are separate. Preserve an existing dataset's visibility
unless a change was requested.

`scripts/prepare_dataset.py` assembles this body from any number of selected upload
receipts and/or hosted resource descriptors. It separates provenance from the
request body; it performs no network writes. Use it when assembling resources is
helpful, not as a mandatory step for a small metadata edit.

Submit the intended collection(s), inspect warnings, and retain the **returned**
IDs, names and titles. Some NDP deployments auto-rename conflicting names; never
report the requested slug as the final identity without checking the response.

## Update metadata or resources

Read the exact dataset first. Inspect PATCH/PUT and resource-specific operations.
For adding a resource, prefer an advertised resource-add operation, or merge with
the existing resource array, preserving IDs and unrelated entries. Do not assume
arrays append; they may replace the collection. Replacing an existing file version
also needs an intended storage/version policy; a title change alone is metadata.

Preserve unspecified fields, visibility, resource IDs and supported provenance.
Do not recreate a dataset simply to edit it. If the catalog has no version model,
record the selected content hashes and explicit version metadata without claiming
native version history. Deleting a catalog resource, deleting its stored bytes,
and removing a CLIO connection are different actions; clarify destructive scope.

## Verify, publish and recover

Read the exact record back via an advertised detail route or local search. Compare
organization, final name/title, visibility, requested metadata and resource
identities/locations with the intended result. For stored artifacts, retain each
verified hash/size; for hosted data, report the actual access check performed.
Metadata read-back does not establish that another user's account can read bytes.

Local creation is not federation publication. Inspect the actual semantics of
`POST /dataset/{dataset_id}/publish`: the observed NDP Endpoint advertises **local
catalog to PRE-CKAN**, not immediate global publication. Other deployments may
differ. Use the supported destination and read it back, preserving any returned
publication identity. If central visibility is requested, check central discovery
separately and report staging/propagation state. Don't change audience just to
make private research discoverable.

After a timeout or dropped POST response, read before retrying. Match slug,
organization and resources to avoid duplicate records. Resume partial work from
recorded object/record identities; an uploaded object is not a completed dataset.
Do not delete shared objects as automatic rollback. Report uncertain write state
as uncertain until a read resolves it.

Tell the user the resulting collection, organization, destination, visibility and
verified resources. Link a returned/documented catalog page when available;
otherwise give its stable identity. Keep request schemas and receipts in supporting
details rather than making HTTP operations the user's workflow.

## Register a URL, S3 object, service or topic

Some deployments provide convenience registrations in addition to `POST /dataset`:
`POST /url`, `/s3`, `/services` and `/kafka`. Inspect their schemas and collection
effects before choosing them. A route called “add resource” may create its own
catalog package; it is not necessarily an append operation for an existing dataset.
Use the dataset update procedure when preserving an existing collection matters.

URL/S3 registration describes existing hosted bytes. Service registration describes
an existing callable API, not a service install. The observed `/services` schema
requires `owner_org="services"`; honor a deployment's actual constraint rather
than registering it under an arbitrary research organization. Topic registration
describes the requested Kafka resource; distinguish registration from creating a
broker, starting acquisition, or consuming messages. Do not guess those effects
from the route name. Read back the created/updated record and test the requested
data operation separately from its metadata registration.
