# Pele in CLIO

## Source language and host contract

Pele renders Mermaid-family source with its own layout. Use `flowchart`,
`sequenceDiagram`, `gitGraph`, `mindmap`, `stateDiagram-v2`, `timeline`, or a
supported grammar declaration. There is no `pele` code fence, `clio.pele.v1`
component, or renderer configuration object to invent. The bundled renderer in
this integration is Pele 1.6.0; a generic online Mermaid editor may not recognize
Pele's railroad declarations. Online examples can also target a newer version.

A short explanation can be a fenced `mermaid` block. In a dashboard, load the
active `clio.mermaid.v1` schema, then give the component ordinary source text:

```json
{
  "id": "handoff",
  "component": "clio.mermaid.v1",
  "title": "Observation handoff",
  "source": "sequenceDiagram\n  participant User\n  participant Endpoint\n  User->>Endpoint: Request observations\n  Endpoint-->>User: Return observations"
}
```

This is one component inside a surface/report, not a complete dashboard document.
For a larger source file, register its actual text and use the returned artifact
URI in `dataUri` instead of `source`; do not pass a guessed artifact ID, raw file
path or HTTP URL. `create-dashboard` explains saving and revising the report.

## Match notation to meaning

| Relationship | Declaration and authoring semantics |
| --- | --- |
| Stages and decisions | `flowchart LR` or `flowchart TB`: stable node IDs, display labels and directed edges. A diamond can express a decision. Put an actual condition on a branch rather than inventing a stage. |
| Ordered exchanges | `sequenceDiagram`: participants are lifelines, arrows are messages in time order; `alt`/`else`/`end` can express documented alternatives. It is not a dependency graph. |
| Branch ancestry | `gitGraph`: create commits on the active branch, create/check out named branches, and merge an existing branch into the active one. A merge is not merely another message arrow. |
| A hierarchy | `mindmap`: indentation establishes parent/child relationships; siblings have equal indentation. It does not express time or arbitrary cross-links. |
| Lifecycle | `stateDiagram-v2`: states and transitions, with `[*]` for entry/exit. Do not label processing stages as observed states without supporting material. |
| Chronology | `timeline`: date/period labels followed by their events; dates come from the supplied material. |
| A language or protocol grammar | `railroad-ebnf-beta`: productions define accepted token sequences. Grammar alternatives, optional terms and repetition have distinct meanings. See the worked grammar below. |

These are useful choices, not an exhaustive list or required set of panels.
Choose the notation the explanation needs. For another supported family, use its
documented declaration and inspect the actual CLIO rendering.

## Railroad grammar

Use EBNF for ordinary grammar explanations. A production ends with `;`.
Quoted strings are literal terminal tokens; unquoted names refer to productions.
Adjacent terms form a sequence, `|` separates alternatives, `( ... )` groups,
`[ ... ]` is optional, `*` means zero or more, and `+` means one or more.
Define referenced productions when a self-contained grammar is needed.

```mermaid
railroad-ebnf-beta
request = verb path [ query ] ;
verb = "GET" | "POST" ;
path = "/" segment ( "/" segment )* ;
query = "?" pair ( "&" pair )* ;
pair = segment "=" segment ;
segment = ( "a" | "b" | "c" )+ ;
```

This intentionally small synthetic language accepts GET and POST, path segments
and an optional query. It does not model all of HTTP. Adapt the grammar to the
actual language; do not silently omit alternatives or change repetition to make
the drawing easier. ABNF, PEG and the railroad DSL have different declarations
and operators; do not mix them into an EBNF production.

## Layout, labels and appearance

CLIO supplies the container width, adaptive canvas and active palette. Pele's
layout differs from Mermaid's; a wide LR flowchart may become vertical in a
narrow container. Inspect the final docked image as well as any expanded view.
Give a dense view more space or reorganize it according to the relationship;
scaling down until labels are unreadable does not solve layout.

Use stable short IDs and separate display labels. In JSON, `\n` separates source
statements; a literal backslash-n inside a node label is encoded as `\\n`.
Mindmaps need their actual indentation preserved. Arbitrary HTML labels such as
`<br>` are rejected by CLIO. Use ordinary text and supported line breaks.

Pele uses CSS variables for colors. Mermaid `themeVariables` do not control its
palette. CLIO owns that mapping; do not inject CSS, `%%{init}%%` directives,
external fonts or JavaScript to force a theme or dimensions through this component.
Renderer API options such as `maxWidth` are not extra component properties.
For custom authored interaction or styling beyond the contract, use the existing
HTML/SVG artifact workflow when it serves the request.

## Navigation and recovery

CLIO intercepts explicit `workspace-folder:` flowchart targets before rendering.
Inspect the directories and use the folder example in `SKILL.md`; folder clicks
are CLIO navigation, not arbitrary Pele links. SVG/PNG exports retain the image,
but do not promise working app navigation. External links, images, callbacks and
third-party Mermaid plugins are not capabilities of this component.

For a syntax error, check the declaration, the grammar's own operators, matching
blocks/brackets, quoting and indentation. Correct the source instead of swapping
in a prewritten gallery or deleting the difficult relationship. CLIO tries its
compatibility renderer when Pele rejects source, but that does not add support
for a Pele-only grammar to an older Mermaid parser. Report an unresolved render
error honestly.

A missing viewer or failed image capture is a different failure from invalid
syntax: source validation does not prove visible pixels. Use the declared
`review-visual-presentation` procedure and the exact published artifact. Review
the actual returned image, preserve the request's semantics in any revision, and
capture again. Do not claim to have tested node clicks unless you exercised them.

Authoritative upstream references: [compatibility](https://pele.run/compatibility),
[railroad examples](https://pele.run/examples/railroad),
[theming](https://pele.run/theming). CLIO's current catalog and runtime constraints
take precedence over upstream features not exposed by the host component.
