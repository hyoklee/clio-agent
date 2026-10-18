# Adaptable NDP workflows and runnable helpers

These are independent examples, not a sequence to enact on every request.
Uppercase identifiers in tool examples mean values returned by previous tools.
Discover actual operations and schemas before use. Bundled fixtures are synthetic;
their locations and organizations are not real publication destinations.

## 1. Find scientific data and produce a checked result

Request: “Find EarthScope GNSS data for WWMT, compare the vertical displacement
over the available interval, and make a chart.”

```text
connected_data_status()
connected_data_ndp_organizations(query="earthscope")
connected_data_search_ndp(query="WWMT", organization=PUBLISHER_ID,
                          endpoint_id=CATALOG_ENDPOINT_ID)
```

Inspect actual resources and their coverage. Select the measurement resource,
not its thumbnail or dashboard link; refine/paginate if necessary. Connect the
returned dataset/resource selection using `discovery-and-analysis.md`. Present
private sign-in only if needed. Wait for indexing, list the approved relative
paths, then download the selected file for analysis and wait for its task result.

Inspect time/component encodings, units, gaps and reference conventions. Compute
only what the coverage supports, visually review the chart and register it with a
source/method report. If there are only station metadata or a preview image,
explain the available evidence instead of inventing a displacement series.

## 2. Create an organization, then register already hosted research

Request: “Create Coastal Lab on this Endpoint and catalog our existing NetCDF
observations with their methods document. Keep the dataset private.”

Discover the Endpoint's organization and dataset operations. List local
organizations, reuse an exact existing match if this is a retry, or create the
requested organization and read it back. Inspect the two supplied hosted resource
locations and their metadata. Registration need not copy already hosted bytes.

For a local preparation demonstration, let `SKILL_DIR` be the resolved directory
returned by `load_skill`. Use the available Python executable; these helpers use
only its standard library and do not install dependencies:

```text
python "SKILL_DIR/scripts/prepare_dataset.py" --name coastal-observations-2026 --title "Coastal observations 2026" --organization coastal-lab --resources "SKILL_DIR/examples/hosted-resources.json"
```

This prints a private dataset body with **two** resources and an evidence section
explicitly marking both locations unchecked. The example.org locations are
illustrative. For real work, save inspected real descriptors in a workspace JSON
array and rerun with that input. Submit only the output's `dataset` object after
checking it against the observed Endpoint schema; retain `evidence` locally.
Read the returned dataset back. Do not claim file access or federation publication
from a successfully prepared body or local metadata record.

## 3. Store selected artifacts in a requested collection

Request: “Take these three artifacts and create ‘TO Optimization dataset 1’ in
Gnosis.” This particular request asks for one dataset with three resources. A
request for two independent collections or additions to an existing dataset
requires different grouping; do not generalize this example into a rule.

Resolve the selected artifact versions and existing local organization, including
plausible spelling differences. Discover storage and the chosen existing bucket.
For each selected artifact, call:

```text
connected_data_ndp_upload_artifact(endpoint_id=WRITE_ENDPOINT_ID,
  artifact_id=SELECTED_VERSION_ID, bucket_name=SELECTED_BUCKET,
  key_prefix=PROJECT_PREFIX)
```

Save each returned verified receipt as workspace JSON. The helper can combine any
number of receipts; for this request:

```text
python "SKILL_DIR/scripts/prepare_dataset.py" --name to-optimization-dataset-1 --title "TO Optimization dataset 1" --organization RESOLVED_GNOSIS_ID --receipt result-a.json --receipt result-b.json --receipt result-c.json
```

Check the body and visibility, create the requested collection and read it back.
Keep each artifact/version/hash association with the returned resource identity.
If Gnosis or storage is absent, resolve that missing prerequisite; do not silently
create another organization, install storage or manufacture successful results.

The helper also accepts both `--receipt` and `--resources` for a collection mixing
newly stored outputs and existing hosted material. It prepares **new** records;
use the update procedure for an existing dataset rather than replacing its
resources with a freshly generated body.

