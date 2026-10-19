# NDP conversations: contract repairs and export qualification

This continues the October 18 scientific benchmark. A finished answer, green
tool row, discovered skill or generated screenshot does not qualify a case.
Review includes every turn, tool arguments/results, background transfers,
command exit status **and stderr**, acquired bytes and provenance, independent
calculations, actual rendered views and the exported session itself.

Evidence is retained locally in `D:/CLIO-Develop/ndp-shareable-20261019/`.
Native JSON histories are unedited. Unsuccessful candidates remain in the audit;
they are not removed to produce a clean-looking export. Showcase selection is
not a reliability rate over the benchmark.

## Repairs driven by actual sessions

| Observation | Change | Verification boundary |
| --- | --- | --- |
| Luna passed a saved `ndpep_` service ID to catalog organization discovery, then incorrectly blamed NDP availability. | Active-source status exposes configured `ndp_catalogs`; discovery safely resolves an owned, visible saved service only when its destination/authentication match a configured catalog. Other services receive a specific correction. | Real local HTTP/owner-scope tests and fresh Luna regression below. |
| README-only and measurement selections had the same displayed dataset label. | Status includes the exact approved dataset/catalog/resource selection. It does not imply approval for unselected resources. | Connected-source tests and source review. |
| Index/open used ambiguous linked/downloaded revisions; failed transfers could advertise an older snapshot as their result. | Explicit linked/downloaded references, specific wrong-kind errors, and success-only references tied to the operation's own manifest. | Storage task tests, including a failed transfer with retained older bytes. |
| Resource query parameters vanished when HTTP requests supplied an empty parameter dictionary. Tahoe's ArcGIS download redirect therefore lost required parameters. | Preserve original and redirected query strings; still strip protected Authorization on cross-origin redirects. | Real TCP query/redirect tests and subsequent live NDP GeoJSON acquisition. |
| `uv` used an unwritable Windows child-profile cache. A PowerShell command still returned zero after `uv` failed. | Publish a workspace-local `UV_CACHE_DIR` with the prepared runtime. | Runtime tests and fresh live analysis commands; stderr inspected independently. |
| Alta revised a figure and ZIP, but the ZIP's second version exceeded the eight-promotion cap. A completed tool call contained an explicit rejected item. | Budget distinct artifact identities per turn; reviewed revisions reuse that identity's slot. Distinct additional outputs remain capped. Tool guidance explicitly requires inspecting each batch item's acceptance. | 53 artifact tests pass, including revision-at-cap and prior-turn accounting. Live post-fix qualification is recorded separately below. |
| Candidates 6 and 7 rendered surfaces but definition storage sometimes refused an equivalent Windows path. | A concurrent production-store probe captured `D:\...` versus `\\?\D:\...` for the same managed destination. Resolved containment now normalizes DOS/extended drive and UNC aliases, while retaining distinct drives, shares, sibling paths and device namespaces. Credential/read-only checks use the same comparison. | Retained before/after probe: one refusal before, both concurrent writes succeed after. Boundary and producer regression tests pass. This controlled store probe is not model or rendered acceptance. |
| Candidate 7 Alta promoted a CSV under a friendly extensionless title; the chart validator treated that title as its format and refused the valid table. | Validation and table query/export use the selected immutable version's original file suffix. MIME inference retains explicit published filenames and falls back to the version path for friendly labels. Export stat also handles Windows long paths. | Actual candidate-7 artifact now returns HTTP 200 for table query (25 filtered rows) and CSV export (50 rows). Regression tests cover friendly labels, version selection and actual CAS tampering. |
| The layered historical reference and monthly percentile bands disabled chart box selection. | Select observation coordinates from compatible point/line layers; do not infer arbitrary coordinates from independent panels or conflicting observation fields. | 45 chart/selection tests and type checks pass. The actual Alta departure chart displays a brush rectangle alongside the reference line. Row-selection feedback was not established; drawing the rectangle alone does not qualify that full interaction. |
| Actual artifact-inclusive Tahoe export omitted a consumed TRPA service-metadata input, though its recorded bytes still existed in the managed workspace state store. | Recorded artifact export recognizes that workspace's canonical state root as well as its project/granted roots, handles Windows long paths and still verifies the recorded SHA. It does not expand unregistered-input scope or include another workspace's state. | 38 export checks pass, including retained managed input and refused foreign-state/unapproved paths. The original omission-bearing archive is retained; final native re-export qualification is separate. |

