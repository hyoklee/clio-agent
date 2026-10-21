# Diagram skill and screenshot audit

## Correction to the earlier acceptance claim

The submitted image exactly matches the operator-authored gallery capture
`D:/CLIO-Develop/diagram-live-20261018/diagram-gallery.jpg`, SHA-256
`b8f769cc5f05041d56552edf65c496cae1117b9a63166974d52cb7c790e7b15b`.
The six gallery examples are literal strings in GACT's
`web/tests/review/diagrams.tsx`. The lower workbench displays a saved model
artifact, but that does not make the gallery examples model-authored output.

The earlier Sol/Luna sessions were actual model runs against a synthetic station
project. They authored/reviewed a flowchart, with operator retries after real
capability/capture failures. They did not test agent authoring of sequences,
git graphs, mindmaps or railroad grammars. The lookup counts in the old receipt
cover the final repair turn; the strong model's initial authoring loaded six
skills/references. `qualification.json` now includes these scope corrections
without removing the original evidence.

## Skill and component guidance

The shared built-in is `src/clio_agent/gact/builtin_skills/create-diagram/SKILL.md`.
Its existing `references/diagram-examples.md` contains five syntax examples.
The entrypoint now discovers Pele explicitly and links a new
`references/pele-in-clio.md`, covering:

- Mermaid-family source versus the Pele renderer and the unchanged
  `clio.mermaid.v1` host component.
- Inline source, registered source artifacts and the ordinary dashboard workflow.
- Diagram selection and the meanings of protocol alternatives, branch ancestry,
  indentation, transitions and grammar productions.
- EBNF terminals, references, optional terms, alternatives, grouping and repetition.
- Adaptive layout, line breaks, automatic themes, host limitations and recovery.
- Actual image review, including the difference between a renderer gallery and
  a model's authored result.

Canonical component instructions in `clio-schemas-diagrams-1786` now point to
this procedure and distinguish source text from renderer API options. Generated
instructions and hashes were regenerated and verified. The shared visual-review
skill now explicitly includes component/frame headings and separates docked
readability from expanded readability.

The current NDP service on port 5219 uses a checkout without this diagram skill.
It was not replaced or restarted. This evaluation used the separate real CLIO
application on 5226 and service on 8221, not the gallery route.

## Fresh actual model evaluations

Evidence root: `D:/CLIO-Develop/diagram-live-20261018/skill-audit-20261018/`.
`receipt.json` contains the actual session IDs, model choices, loaded references,
tool calls, captured viewer states, image hashes and responses. The requests were
entered through the normal workspace composer; no mocked API responses, provided
diagram sources or substituted captures were used.

The content source was an explicitly synthetic teaching note, not production
scientific data. It described an allowed/denied request protocol, a precise
branch history, a research hierarchy and a query language. Each model was asked
to author all four diagrams and inspect its rendered report. The small-model
workspace did not contain Sol's report.

| Model | Session | Result |
| --- | --- | --- |
| `gpt-6.1-sol` | `sess_d9b3f89658e6` | Authored all four types, published, captured, shortened clipped headings and added a branch-history caption, then captured again. 16 tool calls, two successful captures. |
| `gpt-6-luna` | `sess_f0d6f9e2042a` | Authored all four types and captured the published report. A subsequent review after the renderer/guidance correction captured again and reported the docked readability limit. 16 tool calls across those two turns, two successful captures. |

Both models loaded the new Pele reference and authored valid source preserving
the mutually exclusive protocol outcomes, exact commits/merge, all hierarchy
children, optional filter, comma-separated repetition and nonempty letter terms.
The source files were independently inspected against the teaching notes.

The first Luna setup attempt was invalid: the operator's old `path` request field
left the newly created workspace root empty. It was stopped; its session and
transcript are retained as `small-invalid-setup-*`, rather than counted as a
skill failure or successful acceptance. A new workspace was created using
`root_path`, its returned root verified, and a fresh session given the absolute
input location. Only scoped writes inside that registered test root were approved.
No repository-folder grant was added.

## Visual findings and limits

Sol explicitly reported small railroad labels in its 264-pixel docked view.
Luna's initial claim of no defect missed a truncated component heading. That
review is not counted as a visual pass. The renderer still had `truncate` on its
diagram headings; both normal and fullscreen headings now wrap instead. The
existing source/artifact was preserved, and the actual model received a fresh
capture after that renderer change and after reloading the updated review skill.

The new Luna capture shows the complete wrapped heading. Its answer now states
that the grammar labels remain harder to read at 264 pixels and that it did not
inspect an expanded view. An operator separately inspected Sol's actual expanded
viewer and saved native screenshots. The original teaching semantics remained
unchanged. This establishes authoring of the four requested types and a concrete
renderer correction; it does not establish polished readability for every type
at every width, or a universally reliable automatic visual critic.

Native workspace screenshots are in the evidence root's `screenshots/` directory.
`strong-expanded-grammar.jpg` is a rejected take: a wheel action zoomed the
diagram rather than scrolling the page. Zoom was reset; the separately saved
`strong-expanded-grammar-actual.jpg` shows the actual later view. Untouched
model captures are retained independently and verified against their tool hashes.

## Supporting checks and state

- All seven fenced diagram examples in the skill bundle rendered through the
  installed Pele 1.6.0 library. This is renderer regression evidence.
- The actual CLIO skill loader resolved the entrypoint and both references.
- 13 visual-review/skill-discovery tests passed, no skips. The Core binding
  printed its existing nanobind leak diagnostics at process exit.
- 11 diagram renderer tests passed, no skips; existing React act warnings remain.
- UI TypeScript and targeted Oxlint passed. Canonical schema export verification,
  Ruff and formatting checks passed.
- The dev server logged ResizeObserver loop notifications during the operator
  review. This audit does not claim an error-free browser console.
- Codex's generic skill validator rejects the existing CLIO-specific `title`
  frontmatter field. CLIO's own parser/loader accepted it; the field was preserved
  rather than changing the target product's skill format to satisfy that validator.

These changes are local and uncommitted. No push, merge, release, public
deployment or homepage edit was performed. The temporary 5226/8221 services were
shut down after evidence collection. The temporary Core daemon on port 27801
(PID 14556, parent 41884, created at 15:15 during this run) was also stopped after
verifying ownership. The user's 5219/8209 services and Core PID 41976 remained up.
