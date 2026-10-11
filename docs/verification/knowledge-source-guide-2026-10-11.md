# Knowledge source guide verification — 2026-10-11

The public guide is `site/src/content/docs/docs/files/knowledge.mdx`, titled
**Knowledge source**, linked from the Files and sources navigation, sidebar,
overview, and connection guide. It is labeled as a next-release preview.

## Real captures and example data

Four light-theme browser screenshots show the connection form, graph with reader,
filtered file list with reader, and actual knowledge-tool activity. The authored
six-note Field study notebook is fictional. The downloadable
`site/public/examples/field-notebook.zip` contains the same notes and a minimal
`.obsidian/app.json`. No personal vault notes, screenshots, or credentials are
published.

The live source selected only `Field-notebook/Field study`, with read-only access.
Its index contained exactly the six selected notes. Opening the sibling
`Example vault.md` returned HTTP 404; `../Example vault.md` returned HTTP 409.
All eight files in the enclosing example vault matched their pre-turn ZIP bytes
after the agent finished.

An actual Codex/Luna turn used `knowledge_search`, `knowledge_related`,
`knowledge_open`, and `workspace_resource_read` to explain the daily calibration
checks and cite the notebook. All 19 recorded tool calls completed successfully.
The screenshot shows a portion of that activity, not fabricated model output.
The browser reported no page errors during the capture session.

Original PNGs, cropped JPEG derivatives, SHA-256 copy checks, scripts, and review
evidence are retained in the dated local `clio_recordings` knowledge-source shoot.
Only cropped/encoded real captures are used; no UI labels or tool results were
altered. Graph orientation was changed in production before the accepted capture
so node labels remain readable beside the reader.

## Validation

- Backend: 40 connected-storage, linked-storage, knowledge, and sync tests passed.
  Coverage includes folder-scoped indexing, unresolved outside links, capture and
  edit confinement, private-root rejection, the enclosing-vault sync path, and
  vault-root link resolution within the selected folder.
- Ruff passed; mypy passed on all four changed production modules.
- Frontend: 29 source-picker/workbench tests passed; the final graph layout passed
  the three workbench tests, TypeScript checking, and frontend lint.
- Website: 30 unit tests passed; Astro check reported zero errors and warnings;
  production build and internal-link validation passed.
- New browser tests passed at 390px and 1440px, exercising navigation, loaded
  screenshots, full-size image links, example ZIP download, and overflow checks.
  Their rendered captures were inspected at both widths.

The official Headless Sync documentation was checked for subscription, open-beta,
sync-mode, and one-sync-method-per-device semantics. Authenticated Sync is not
claimed as live-verified. The official client synchronizes the enclosing copy;
the source folder limits CLIO knowledge access.
