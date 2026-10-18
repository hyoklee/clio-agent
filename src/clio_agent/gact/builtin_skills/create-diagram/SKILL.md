---
name: create-diagram
title: Create Diagram
description: Choose, compose and review diagrams from a person's material. Mermaid's component entry supplies the complete supported-family inventory, syntax and examples; this skill covers the authoring workflow.
---

Start with the relationships the reader needs to understand. A protocol has
participants and ordered messages; an ER model has entities and cardinalities;
a lifecycle has states and transitions; commit history has ancestry; a grammar
has accepted token sequences; a hierarchy has containment. Choose the notation
that preserves that meaning. A diagram is optional: prose, a table or a list
can answer better. Do not turn every subject into a flowchart or reproduce a
fixed dashboard layout.

## One authority for the component

The active A2UI catalog's **`clio.mermaid.v1` entry** contains the complete
supported-family inventory, syntax, runnable examples, notation variants and
CLIO viewer behaviour. Load its exact schema in the same batch as any needed
layout components:

```text
load_skill("a2ui-catalog-clio-workspace", files=[
  "catalog.json#/components/clio.mermaid.v1",
  "catalog.json#/components/Column"
])
```

Use the catalog skill actually declared for this session; the example names
CLIO's workspace catalog. The returned `x-clio-authoring` is guidance, not a
property to copy into a component payload. It covers all supported families,
not only flowcharts/sequences. Choose the relevant family and use its syntax;
there is no requirement to render every family. No additional syntax reference
from this skill is needed. Mermaid remains the source language and component
name; the bundled rendering library is an implementation detail.

For a short explanation, a `mermaid` fenced block uses the same source language.
For a composed saved report, `create-dashboard` covers publication and revision.
The catalog is the authority for source/artifact inputs, controls, themes,
navigation and limitations. Do not invent component properties from library APIs.

## Author from evidence

Identify the facts that must survive: entities and attributes, edge direction,
branch conditions, message order, optionality, multiplicity, dates or ownership.
Keep a small checklist against the supplied material. Mark uncertainty and
synthetic examples; do not invent stages, measurements, filenames or chronology.
Choose stable IDs separately from display labels. Preserve source text so a
later revision can change the diagram rather than rebuilding from a screenshot.
Source statements need actual newlines. The component entry includes a complete
JSON payload showing one level of newline encoding; serialize that document
once rather than leaving literal backslash-n separators in the source value.

Give each diagram the space its relationships need. Full width, equal columns,
uneven columns and a vertical report are all options. Separate independent
subjects when useful, while keeping views needed for a comparison together.
Keep quantitative evidence in data views when filtering, units or shared
selection matter; diagrams and custom HTML/SVG are available for explanations
that benefit from them.

Folder links are intentional actions, not inferred from filenames or node
names. Inspect the actual workspace before adding the catalog's explicit
`workspace-folder:` targets. A conceptual tree does not imply real files exist.

## Review the authored result

Use `review-visual-presentation` for a substantial diagram/report. Inspect the
actual captured image of the published artifact at the docked width, and an
expanded view when needed. Check every relevant view, not just the first tab.
Review headings, labels, legends and arrows as well as the diagram bounds.
Source visibility or a successful render does not establish readability.

Compare the rendered relationships with the evidence checklist. Fix missing
conditions, reversed arrows, omitted siblings, undefined grammar productions,
clipped text or unreadable scaling; then capture and inspect the correction.
Do not simplify away a difficult relationship just to make syntax pass. State
any remaining defect and distinguish an unavailable capture from a parser error.
A renderer gallery tests the renderer; acceptance requires the model's own
authored artifact and its actual captured pixels.
