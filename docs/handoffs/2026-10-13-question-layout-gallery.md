# Question controls and visual guide

Questions had several nested borders, and adding a comment required selecting an
option first. The UI now uses one shared surface for native text, choices,
connected-tool forms and link requests. Each offered choice has a plus control
that selects it and opens its optional comment. This supports an offered answer
with a clarification or requested change. A different approach remains available
through Something else when the question permits it.

UI PR: https://github.com/iowarp/gact-tui/pull/610

The website's question guide now lets readers cycle through seven illustrated
formats: choice, text, confirmation, multiple selections, form, link and visual
question. It separately explains visual context, the waiting behavior and the
owning agent. A walkthrough shows the selected option and comment together.

## Source and capture evidence

- UI source: `f3bac76f125c2a110a614ea4f1657a7051c3197b`.
- Actual components are exercised by the committed test-only review page
  `web/tests/review/docs-question-controls.html` in the UI repository.
- New native and connected-tool captures use seeded fictional questions. The
  visual chart and open-question list are retained demo captures. No new model
  inference or scientific analysis was run.
- Full screenshot originals, framing bounds, fixture sources, submitted response
  payloads and checksums are retained in
  `D:/Libraries/Videos/clio_recordings/2026-10-13-question-layout/`.
- The website crops surrounding empty space with CSS; the image viewer retains
  the complete screenshot. Source pixels and product labels are preserved.

## Validation

- UI TypeScript, targeted lint, component reuse, presentation override,
  icon vocabulary and file-size guards passed. Production Vite build passed.
- Browser interactions confirmed native choice/comment submission, multiple
  selections with per-option comments, and structured form field submission.
- Phone review at 390 pixels showed no horizontal overflow; light and dark
  layouts were reviewed.
- Added regression coverage for opening an unselected option's comment directly
  and for keyboard access, hidden drafts and explicit submission. Hosted CI runs
  the suites; no local test suites were run.
- Website type checking reported zero errors and zero warnings. Its production
  build generated 90 pages and passed internal link validation.

Local Desktop build and installation receipts are kept separately under
`D:/CLIO-Develop/question-layout-20261013/`. They distinguish the installed UI
revision from hosted qualification and merge status.