Two later runs exposed contracts beyond the initial exporter fix:

- Luna candidate 12 used a valid source artifact URI in a map, but the live byte
  route refused its managed-input path. Live reads and export now share a
  hash-pinned managed-state resolver. Only the owning workspace's canonical state
  qualifies; provider-custody failures retain precedence and ordinary project
  reference custody is unchanged. Sixty-two focused checks pass. Both actual
  refused artifacts now return HTTP 200 with matching recorded hashes, including
  the original 937,550-byte GeoJSON. Foreign/unapproved paths and tampered bytes
  remain refused (`review/managed-input-live-byte-receipt.json`).
- Sol candidate 11 received three `a2ui_view_stale` failures when capturing an
  otherwise stable Vega chart. The observer now distinguishes identical SVG
  attribute/text assignments from actual changes. Reversions, replacement,
  controls and readiness still invalidate stale captures. Eleven UI checks pass.
  A separately labelled diagnostic follow-up captures the actual displayed
  790×532 chart successfully, SHA
  `c522c62bcd2144c4b125868349fda22e9857e088f1f21bf9e72d3c4f3e9d71ac`
  (`review/capture-regression-receipt.json`). Earlier failures remain in the
  native history; this regression is not a clean scientific showcase.

The canonical NDP skill and its discovery reference explain catalog/service ID
namespaces, approved resource sets, index/download/open semantics and follow-up
references. These are generic workflow contracts; no Alta/Tahoe answer, resource
ID, analysis recipe or benchmark success condition is inserted into main/planning
prompts. NDP tool activation still requires an active NDP source or visible saved
service; a stored account alone does not add the higher-level tools.

## Independent skill reviews

Authenticated Claude Code **Opus `claude-opus-5-5`** and **Fable
`claude-fable-5-1`** reviewed the actual skill/tool source pack without editing
files. Reports are in `review/opus-review.md` and
`review/fable-source-review.md`. Fable's first attempt did not complete its review
and is retained separately. These are source reviews, not live CLIO acceptance.
Findings about ID namespaces, selected-resource visibility, revision kinds and
stale task pointers informed the repairs above. Recommendations were checked
against actual activation and ownership code rather than applied mechanically.

## Fresh Luna contract regression

Session `sess_11c28d2116a4`, `gpt-6-luna`, no seeded datasets:

1. “Which NDP collections contain Alta-Collins snow and liquid-precipitation
   observations, and what time coverage could we compare?”
2. “Are those two collections actually overlapping in time? Please check the
   observation timestamps before deciding how to combine them.”

The first turn discovered the NDP skill and both datasets in five calls without
the saved-Endpoint-ID failure. It nevertheless suggested overlap based on
collection labels. The follow-up acquired the actual CSVs and corrected that:
9,940 historical rows end April 30, 2023; 426 current rows begin October 1, 2023;
there are no shared timestamps. Sixteen calls in total, no failed operation or
command error. This establishes the repaired discovery/acquisition path and an
evidence-based correction. The initial semantic mistake remains a failure of
temporal reasoning, not a general reliable-science pass.

## Provenance and independent calculations

**Alta:** NDP discovers records published by the University of Utah's Hive.
Provider citations to Hive are compatible with NDP acquisition; they do not mean
the agent bypassed NDP. Both original CSVs and their READMEs were selected and
downloaded through CLIO's NDP source path. Historical/current SHA-256:

- `dc83bccd890d1533cc9de27a0ec55ccbad53db1b1689c803530647ad92567a45`
- `511191c3333ce7aa1f24f63d609908699e60f0757f21719387f424fb95fcffcf`

In earlier ratio trials, an independent ordinary-CSV calculation reproduces 10.9117:1 for 2023–24 versus
12.2736:1 for the equal-season historical mean when retaining positive snow/LPE
pairs. A complete November–April window gives 11.2336 versus 12.4770. Including
all recorded nonnegative precipitation gives 10.8078 versus 12.1395. Each ranks
2023–24 fifth lowest among 25 seasons. These describe one site's observations,
not a persistent climate trend or causal attribution. Original quality-control
differences, October gaps and the estimand definition must remain visible.

