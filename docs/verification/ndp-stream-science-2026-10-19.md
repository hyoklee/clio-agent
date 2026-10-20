# NDP stream science: provenance and agent ownership

## Corrected claim

The screenshot's response to “Can I inspect a short segment in the stream
interface, pause it, and continue without repeating observations?” supplied
manual Attach-menu instructions and a long cursor. That follow-up read prior
results; it did not perform a new UI pause/resume check.

The underlying 30- and 10-record captures are genuine returned bytes from
`https://vdc-192.chpc.utah.edu/api-stream`, operation
`GET /stream/segment/url`. Their recorded hashes match the retained SSE files,
and their 40 timestamp values are unique and consecutive. The operation reads a
remote CSV and emits its rows. It is separate from Ares Kafka and current GNSS
acquisition. These facts verify transport/continuation, not the origin or
physical meaning of the CSV's values.

The source directory's published pull manifest links AGMT to catalog dataset
`a446495f-e6fe-4b14-abd3-0925eecfc2f3`, but does not establish the instrument
acquisition chain, physical units, processing or reference frame. The absence of
those checks is not proof that the data was fabricated. It does mean the previous
description of it as verified real GNSS observations exceeded the evidence.

## Generic guidance change

The built-in skill now distinguishes measured, derived, simulated and
provenance-unverified data before interpreting the physical phenomenon. It
requires the agent to perform acquisition and analysis itself, retain cursors
internally, inspect the actual historical-query/retention contract, and distinguish
unavailable history from history whose availability could not be checked.

A source's preprocessing can be valid if its documented meaning and transformations
support the question. A filename containing “raw,” a familiar publisher, transport
success or a plot does not establish authenticity. No provider, station, URL,
benchmark answer, or prescribed model tool sequence is introduced by this change.

The public stream guide follows the same scientist-led request. The old unverified
CSV plot and procedure-heavy prompts have been removed from the scientific
walkthrough. Original evidence is retained; no conversation was rewritten.

## Trial 1: ordinary question in the existing workspace

- Model: `codex/gpt-6.1-sol`.
- Session: `sess_c3b48aaa2707`; existing workspace `ws_87d8340e8e3e`.
- Exact prompt: “What does the connected stream actually tell us about recent
  ground movement, and can you compare it with the available historical record?
  Show the evidence.”
- No URLs, skill names, tool steps, response structure or expected answer supplied.
- Trace confirms the actual updated main skill and scientific-stream, service
  and discovery references were loaded. The model acquired the matching catalog
  export, checked timestamp coverage and replay equality, and refused to claim
  current ground displacement or stability.
- This is **partial behavior improvement, not scientific acceptance**. It still
  called unverified values observations/measurements and made a numerical chart
  and trend comparison prominent in the physical-science answer. The generic
  provenance gate was clarified after reviewing the actual complete answer.
- The API-submitted message also lacked the web client's widget capability
  declaration. `create_a2ui_surface` failed; the model produced an inspected PNG
  instead. That harness limitation and failure remain in the original history.

The retained transcript and loaded skill hashes are in
`D:/CLIO-Develop/ndp-stream-science-20261019/agent-trial-transcript.json`.
This trial inherited previous workspace files and is not an independent clean
workspace trial. It is not a collaborator showcase.

## Trial 2: clean workspace, question submitted through the real web client

- Workspace: `ws_8a5cdc46f625`, initially empty project directory.
- Session: `sess_ca804359f186`, `codex/gpt-6.1-sol`.
- Approved existing service destinations were connected through the ordinary API;
  no prior answer, analysis data, expected diagram or processing script was seeded.
- Exact prompt, submitted through the actual web UI: “Can NDP tell us about recent ground movement at station
  AGMT, compared with its past record? Show the evidence.”
- Completed at 23:40 UTC: 42 tool calls, including three failed operations. The
  actual client advertised its widget capabilities and rendered a coverage table.
- The trace loaded the revised main skill (`ad97fd76819adc21552740d71adac209b391555451346cf6cfb96d63a6d3e1ce`)
  and scientific reference (`59e204f4b4b4fbff113b0f3c05e255aa6e8db6109213f6b243a757d9816bc4eb`).
- The agent found and downloaded two catalog archives itself, scanned all 858,783
  and 859,949 rows, and established December 3–12, 2024 coverage. It explicitly
  separated those identifiers from the current station-discovery identifier and
  declined to plot unverified values as physical ground displacement. It gave no
  Attach-menu, copied-URL or cursor handoff to the user.
- The CSV file listing returned HTTP 500. Its initial bridge-start request omitted
  a required dataset identifier and received HTTP 400. The corrected request
  failed during dataset creation with an upstream authentication HTTP 502. A
  subsequent bridge-session listing returned `[]`; no producer remained running.
- The final answer distinguishes unavailable captured recent samples from proof
  that no recent data exists, and explains the unresolved units, reference frame,
  processing and product compatibility. This is improved agent behavior and a
  verified archive-coverage result, **not successful recent-motion analysis or a
  replacement collaborator showcase**. One fresh Sol trial does not establish
  general reliability or Luna behavior.

The complete transcript, exact prompt receipt and untouched UI screenshot are in
`D:/CLIO-Develop/ndp-stream-science-20261019/` under `fresh-agent-trial*`.

## Checks

- 80 existing NDP helper, skill runtime and Endpoint workflow tests pass.
- Site unit tests: 39 pass. Static build: 96 pages, all internal links valid.
- Four NDP browser cases pass at 390/1440 pixels in Light/Dark, including removal
  of the unqualified plot and correct documentation media references.
- These support packaging and rendering. Fresh agent behavior and scientific
  completion are assessed separately above.