## 4. Add a resource and edit metadata without replacing a collection

Request: “Add this revised calibration table to the existing estuary dataset,
keep the original observations, and correct the description.”

Resolve/read the exact record and organization, resource IDs and visibility.
Resolve/store the selected calibration artifact or inspect its stable hosted URL.
Inspect supported resource-add/PATCH operations. Use a resource-specific operation
if available; otherwise prepare a merged array preserving the existing resource
IDs and unrelated fields. Update only the requested metadata. Read the exact
record back and verify the original observations remain along with the added
calibration resource. A lost response means read before retry, not another POST.

If the user instead asks to replace a resource version, establish the intended
identity/version policy; don't silently retain or delete old bytes as a side effect.

## 5. Query station metadata through an SSH Endpoint

Request: “Use the Ares NDP service to find metadata for IU.ANMO.”

Reuse the saved Ares connection; if it has not been saved and the user selected
that host/service, connect the existing service:

```text
connected_data_ndp_endpoint_connect(name="Ares NDP",
  url="http://127.0.0.1:8002", ssh_profile="ares", authentication="none")
connected_data_ndp_endpoint_operations(endpoint_id=SERVICE_CONNECTION_ID,
  query="search")
```

Use the observed local catalog search with `terms=["earthscope"]` and
`server="local"` to discover the actual service identifier. If its service proxy
is advertised, inspect it and request:

```text
connected_data_ndp_endpoint_request(endpoint_id=SERVICE_CONNECTION_ID,
  operation_id=OBSERVED_SERVICE_PROXY_OPERATION,
  parameters={"service_identifier": RETURNED_SERVICE_IDENTIFIER, "path": "query",
              "query": {"net":"IU", "sta":"ANMO", "level":"station", "format":"text"}})
```

Read the captured `resource_id` or inspect its materialized path:

```text
python "SKILL_DIR/scripts/inspect_capture.py" "CAPTURE_WORKSPACE_PATH" --sha256 CAPTURE_SHA256
```

For FDSN station text this reports pipe-delimited columns, actual row count,
missing cells and sample rows. Distinguish station epochs from repeated samples;
this result is metadata, not a waveform read or a new stream producer.

## 6. Sample archived data, inspect and resume

Request: “Show a short sample from this archived CSV stream, then the next segment.”

Discover/select an actual archived file or approved user-supplied URL. Inspect the
on-demand service's segment schema and request a finite segment. Read the captured
data and retain the `done` cursor for the next request. Confirm measurement
identities/timestamps at the boundary; don't count control events as measurements.

The fixture demonstrates parsing without contacting or starting any service:

```text
python "SKILL_DIR/scripts/inspect_capture.py" "SKILL_DIR/examples/replay-segment.sse"
```

Expected: four complete events (`hello`, two `sample`, `done`), no incomplete
event, resume cursor `row:44`, and last event ID `43`. The ID and cursor differ.
The sample timestamps are from 2020: this is archived replay, regardless of when
the capture is made. An incomplete final event is flagged and not counted.

For a genuinely live request, follow the separate producer lifecycle in
`services-and-streams.md`: choose actual station codes/topic, start the requested
session, retain its identity, inspect status, consume output and stop that specific
producer when finished. The finite read channel closing does not stop it.

## Helper interpretation

Both scripts print JSON to stdout and leave inputs unchanged. Redirect to a new
workspace file only when you want to retain the report. Invalid input, hash
mismatch, oversized capture or unverified upload receipts return a nonzero status;
do not submit a partial prepared body. `inspect_capture.py --format` can override
auto detection; `--delimiter` handles known delimited formats. Binary HDF5,
NetCDF, MiniSEED and large files need their proper readers, not this text helper.

Prepared metadata is not a remote mutation; a stored receipt is evidence from the
upload tool, not independent credential verification by the helper. Shape/hash
inspection does not validate scientific units, freshness or another account's
access. Adapt each example to the actual request, selected data and deployment.