**Tahoe:** NDP dataset `f8e23062-bc48-4bdd-9698-374bee3712fd`, GeoJSON resource
`6c62c1d6-bce0-4ee1-bd9c-8b55fd3f1eee`, TRPA publisher. Actual downloaded bytes
are CRS84 longitude/latitude despite the original URL's requested projection.
SHA-256 `bf1d07bac1af2b520ba21963b30048f1f8231c8882b86f8923b3f963ca641154`.
Independent WGS84 ellipsoidal measurement reproduces **497.727861 km²** enclosed
area and **123.049623 km** perimeter. A topology-preserving 100 m simplification
gives 496.878991 km² and 112.671601 km. Computational decimals are reproducibility,
not known survey accuracy. The polygon has no island holes, and inspected
metadata does not establish its survey date or reference water level.

`review/verify_science.py` and `review/independent-science-check.json` retain the
independent computation without modifying model-produced analysis.

## Rejected candidates and remaining gaps

- Candidate 4 Alta's green command hid the `uv` cache failure; Konza also hit a
  moved GitHub link and an unavailable search service. They are not clean demos.
- Candidate 5 Alta's science passed independent checks but its revised evidence
  ZIP was explicitly rejected by the artifact promotion cap. The rejection is
  retained; the audit now checks `accepted=false` and partial batch rejections.
- Candidate 5 Tahoe's lake measurement succeeded. Its follow-up asking for land
  within shoreline distances hit two HTTP 404 errors for nearby-water resources.
  It therefore could not supply a complete land mask and is not a clean showcase.
- Candidate 6 Tahoe hit a definition-artifact refusal and a revised-image
  promotion rejection. Its unedited native HTML was used to test the archive
  renderer, not labelled as a successful demo. That inspection also found that
  offline maps attempted remote tiles blocked by the archive CSP; the UI now
  uses a labelled, network-free background while retaining scientific geometry.
- Candidate 7 Alta hit the friendly-title table refusal and a partial artifact
  rejection during recovery. Candidate 7 Tahoe repeated the Windows namespace
  definition refusal. Both remain rejected. Alta's saved chart does render after
  scrolling into view: an offscreen suspension placeholder was initially mistaken
  for a persistence failure; no replay repair was needed.
- Candidate 8 Alta acquired the real measurements and its scientific calculations
  pass independent checks. It nevertheless introduced a Python syntax error while
  editing categorical selector labels with PowerShell, then repaired the script.
  That is retained as a model-authored coding failure and excludes the run from
  failure-free showcase selection. It is not evidence that the repaired NDP
  acquisition or Windows containment contracts failed again.
- Candidate 9 Alta completed the scientific comparison and monthly cutoff
  explorer. Independent recomputation checks all 25 seasonal points, six monthly
  comparisons, six sensitivities and 91 explorer rows, including its explicitly
  documented floating-point boundary tolerance. Its third-turn handoff and Luna
  candidate 10 both then failed native turn finalization: Core `AsyncPutBlob`
  returned code 12 for session event storage. Zero failed tools did not make
  these runs successful. The audit now also checks message `error_info` and
  `stop_reason=error`; both histories remain rejected for complete acceptance.
- A direct native capacity inspection confirmed the private demo store was full:
  536,870,912 total bytes, zero remaining. This was the explicitly bounded custom
  test store, not an NDP refusal. An operator added a separate 2 GiB file target
  with native registration, preserving the original target and recording config
  hashes/backup. Capacity became 2,684,354,560 bytes; a 76,800-byte native
  write/read-back passed. The Core daemon PID remained unchanged across preview
  reload. This is capacity/setup repair, not retroactive acceptance of the two
  interrupted runs, and not a change to automatic growth policy for user stores.
- Candidate 5 Alta's interactive follow-up attempted an undeclared dashboard
  binding and recovered. That model-authored binding error remains in the full
  history; the original turn already had a partial artifact rejection.
- Candidates 11 and 12 finalized normally after the capacity repair. Candidate
  11 had the three capture failures above; candidate 12 had the managed source
  refusal and a corrected Python API mistake. Both remain rejected for clean
  showcase selection, rather than being relabelled successful after recovery.
