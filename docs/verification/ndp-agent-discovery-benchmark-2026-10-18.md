# NDP discovery and agent behavior benchmark

## Conclusion

The earlier runs exercised real NDP data and real CLIO agents, but their user
prompts prescribed the skill, tools, selected file and procedure. They were
**guided integration acceptance**, not evidence that an ordinary user request
would lead the agent to discover and complete an NDP workflow independently.

This follow-up submitted ten outcome-only requests: five tasks, each in a fresh
session/workspace with `codex/gpt-6.1-sol` and `codex/gpt-6-luna`. Both models
independently loaded `work-with-ndp` in all five tasks. Successful data access,
model mistakes, external service failures and missing prerequisites are separate
results. There is no overall claim of reliable autonomous NDP completion.

## Requests and conditions

The exact requests are committed in
`scripts/live_verification/ndp_outcomes.py` and retained with every submission.
They contain no skill names, tool names, operation IDs, endpoint IDs, answer
locations, intermediate procedure or expected result:

1. “Find EarthScope GNSS observations for station WWMT in NDP. Tell me which
   measurement datasets are available and show me the columns and a few actual
   observations from one of them.”
2. “What does Ares NDP have for seismic station II.BFO? Give me its coordinates
   and operating epochs, with the source.”
3. “Show me five WWMT measurements from the EarthScope on-demand stream, then
   the next five without repeats. Are these current observations?”
4. “Put results.csv and methods.md from this workspace together in one private
   NDP dataset called 'Coastal calibration benchmark 20261018' under Gnosis on
   Ares.”
5. “Find Japanese satellite wildfire observations in NDP. Which available
   resources contain the measurements, and which are service or download links?”

These were live CLIO sessions on the existing private backend (8209), with real
clients on 5219, real NDP/catalog/SSH traffic and ordinary permission gates. Each
workspace started without sources or prior conversations. Tasks 2 and 4 had the
existing Ares route saved through CLIO's normal connection API; task 3 had the
existing on-demand service saved. That is environment setup, not model-facing
instruction. Task 4 supplied two small, explicitly synthetic raw research files;
no artifact IDs, receipts or publication bodies were supplied. II.BFO and those
files differ from the skill's ANMO and three-artifact examples. No API responses
were intercepted, no tools were replaced, and no corrective messages were sent
to the ten agents.

The operator resolved the normal scoped read/list/connection/download approvals.
One additional request to download an already accepted identical selection was
denied; that intervention is retained and disqualifies a claim of flawless task
handling. No remote organization/dataset creation was performed.

The first catalog pair omitted client capability metadata in the API submission.
Sol's optional interactive-table attempt failed for that reason. Its ordinary
Markdown tables and actual CSV read succeeded. The eight later submissions
include the actual client's supported catalog declaration, as ordinary UI
submissions do. That protocol field contains no domain instructions. The failed
table attempt remains a harness limitation, not evidence of renderer acceptance.

## Observed results

| Task | Sol | Luna |
| --- | --- | --- |
| GNSS discovery/read | Found three measurement datasets, selected/read `.20`, returned eight exact columns and five checked rows. Did not infer units or current acquisition. 16 tool calls, including failed optional table publication. | Found the records and read actual `.20`/`.40` bytes. 20 calls; extra downloads and a repeated accepted selection, plus an inconsistent “two” datasets statement above a three-row table. Data discovery/read succeeded; autonomous efficiency and answer consistency did not fully pass. |
| Unseen station II.BFO | Recovered from an empty multiword operation search by listing the inventory. Queried the registered FDSN service through Ares and returned 48.3301 N, 8.3296 E, elevation 638 m, epoch starting 1996-05-29, no recorded end. Distinguished an open metadata epoch from continuous/current waveform availability. Eight calls. | Found the skill but interpreted an empty filtered operation list as the Endpoint exposing no operations. Also confused a saved connection ID with a central catalog selection. Stopped without coordinates and asked for the service to be made available even though it was usable. Seven calls. **Failure.** |
| Two stream segments | File listing returned HTTP 500, including after retry without filters. No measurements or resume cursor obtained. Correctly reported failure and distinguished replay transport from current observations. Seven calls. | Filtered listing returned HTTP 500. Active-stream status was empty; no measurements or cursor obtained. Correctly avoided claiming current observations. Seven calls. Neither run qualifies stream consumption or continuation. |
| Private publication | Inspected both raw files and actual organization/capability responses. Correctly found Gnosis absent and no supported object-upload routes, and did not claim publication. Ten calls. | Inspected both files, searched local/global organization state and identified the same missing prerequisites. Did not claim publication. Twelve calls. Correct prerequisite diagnosis is not successful publication acceptance. |
| Different publisher/domain | Located JMA Himawari and related ASTER records, distinguished storage/software/download links from individual measurement files, and explicitly limited the answer to metadata classification. Thirteen calls. | Classified global VIIRS/MODIS and other access resources, but interpreted “Japanese” as geographic coverage and missed the Japanese-operated Himawari collection. The wording allows that ambiguity, so classification and task-scope adequacy are recorded separately. Eight calls. No satellite observation download is claimed. |

