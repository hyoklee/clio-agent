# Responsive composed charts, 19 October 2026

The reported widget is the actual `Around the largest particle burst` chart in
`sess_10e7e9a44ddc`, surface `konza-wind-co2-coverage`, component `aligned`.
Its saved Altair/Vega-Lite definition uses three vertically concatenated,
independently scaled panels, each 120 pixels tall. Altair's default view width
is 300 pixels. The existing renderer fitted only unit/layer charts; it did not
fit compositions. A ResizeObserver alone did not repair that missing path.

## Renderer change

The shared UI renderer now measures Vega's actual bounds, including axes,
legends and inter-panel spacing, and adjusts the compiler's constant plot-size
signals with bounded layout corrections. It covers vertical/horizontal/wrapped
concatenations, nested compositions, facets and repeats. Scientific scale domains,
rows, relative panel sizes and authored encodings are retained. Panels retain a
minimum readable size; a layout that cannot fit can scroll. Discrete step-based
dimensions remain authoritative rather than silently dropping observations.

Ordinary container resizes update the live Vega view rather than re-embedding it.
A component regression retains the same view and an edited parameter through
three container sizes. A fullscreen height-only resize also preserves that live
view and parameter. Inline stacks retain their readable panel heights;
fullscreen stacks use the available chart-height budget. Window height is now
observed explicitly, so height-only changes also trigger layout.

The existing portal transition still re-embeds when entering or leaving
fullscreen. This change does not claim to preserve every authored Vega parameter
across that transition, or provide panel-aware brushing for arbitrary compositions.
No new A2UI property, schema, chart library or agent prompt was added.

## Actual session review

No model rewrite, injected answer diagram or scientific-data replacement was
used. The original chart definition and its 60 rows were rendered in the real
CLIO UI on port 5219. Actual measured widths included approximately 789 pixels
inside a 790-pixel inline host and 1,240 pixels in the normal fullscreen host.
A 700-pixel browser viewport also rendered the chart in its narrower host.
Changing to 1,280 by 900 while fullscreen stayed open grew the chart to 718
pixels high. Changing only width to 1,100 retained that height and all 60 rows.
The default viewport was restored afterward.

Evidence is retained in `D:/CLIO-Develop/chart-composition-20261019/`:

- `original-session.json`: unedited native session export.
- `current-surfaces.json` and `current-reported-chart.json`: actual reconciliation
  state fetched through the read-only session API.
- `live-layout-receipt.json`: final native DOM measurements.
- `konza-responsive-final.png`: actual final fullscreen application screenshot.
- `final-chart-tests.log` and `offline-build.log`: supporting checks.

During development, adding hooks caused a Fast Refresh hook-order error in the
already mounted preview. A clean page reload cleared it; the final review used
that clean load. A diagnostic SVG-download event timed out during these updates
and is not counted as export acceptance. Earlier navigation/loading timeouts are
also not scientific-data acquisition failures or successful export checks.

## Validation boundary

The relevant chart tests passed 75 unique cases, including real Vega layout,
selection, composed charts and component lifecycle checks. The final separate
resize regression also checks fullscreen height-only updates. The offline viewer
build, UI type checking, lint and component-size/reuse/presentation guards passed.
This is renderer regression and actual existing-session review,
not a new Sol/Luna agent-authoring benchmark. Existing four HTML transcript files
were not rewritten, and nothing was committed, merged or released for this fix.