- Re-auditing **all three turns** of candidate 8 Tahoe found a partial final
  artifact batch: its reproducibility ZIP was accepted, but three companion
  artifacts hit the eight-output retention cap. The package itself reruns and
  the native export has no omitted registered artifact, but those facts do not
  erase the rejected designations. Earlier commentary overstated its clean
  qualification; this full history is also excluded from failure-free selection.
  The tool now advertises its configured limit and returns `promotion_budget`
  (`limit`, `used`, `remaining`) after each batch. The cap is not increased for
  demos. Working scripts can stay ordinary workspace files; requested outputs
  and useful companion packages take priority for artifact designation.
- Candidate 13 acquired the real Alta data, rendered and reviewed its chart, and
  independently matches all 25 seasonal values. Its own exact-decimal check
  initially failed, then passed with a justified numerical tolerance. That failed
  command remains in its history. Candidate 14 Luna completed its first boundary
  question in 26 calls without failure, but its follow-up had an invalid Python
  import, mutually exclusive recall arguments supplied together, and incorrectly
  nested UI components. It recovered and rendered a comparison; this is useful
  capability evidence, not a clean multi-question reliability pass.
- Candidate 15's snowfall question completed 48 calls without failed operations,
  command errors, partial rejections or native turn errors. Independent checks
  reproduce the original 10,366 observations, all 25 seasonal points and three
  comparison summaries. Its monthly follow-up also reproduces all 350 rows across
  two reference cohorts and 25 selectable winters. That follow-up nevertheless
  failed once on unavailable context search and once on a saved-view parent-path
  update; recovery does not make the full conversation failure-free. Monthly
  rank checks explicitly account for the table's four-decimal rounding: every
  source total differs by less than 1e-10 inch, so this removes serialization
  noise rather than changing a meaningful measured difference.
- Candidate 16's first Tahoe question completed 46 calls without a failure or
  partial rejection, including real returned promotion budgets. Its shoreline
  follow-up had the same unavailable context-search failure. Both histories
  remain excluded from failure-free delivery.

Those failures exposed two more shared contracts. The native context store had
no search indexer, but both the recall tool and compaction footer offered text
search. The tool now exposes ID-only recall when search is unavailable, and the
summary footer names that supported mode. Retained steps remain readable; no
indexer is invented or enabled as an unqualified workaround. The dashboard tool
and skill now distinguish whole-model writes to live definitions from exact
declared-path changes in immutable saved viewers. An unbound saved-view refusal
lists the actual available paths. Fifty-five focused context/dashboard checks
pass; these source checks are separate from fresh agent qualification.
- The original wetland/riparian habitat-area request remains unqualified. Earlier
  provider fallback maps and a successful lake-boundary task do not establish
  successful NDP habitat acquisition or basin-wide habitat acreage.
- Protected live streams and private publication are not established by these
  public-file conversations. Earlier authentication/storage gaps remain separate.

## Export qualification

The two three-question Sol 6.1 conversations passed whole-session execution and
independent scientific/reproduction checks. Their native **transcript HTML** and
separate scientific ZIPs are the conversation handoff. Tahoe's additional
artifact-inclusive archive passes; Alta's does not, for the historical input gap
below. No failed call is removed from any history.

| Case | Session | Complete execution | Independent science and portable package |
| --- | --- | --- | --- |
| Alta seasonal and monthly snowfall (17) | `sess_4e74d38f7a9d` | Six messages, 95 completed calls; zero failed operations, command errors, partial rejections, error outputs or native turn errors. | Original hashes and all 10,366 observations, 25 seasonal points, 175 month rows and 14 cohort comparisons checked independently. Separately extracted final ZIP reruns with `python -I -S` from an unrelated directory; all three CSVs match byte-for-byte. |
| Tahoe boundary area and shoreline detail (18) | `sess_9cca40f4085e` | Six messages, 110 completed calls; the same six failure categories are empty. | Original CRS84 polygon, 572 exact grid intersections and all ten resolution/geometry results recomputed independently. The final 27-member package reruns in a separate isolated environment; all numerical/geometry differences are zero and both PNGs are pixel-identical on this Windows host. |

All six user messages select `gpt-6.1-sol`, high reasoning and authorized bypass.
Initial workspaces contain no supplied scientific files or answers, only a saved
anonymous NDP public service. The agents independently load the NDP skill and
the relevant presentation/catalog guidance. The frozen execution code is
`4f53a9461`; later exporter repairs do not rewrite their tool histories.

