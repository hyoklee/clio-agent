# Alta chart sizing, interaction and NDP provenance

The actual result is in workspace `ws_5864c27f6197`, session
`sess_3511cbaf2a25`, surface `alta-cln-snow-liquid-ratio` at the existing
port-5219 preview. This is a retained real-data CLIO conversation, not a fixture.

## Renderer findings

The original Luna-authored current `clio.chart.v1` component had component
height 360 but a fixed 600-by-300 Vega-Lite specification. The renderer preserved
those dimensions even when the viewer expanded, leaving unused space to the
right and bottom. Single-view and layered charts now fit the measured viewer
width and component height, including full screen. Independent compositions
retain their authored per-view geometry.

The shared numeric format added thousands separators to quantitative year
labels. The default now uses rounded numbers without grouping; authored formats
still win. Axis text is larger, continuous scales have room for endpoint marks,
and bounded labels avoid clipping at the viewer edge.

Full-screen autofocus previously selected the first toolbar button, opening
its tooltip. Escape dismissed the tooltip before the dialog. Opening now focuses
the dialog itself. Nested menus keep their own normal dismissal behaviour.

The constant historical-mean rule also prevented coordinate inference for the
data layers. Constant reference rules no longer disable observation selection.
Enabling the controls exposed another renderer defect: a root zoom parameter
expanded once per layer and generated duplicate signals. The zoom parameter now
belongs to one ordinary data layer, which binds the shared scales once.
Headless real-Vega checks exercise rendering, zoom and reset on this composition.

## Actual browser acceptance

On the original result, with all 25 seasonal observations retained:

- A native click on the 2024 point attached **1 selected row of 25**;
  the hover showed year 2024 and ratio 10.81.
- A native rectangle drag over winters ending 2000 through 2004 attached
  **5 selected rows of 25**. The expanded reference contained exactly
  2000/12.95, 2001/13.54, 2002/12.64, 2003/12.64 and 2004/14.66,
  with stable row keys 0 through 4.
- One Escape closed the full-screen viewer, including after chart interaction.
- Inline and full-screen results were visually inspected. Test attachments
  were removed without submitting them, and the test selection was cleared.

Real screenshots and reference text are retained under
`D:/CLIO-Develop/konza-chart-20261018/`: `alta-inline.jpg`,
`alta-full-screen.jpg` and `alta-selected-reference.txt`.

## Ordinary model follow-up

The visible Luna session received exactly:

> Improve the existing seasonal comparison chart’s readability and use of space, while preserving the measurements and scientific conclusions.

No tool, skill, renderer, axis setting or replacement procedure was supplied.
It completed six calls: review skill, surface inspection, chart catalog lookup,
component replacement, inspection and a post-revision capture. The replacement
succeeded on the first attempt, retained the 25 values and historical mean,
and chose a more useful vertical domain (9.5 through 15.5) instead of leaving
most of the plot below the observations. The current renderer still controls
the viewport size regardless of its newly authored 740-by-360 dimensions.

This is one successful revision, not a broad reliability benchmark. The
earlier Konza Luna revision failures remain failures. This follow-up has a
post-revision capture; it does not establish a complete pre/post image-review
loop by the model. Codex separately inspected and interacted with the actual
result as recorded above.

## NDP discovery and original publisher

The original tool records establish the following path:

1. `connected_data_search_ndp` found both datasets in the NDP catalog under
   organization `marriott_library_hive`.
2. The agent linked their selected CSV and README resources as provider `ndp`
   and read/downloaded the selected files through CLIO connected sources.
3. The analysis ran on those local materialized CSVs. Its source links cite
   the original published dataset DOIs, not another independently searched
   replacement dataset.

NDP is the discovery/linking layer here; the dataset publisher is The Hive.
An upstream publisher citation does not mean NDP was bypassed.

| Dataset | NDP ID | DOI | CSV rows | SHA-256 |
| --- | --- | --- | ---: | --- |
| Alta-Collins 2000–2023 | `eb9652c3-6825-4cfa-93ad-31a4cff0607c` | `10.7278/S50d-nsy5-8bje` | 9,940 | `dc83bccd890d1533cc9de27a0ec55ccbad53db1b1689c803530647ad92567a45` |
| Alta-Collins 2023–2024 | `16bee949-c829-4038-a316-204a5322b7d8` | `10.7278/S5d-dx7x-d8ay` | 426 | `511191c3333ce7aa1f24f63d609908699e60f0757f21719387f424fb95fcffcf` |

`audit_alta.py` independently recomputes all 25 plotted seasonal ratios from
those exact retained CSV bytes using decimal sums. **Every plotted value
matches.** It writes `alta-provenance.json` and the actual revised component
definition in the same evidence directory. It exports no account credentials.
This audit rechecks retained downloads; it does not claim fresh upstream
download acceptance or statistical validation of a climate trend.

## Checks and scope

184 chart, full-screen and diagram regression cases pass. TypeScript and full
workspace lint/ownership guards pass. Tests use real Vega compilation and
rendering, including fixed/container widths, endpoint margins, integer year
labels, constant-rule layering, scale zoom/reset and full-screen autofocus.
The pure loader/tooltip security tests moved from the oversized chart component
test file to the embed test file; assertions were preserved.

No merge, release or homepage change was made.
