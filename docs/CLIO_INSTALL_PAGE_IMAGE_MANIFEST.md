# CLIO website capture plan

The public website uses the current capture set documented in
[the capture README](../site/src/assets/captures/README.md) and its checksum
manifest. The former screenshot plan is superseded by this one.

## Current set, 10 October 2026

| View | Website placement | Framing |
| --- | --- | --- |
| Dashboard | Homepage default tab and dashboard guide | Full report: charts, map, legends and all five station rows. |
| Files | Homepage Files tab | Complete findings, limitations and source filenames, with the file toolbar. |
| Evidence | Homepage Evidence tab and evidence guide | All six registered files, with the full-details navigation. |
| Artifact lineage | Dedicated homepage section and evidence guide | Complete branching graph, selected result, readable names and controls. |

All four use fictional bike-station data, published through production tools.
Captions identify the authored walkthrough and state that it is not a model run.
Development screenshots do not imply that a release contains the pictured UI.
The evidence guide describes Data and Work, full-details tabs, human-readable
tool results, failure semantics, and artifact lineage.

## Capture rules

- Never use private research data, private transcripts, credentials or personal
  account details. Do not import private sessions into the capture service.
- Default to light mode and retain the real product controls.
- Choose the viewport for the largest result before capturing. Preserve axes,
  legends, source filenames, full graph branches and explanatory limitations.
- Keep the left navigation only when it helps explain workspace navigation.
  Artifact and dashboard detail shots can maximize the canvas.
- Do not publish a clipped, blurry, unfinished or obsolete capture. Check the
  source image and its embedded website rendering on desktop and mobile.
- Keep outcomes truthful, including failures when they are the subject of a
  walkthrough. Technical details belong behind disclosure; do not hide errors
  to imply that a failed run succeeded.
- Preserve untouched originals, source revisions and SHA-256 checksums in a
  dated archive. Remove temporary services, copied state and browser profiles
  after qualification.

## Observability acceptance

Use the UI's clearly labelled synthetic test fixture for deterministic layout
checks. The current case includes a main agent, four child agents, twelve tool
calls and a recorded failure. Check overview fit, agent expansion, correct bar
ratios, row/connector alignment, named filters, keyboard navigation, conversation
opening, and resizing. This is renderer acceptance, not a live model run.

Future public execution walkthroughs should record a real model run on fictional
or public data and retain its transcript and source versions. Do not present a
test fixture as such a run.