Exact Alta prompts:

1. “How unusual was the 2023–24 snowfall total at Alta-Collins compared with the historical winters available through NDP? Show the comparison and explain any coverage limits.”
2. “Was that driven by especially snowy months, or was snowfall elevated throughout the winter? Let me explore the monthly comparison.”
3. “Can a colleague reproduce the seasonal and monthly comparisons outside CLIO? Package the source data, results and methods, and check that a clean extracted copy reruns.”

Exact Tahoe prompts:

1. “Can NDP’s Lake Tahoe boundary tell us the lake’s surface area? Make a map and show how you measured it.”
2. “How much does the estimated shoreline length depend on map detail? Show a comparison at several resolutions.”
3. “Can a colleague reproduce both the area and shoreline comparisons outside CLIO? Package the source boundary, results and methods, and check that the files open and the analysis reruns.”

No skill/tool names, artifact IDs, intermediate procedures or answer structures
are supplied in those prompts. These selected cases are not a benchmark success
rate and do not qualify the earlier failed histories or establish Luna reliability.

Receipts: `review/alta17-execution-qualification.json`,
`review/tahoe18-execution-qualification.json`,
`review/contracts17-18-science.json`,
`review/alta17-independent-extraction-receipt.json`,
`review/tahoe18-final-independent-extraction-receipt.json` and
`review/contracts17-18-prompt-preconditions.json`.

Final scientific packages (distinct from the native conversation exports):

- Alta SHA-256: `c523be75de6b95a22fd504cdc99e0350d3808f92fafb320bdee566b92c262416`.
- Tahoe SHA-256: `90aa71a46d024bfda17cfe954dfbf6fafddb8a8ba74e46321ced798ad861f158`.

Native export inspection found two additional historical-input defects. Alta's
automatically registered consumed script had reference-only custody and was
subsequently edited. Its complete original file-read receipt retains exactly
7,932 bytes matching the recorded SHA, so the exporter now uses those exact
bytes with an explicit `recorded_tool_read` receipt. No normalization, partial
assembly, present-day substitution or ledger mutation is allowed. Future small
consumed scripts/granted inputs use the selected store's bounded ingestion;
copy failure and concurrent change retain explicit evidence gaps. A real HTTP
regression opens the original script after editing and deleting its workspace
copy. Eighty focused export/input/cross-workspace checks pass, plus the two new
copy-failure/race cases in the ten-test script suite.

Tahoe exposed an anonymous used edge recorded before image designation. Both
image versions were correctly retained, but the exporter reread the current
workspace path. It now resolves an exact path/hash match to an already selected
owned version, retaining the final hash check. Anonymous uses of one path at
different hashes remain separate archive entries. Forty-five focused export
checks pass, including refusal of a same-hash object recorded at a different path.

The original export refusals and browser wait timeouts are retained as diagnostic
evidence. The first Alta archive had 56 members and 55 valid manifest hashes,
but a later audit found that its earlier exporter silently kept only the last
anonymous hash for a repeated path. It is **not qualified as a complete
artifact-inclusive export**. After correcting that collapse, the exporter
correctly refuses two unavailable earlier hashes of `monthly_surface.json`.
The canonical definition versions exist, but they are different serializations;
they are not reconstructed into claimed original input bytes. The scientific
source files, results, saved views and portable package remain available.

Native transcript HTML uses its documented conversation/review scope, with the
scientific ZIP alongside it. Both final HTMLs contain all six messages, all
95/110 tool records and the actual loaded skills unchanged. Their saved-view
snapshots have no failures. The native export API uses the exact unmodified
visual snapshots and renderer captured by the UI; the server freshly resolves
the authoritative transcript. Export receipts assert equality of messages, tool
records and loaded skills against the original UI-generated archives.

Final transcript HTML SHA-256:

- Alta: `a559b486a93652155e74d6a8afb87b574f819a6ff6f4b5c587288c94646262ba`.
- Tahoe: `04591c1cb4912d4f927d23b36c08872135d1f0ba8ce4bf67cb87f41b84bb0f0a`.

