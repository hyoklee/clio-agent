# Konza run divergence and chart interaction acceptance

## What happened in the screenshots

These were independent model runs, not a switch between chart libraries.

- `sess_39073472a123`, `gpt-6-luna`: catalog search returned the Konza collection,
  but both connection attempts contained UUIDs that did not match the returned
  resource list. For example, `24d65e21-...` was supplied where the catalog
  returned `94d65e21-...`. CLIO refused the selection locally, before contacting
  NDP. The generic “Choose resources” message obscured that cause. No measurement
  analysis completed in this run.
- `sess_1483f54f8596`, `gpt-6-sol`: used valid resource IDs, read six selected
  resources and produced the evidence report and inline chart. The scientific
  conclusion was limited by missing burn-day overlap in the selected wind and
  CO2 series, not by the earlier resource-ID failure.

The displayed chart is the current `clio.chart.v1` component rendering
Vega-Lite. That original model authored a valid Vega-Lite JSON spec directly.
Altair is another way to author the same spec for the same renderer; it is not
a separate interactive chart system. The rows and spec are retained in
`home/state/workspaces/4bae40ed47fc041aea0f657c/a2ui/konza-burn-observations.json`
under the existing `D:/CLIO-Develop/ndp-live-20261018` runtime.

## Renderer defect and fix

The original custom spec defined its x/y encodings but omitted the separate
component `xField`, `yField` and selection metadata. Those omissions are valid
for a custom spec. The renderer nevertheless depended on those extra properties
to install box selection and had no stable local row identity for this input.
Consequently it rendered the chart without the promised interactions.

The renderer now infers unambiguous encoding fields from authored specs and
supplies stable local row keys when inline data has no unique entity key.
Repeated series names do not identify individual observations. Explicit
selection bindings remain authoritative. Ambiguous independent plots are not
assigned a guessed shared coordinate system.

Default selection feedback highlights point marks without regrouping line
geometry. Brush comparisons tolerate floating-point scale-inversion error at
the endpoints. Hour labels default to horizontal, and the shared grid defaults
are quieter and less dense. Authored axis/opacity settings remain authoritative.
No alternative chart renderer, command allowlist, or source-data rewrite was added.

## Actual browser acceptance on the original result

The original agent-authored chart and all 22 observations were retained. In the
actual UI at port 5219:

1. A native pointer click on the 21:00 upper-tail point selected one row.
   “Reference this” attached **1 selected row of 22**.
2. A native drag around 21:00–23:00 selected six observations.
   “Reference this” attached **6 selected rows of 22**.
3. The expanded reference contained exactly the corresponding median values
   `0.008, 0.023, 0.041` and 95th-percentile values `1.001, 0.191, 0.377`.

Real browser evidence is in `D:/CLIO-Develop/konza-chart-20261018/`:
`actual-box-selection.jpg`, `actual-point-selection.jpg` and
`actual-reference.txt`. Test-only composer attachments were removed without
submitting a message to the original session. Screenshots are actual application
captures, not fixture pages or generated UI mockups.

## Fresh visible model trials

Both trials were started through the actual web composer in the existing Konza
workspace. The source was the existing scientific evidence report, not new
synthetic measurements. This tests chart authoring over an existing result;
it does not repeat discovery or raw-data scientific acceptance.

Exact initial prompt, identical for both models:

> Using konza_burn_2022_evidence.md in this workspace, show how the hourly median and 95th-percentile air-quality readings changed through the burn day. Include an explorable chart and explain what the measurements support.

No skill, tool, renderer, code structure or intermediate procedure was supplied.
Both discovered `present-interactive-analysis` and the chart catalog entry.
Each used two catalog lookups: the catalog root and the chart component schema.

| Session | Initial outcome |
| --- | --- |
| Sol: `sess_e200c02a20aa` | Authored Altair in Python, registered a 22-row artifact and rendered it through `clio.chart.v1` using `dataUri` plus a custom spec. Seventeen calls, including two recovered build-command failures and a failed initial capture while no viewer was ready. |
| Luna: `sess_7db5b493705f` | Chose the current trajectories preset with 22 inline observations. Five calls. The real view has point/box selection controls, but its initial linear scale compresses the median. |

Exact review follow-up, identical for both:

> Review the chart’s appearance now that it is visible, and improve anything that makes the readings difficult to compare.

Sol captured the actual chart, revised labels/grid/ticks in place, and captured
the revised result. All eight review calls completed. Its chart retained all
22 observations; a native pointer click and Reference this selected one row.

Luna captured the actual chart and correctly diagnosed the compressed median,
but sent incomplete component replacements without their data source. Three
revisions were refused. It correctly reported that the comparison had not improved.

The component-update tool's existing full-replacement semantics are now stated
explicitly, and a validation refusal explains that unchanged required properties
such as `data`/`dataUri` must be retained. Validation is not weakened and refused
revisions leave the previous surface intact.

After the idle backend was restarted with that feedback, Luna received only:

> Please try improving the comparison again.

Two further replacements failed; a title-only replacement succeeded, but the
comparison remained linear. Luna again reported the remaining limitation.
This is **not** successful weak-model visual-revision acceptance. The clearer
contract and error hint do not establish dependable recovery. Evidence includes
`luna-review-limitation.jpg`, `luna-final-ui.txt` and the session's retained traces.
Sol's actual revised chart is in `sol-reviewed-chart.jpg`.

Several simultaneous browser tabs temporarily left new views waiting for
history and component loading. Closing redundant agent-created inspection tabs
released those requests. The observed stall is retained as an environment
limitation; its transport cause is not claimed as established or fixed here.

## Checks and scope

The chart suite passed 216 cases, followed by all 26 component cases after adding
one more repeated-entity regression: 217 unique passing chart cases. Backend
NDP source/catalog checks pass 26 cases; producer and replacement-guidance checks
pass 65. Ruff, Pyright, TypeScript and the UI workspace's full lint/ownership
guards pass. Logs are in the same evidence directory. Existing test-only
deprecation/nanobind shutdown warnings remain.

The running preview uses the renderer fix, resource-ID diagnosis and replacement
feedback. Existing sessions, sources and NDP credentials are retained. No merge,
release, homepage edit or production publication was performed.