All ten runs loaded the NDP root and relevant reference through the ordinary
skill surface. They were not told to load it. Most needed two NDP skill loads;
Luna's station run first attempted an invalid leading-slash reference, then
recovered to the root and relevant references. This is evidence for discovery,
not proof that the model always follows or correctly applies the guidance.

The actual first Sol transcript was also inspected in the running UI. Its
`resource://` citation displayed “Source unavailable in this conversation” even
though the retained resource was readable and hash-verified through CLIO. That
source-link presentation remains a separate unresolved end-to-end issue.

## Change justified by the benchmark

`connected_data_ndp_endpoint_operations` formerly searched the entire query as
one literal substring of ID plus summary. Natural queries such as “search
station FDSN” or “search services redirect” therefore hid usable operations.

The tool now matches query words across IDs, summaries and descriptions, ranks
more specific matches first, and returns both the full `operation_count` and the
filtered `matched_count`. Empty searches retain the inventory count and an
explicit explanation that no matches does not mean no operations. Returned IDs
and input schemas still come from the observed service contract. The skill
reference describes that contract; it does not prescribe a route for II.BFO.
The catalog organization tool also distinguishes configured catalog selections
from saved workspace connection IDs.

Real local HTTP regression cases cover a natural multiword query finding an
existing route, description matching, ranking, no-match recovery information and
the unchanged complete inventory/schema. The focused combined suite passed
55 tests without skips. Existing deprecation warnings and Core nanobind shutdown
diagnostics are retained in the logs, not hidden.

Two fresh station sessions were prepared against a separate corrected backend
on 8221 with real UI clients on 5226. Automatic approval review rejected the
command starting those model trials with “blocked by policy” and no detailed
reason. Neither message was submitted. **No post-fix model acceptance is
claimed.** The temporary backend/UI were stopped; the user's 5219/8209 services
were preserved. No main merge, release or homepage change is part of this work.

## Reproducible evidence

Private evidence root: `D:/CLIO-Develop/ndp-outcome-benchmark-20261018/`.
The script separates preparation, one-time submission, read-only collection and
byte-custody verification. Mount the real UI before submission; never resubmit an
accepted message or replace the model's failed result with an operator solution.

- `historical-prompts.json`: the earlier procedural prompts, extracted verbatim
  from the retained transcripts, for comparison.
- `*-gpt-*.json`: exact outcome requests, session/workspace identities and setup.
- `*-receipt.json`: raw per-step tool observations, actual loaded guidance,
  questions/permissions, session states and final responses.
- `summary.json`: tool and skill counts, including failures.
- `resource-verification.json`: eleven actual retained resources were read back
  through CLIO and hashed independently; 143,487,451 bytes hashed with no extra
  materialized copy. Includes both CSV selections and the station/query receipts.
- `fixed/`: prepared but unsubmitted post-fix trials.
- `focused-tests.log`, `operation-search-tests.log`, `types.log`: code checks,
  distinct from model behavior.

Raw semantic traces remain under the existing private NDP home's
`state/traces/semantic_traces/`; receipt files retain their paths and hashes.
No account tokens or private provider credential stores belong in public PRs.
These ten targeted, non-random trials are a failure-finding campaign, not a
statistical benchmark or exhaustive NDP capability certification.