Tahoe's corrected artifact-inclusive native ZIP has 68 members, 67 verified
manifest hashes, all four saved views, no omissions and no snapshot failures.
SHA-256: `85bad8514a36b90c7f4af451c7b3827f79d2b553d816a330f272be9a9a6843f7`.
Its actual Files-tab analysis-ZIP download has SHA
`90aa71a46d024bfda17cfe954dfbf6fafddb8a8ba74e46321ced798ad861f158`,
matching the final independently tested scientific package. The main session ZIP
download-manager handoff remains inconsistently observed; native API delivery
and browser review do not count as a passed download-button test.

Both use UI commit `892a5e0e`, renderer SHA
`83122d983118b0bd1411f3f1a1d96a4787f4c8d4f942063d5f1df919ae9f80a3`,
and export backend `81f485978`. Actual final Alta HTML controls switch the monthly
baseline to 24 earlier winters for November–April (February mean 90.4375, rank 2)
and remove/restore October from charts and the table. Both full seasonal results
and coverage caveats are visible. Single Escape closes the fullscreen viewer.

Actual native image review also found an export-only clipping defect: global
fallback `img{height:auto}` overrode the native renderer's layered sizing rules.
Fallback prose styles now stay within the fallback document/status via CSS
scope, including when native dialogs portal outside the root. Thirty-five
document/export tests pass; Ruff, Pyright and file-size checks pass. Fresh native
exports show the complete Tahoe area and shoreline figures, including their
original caveats. Before/after screenshots are retained, without image editing.

Approved originals are in
`D:/Libraries/Videos/clio_recordings/2026-10-19-ndp-science-sessions/`.
The docs use actual native-export screenshots, not mocked product screens.
Final HTML and archive data, decoded embedded tool outputs and included text
were scanned for credential-like values; no matches were found. This is a
pattern scan, not an exhaustive privacy certification. Complete histories retain
local paths and source metadata. In-app review used local HTTP; `file://` opening
is blocked by that browser and remains untested.

Tahoe's final archive console has no warnings/errors. Alta's actual renderer
emits nonfatal Vega warnings about unioned-domain sort and fill/color settings;
the observed chronological categories and measured values are independently
checked. This is not a warning-free-renderer claim. The separate handoff bundle
includes these limitations and the exact ordinary prompts.

`review/qualify_execution.py` fetches a fresh whole-session export after all three
expected ordinary prompts, requires settled matching native message counts and
terminal tool records, and rejects every audited failure category. Its negative
check correctly refuses candidate 8 solely for the partial final batch. A clean
execution receipt still requires separate independent scientific checks, native
export integrity/completeness checks and actual rendered interaction review.

The latest candidate-8 native export contains 64 ZIP members and 63 verified
manifest file hashes, no omitted registered artifacts and three saved views.
Its embedded renderer matches UI commit `7ec76db5`, SHA
`8271d36fe36e5fccdfb362e4313a113fc71930b73653ee39c3641166d481f0ed`.
Actual local HTTP review shows the saved geometry and expanded chart, working
single-Escape exit and no console warnings/errors. This is renderer/export
evidence for a rejected conversation, not a qualified showcase. The in-app
browser blocks `file://` navigation; direct opening from disk was not validated.

## Focused regression checks

- 80 NDP/storage/runtime tests passed, no skips; source, selection, linked/open,
  task reference, activation and workspace-cache coverage.
- 53 artifact tests passed, no skips, after the distinct-output revision fix.
- 79 A2UI producer/visual-review tests passed, no skips, after the managed-state
  boundary correction. Existing native-binding shutdown diagnostics remain in
  the logs; they are not silently removed.
- 246 combined table validation/query/export, Windows path, source-protection,
  file-policy and A2UI producer tests pass after the namespace/format fixes.
- Hosted CI caught four existing document-MIME compatibility failures caused by
  source-suffix precedence. Explicit published filenames retain their earlier
  MIME priority; friendly labels still resolve from the version path. All 53
  document-rendition/data-reference checks pass after that correction. The
  preview was reloaded with it while every session was idle.
- Ruff, Pyright and the production file-size ratchet passed for the changed code.
- UI renderer `892a5e0e` builds successfully, including labelled offline map
  geometry, the latest artifact response, and layered-chart brush support. Thirteen
  artifact-presentation tests, type checks, lint and the frontend-size guard pass.
  Actual final HTML/export review and its limits are recorded above.

Tests and source reviews support the implementation; they do not replace the
live scientific and exported-UI qualification. No homepage changes, merges or
releases are included in this work.
