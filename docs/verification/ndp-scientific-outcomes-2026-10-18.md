# NDP scientific outcomes and Endpoint investigation — 2026-10-18

This extends the earlier discovery benchmark with scientific questions outside
EarthScope, actual measurement analysis, remote Endpoint diagnostics and real
organization-creation attempts. Skill discovery, an accurate prerequisite
diagnosis and completed scientific analysis are scored separately.

## Method and exact requests

Six fresh CLIO sessions received three ordinary requests across Codex Sol and
Luna, submitted unchanged through the actual web composer at port 5219. No skill
names, resource IDs, API operations, answer scripts or intermediate procedures
were supplied in those requests. Fresh workspaces had the existing shared NDP
account, with no attached data or precomputed answers. Normal operation approvals
were reviewed individually. Source queries and tool observations were real;
network responses were not intercepted or replaced.

The evaluator criteria were frozen with the requests in
`D:/CLIO-Develop/ndp-science-20261018/trial-manifest.json` before submission.

**Alta:** “Has the snow-to-liquid ratio at Alta-Collins changed in the 2023–24
winter compared with its historical record? I think NDP has the observations.
Please investigate and show the evidence, with a chart and the limitations of
the comparison.”

**Konza:** “Can the NDP observations from the 2022 Konza Prairie burn tell us
whether the smoke or CO2 signal changed with the wind? Investigate what the
measurements actually support and show me an evidence-based result.”

**Tahoe:** “What can NDP tell us about how much of the Lake Tahoe basin is
wetland or riparian habitat, and how that relates spatially to the lake? Use the
available scientific data to make a small map and quantify what you can, with
clear caveats.”

Two additional fresh Luna sessions used the **identical Alta request**, first
after search/attachment guidance changes and then after clarifying approved
downloaded read paths. They are development follow-ups, not additional untouched
baseline cases or evidence of general reliability. Loaded skill contents and
hashes are retained in the real semantic traces.

Environment limitation: the unrelated local web-search/SearXNG backend was not
available. Catalog requests still worked. This affects the interpretation of
fallback-search failures and is retained in the observations. A renderer needs
a mounted client viewer for pixel capture; the Konza client was navigated away
before its final capture attempt, which limits that visual-review result.

## Baseline outcomes

| Case | Sol | Luna |
| --- | --- | --- |
| Alta comparison | Found both collections, read real CSVs and documentation, calculated 25 seasonal ratios, registered a derived table and produced an actual A2UI chart. Independent recomputation agrees with every output row. | Two long AND queries returned zero matches; it did not broaden sufficiently and stopped without observations. Discovery failure, despite available data. |
| Konza burn | Obtained six resources and analyzed primitive instrument records plus NDJSON. Produced a report and an inline sensor chart. Found no burn-day overlap in its selected wind/CO₂ files. Useful coverage audit, **not** a completed wind-dependence analysis or an exhaustive search of alternative instruments. | Found the collection but supplied invalid resource IDs twice, then attributed the rejected selection to access failure. No measurement analysis. |
| Tahoe habitat | Recovered from stale catalog download links through the provider's actual ArcGIS service; inspected layers, queried class areas and created a real map. Inspected its image, shortened clipped source text and recaptured. Useful proxy map/area ledger; **not** a dissolved unique wetland/riparian inventory. | Found a wetlands collection and connected/indexed it, then attempted to open an unlinked source. Stopped instead of using the approved download path. No map or area analysis. |

Live sessions remain inspectable in the test client:

- [Alta Sol](http://127.0.0.1:5219/workspaces/ws_4eee216d0c9d/sessions/sess_84f53b10e288)
- [Alta Luna](http://127.0.0.1:5219/workspaces/ws_9da079ff1be6/sessions/sess_0aaa6bb6bb25)
- [Konza Sol](http://127.0.0.1:5219/workspaces/ws_aae9ad0fee44/sessions/sess_1483f54f8596)
- [Konza Luna](http://127.0.0.1:5219/workspaces/ws_80da4d323ebb/sessions/sess_39073472a123)
- [Tahoe Sol](http://127.0.0.1:5219/workspaces/ws_b29f58eb1e50/sessions/sess_06dfcfd53df8)
- [Tahoe Luna](http://127.0.0.1:5219/workspaces/ws_4ee61cc8af3d/sessions/sess_010b3490e31e)

## Independently checked Alta result

The two original CSVs contain **10,366 observations, zero duplicate timestamps,
and 25 seasons**. Using the model's stated rule of paired positive 12-hour snow
and liquid observations, the 2023–24 ratio is `635.5 / 58.24 = 10.9117445055`,
versus the mean of historical seasonal ratios `12.2735606447`. The recent season
is fifth-lowest of the 25. This is a single-season comparison, not proof of a
climate trend; season coverage, quality control and early measurement methods
remain material qualifications.

Independent code read the original immutable input copies and recomputed all 25
rows. Maximum absolute difference from the agent's output is approximately
`1.1e-14`. Input hashes, counts and method are retained in
`alta-independent-verification.json` and `verify_alta.py`. The real rendered chart
and actual client screenshot were inspected; neither is a fixture or an
operator-authored answer chart.

## Follow-up failures and corrections

The Konza audit was independently checked against the original downloaded bytes:
138,807 LI-840A and 143,369 wind records, zero April 15 records in either selected
instrument file, and 212,045 W038 concentration messages. An independent primitive
reader rejects global constructors/persistent references. All burn-day hourly
counts, medians and 95th percentiles agree with the report; units remain
unspecified. `konza-independent-verification.json` retains those results. This
confirms the selected-input audit, not collection-wide absence or a wind effect.

The first fresh Luna follow-up discovered both collections with the unchanged
question, downloaded them and read the documentation. It then requested shell
`access_paths` for protected downloaded snapshots. That field asks for broader
folder permissions; the write-access guard correctly rejected the request.
The model incorrectly treated that as an inability to read the approved inputs
and stopped. This was **not** a completed comparison.

Corrections clarify AND search terms, broadening zero matches, indexing versus
Link/Download, `linked=false` after Download, and reading approved downloaded
paths without requesting broader write access. The source write fence is not
relaxed. Final follow-up observations are retained separately, including failures.

The final fresh Luna follow-up completed the numerical comparison and an actual
rendered/captured A2UI chart. Independent verification matches all **25 plotted
values** to the rounded original-data calculation. Its all-period seasonal ratio
is `635.5 / 58.80 = 10.8078231293`, versus historical mean `12.1395466233`.
This differs legitimately from Sol's paired-positive-period estimand above.
The final prose contains an unresolved self-correction about season labels, and
the chart uses year labels formatted as numbers with commas. Numerical completion
does not establish consistently polished presentation or general reliability.

- [First fresh follow-up](http://127.0.0.1:5219/workspaces/ws_4c1f2c3af064/sessions/sess_68677a4cffe8)
- [Final fresh follow-up](http://127.0.0.1:5219/workspaces/ws_5864c27f6197/sessions/sess_3511cbaf2a25)

## Tahoe map and assessment

The agent discovered the provider's `DataDownloader_SoilsandHydro/MapServer`,
queried its actual layers and produced `tahoe_sez_map.png`. Its source renders
TRPA's layer polygons rather than drawing an invented shoreline. The model
inspected the initial image, revised clipped source labels, rendered again and
inspected the revised image before registering the artifact. The final image was
also inspected independently in this investigation.

The map reports approximately **43.4 km²** for selected wet/riverine classes,
**102.4 km²** including forested stream-environment zones, **1,329.7 km²** of basin
watershed layer area and **498.1 km²** for the lake polygon. These are **layer
sums**, not a dissolved unique habitat footprint. Forested stream environments
are a broad proxy and classes can overlap. A basin-wide unique wetland percentage
remains unverified; the figure and result must preserve those qualifications.

The map is retained as a scientific output, not as evidence that every NDP
GeoJSON resource downloaded successfully. The agent's recovery through the
provider service and its unresolved original-link failures remain in the trace.

## Raw Endpoint and stream findings

These are operator diagnostics through real CLIO destinations and direct
credential-safe inspection, **not** independent agent benchmark passes.

1. **Ares:** verified existing Endpoint, CKAN and Kafka services. Readiness reports
   catalog and Kafka healthy, MinIO disabled. Its deployed identity adapter uses
   the old production `/temp/information` endpoint, while CLIO's saved account
   uses the test realm and current `/api/information` contract. No identity issuer,
   membership requirement or server authentication policy was changed.
2. **Replay listing:** `/data/csv-files` returns HTTP 500. Its precise server-side
   exception could not be inspected: SSH to the hosted stream machine timed out.
   Do not claim an unverified filesystem/configuration cause.
3. **Replay transport:** using a real catalog CSV URL, CLIO captured three records,
   then used the completion event's `resume` value as the next request's `cursor`
   to capture the next two. Hashes match the actual saved bytes, timestamps are
   consecutive and unique, and the service reports no active readers afterward.
   Times are **2024-12-03 00:00:00–00:00:04 UTC**, so this is archived replay.
   Captures total 911 and 706 bytes with five/four SSE events, including control
   events. A broken listing does not establish a broken URL replay operation.
4. **Protected live bridge:** anonymous station sampling returns 401; reusing the
   saved account at that reviewed destination succeeds. Session listing succeeds.
   Starting a test bridge fails with upstream HTTP 400 and the actual nested
   reason: `Error creating dataset: Authentication failed: 502: Authentication
   service is experiencing internal issues.` This is downstream catalog/identity
   failure after bridge authentication, not proof of unavailable stations. No
   successful producer start or live measurement consumption is claimed.
5. **Organization creation:** submitted actual `POST /organization` requests for
   the uniquely named test organization `clio-science-test-20261018` to Ares and
   the hosted demo Endpoint. Both returned upstream 401. The current test account
   reports its default realm role and no group memberships. No organization was
   created. A grant/identity repair requires the appropriate NDP operator; using
   an Endpoint's development token or disabling its checks is not an alternative.
6. **Storage/publication:** Ares advertises no S3 object upload routes while its
   MinIO feature is disabled. No live artifact upload, private dataset creation,
   file read-back or federation publication passed. Existing local HTTP upload
   regression tests do not fill this live acceptance gap.

CLIO previously discarded the body of upstream HTTP errors, hiding the nested
bridge failure. The fix retains bounded actionable diagnostics, HTTP status and
private-bearer redaction, while still rejecting redirects and auth denials. Real
TCP tests cover the nested failure, large/silent error bodies and redaction.
The revised production owner was also exercised against the real bridge:
`live-diagnostic-fix-verification.json` retains the readable nested HTTP 400 cause
and empty session lists before/after. This operator check does not constitute a
fresh autonomous agent stream run.
After all eight sessions settled, the reused test backend was restarted with the
fix. Health is ready, the saved NDP account remains authenticated, completed
sessions persist, and its served request route now returns the nested bridge
cause (`served-diagnostic-verification.json`). UI 5219 and docs preview 4391
remain available. No unrelated active session was interrupted.

## Documentation and retained evidence

Documentation adds stream lifecycle, finite capture/resume, freshness and layered
failure diagnosis, plus a bank of scientific questions across snow, fire, habitat,
hydrology and sharing derived results. Multi-winter lake displacement is explicitly
a coverage/feasibility question until suitable GNSS and independent hydrological
measurements are established. The homepage is unchanged.

Private evidence root: `D:/CLIO-Develop/ndp-science-20261018/`:

- `trial-manifest.json`: original requests and frozen criteria.
- `receipts.json`: real messages, tool arguments/observations, permissions and
  loaded skill contents for baseline and follow-up sessions.
- `alta-independent-verification.json`, `verify_alta.py`: independent computation.
- `konza-independent-verification.json`, `verify_konza.py`: independently checked
  instrument coverage and burn-day concentration summaries.
- `replay-verification.json`: actual SSE contents and saved-byte verification.
- `bridge-start-raw.json`: redacted actual nested start failure.
- `ares-organization-create.json`, `ndp-organization-create.json`: real denials.
- `actual-alta-ui.jpg`, `actual-alta-chart-ui.jpg`, `stream-docs.jpg`,
  `science-question-bank.jpg`: actual client/docs screenshots.
- Original semantic traces remain in the reused private CLIO home's
  `state/traces/semantic_traces/`, with the session IDs above.

The existing private runtime/home and UI dependencies were reused. Original
measurements and small analysis/evidence files are retained for inspection; no
new Core installation, Endpoint installation, release or main merge is included.

## Local verification

- 37 Endpoint/agent-workflow/connected-data tests passed, including two new real
  TCP error-diagnostic cases; 28 source/upload tests passed; 31 Endpoint-workflow,
  skill-helper and catalog-page tests passed; 17 shell-server tests passed.
  **113 focused regression checks**, no skips. These do not replace the live
  scientific outcomes above.
- Ruff and Pyright passed for changed production modules. The site check reports
  zero errors/warnings, and its 96-page build passes internal link validation.
- Actual CLIO UI/chart images and rendered documentation were inspected. No
  fixture UI is presented as real-agent acceptance.
