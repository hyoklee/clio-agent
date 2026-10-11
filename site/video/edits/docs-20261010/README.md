# Task walkthroughs — 10 October 2026

These four clips are continuous recordings of real product interactions in the
development build, with fictional bike-station counts. They contain no OPAL data
or imported private sessions. Best of N and refinement use actual Codex/Luna
inference. The dashboard is prepared through the production artifact and dashboard
tools, rather than claimed as a fresh model analysis.

| Published recording | Native source in `raw/` | Approximate duration | Review |
| --- | --- | --- | --- |
| `docs-best-of-n.mp4` | `best-of-n-4.mp4` | 26 s | Three independent candidates, criteria, and selection. |
| `docs-refinement.mp4` | `refinement-2.mp4` | 35 s | First draft, actual feedback, revision, and acceptance. |
| `docs-dashboard-html.mp4` | `dashboard-html.mp4` | 20 s | Real HTML download, offline opening, and linked selection. |
| `docs-session-export.mp4` | `session-export.mp4` | 17 s | Real export menu, HTML download, and offline review. |

The JSON edits specify every source interval and labelled speed change. The
comparison edit omits two brief native screenshot interruptions (0.68 seconds
total); all tab, criteria and pick actions remain recorded. Output
preserves the 1280 × 960 native frame so the composer and acceptance controls stay
visible. Posters and comparison/refinement stills come from decoded source video;
other screenshots are original browser captures. No controls or responses are
painted into the recordings. VTT captions describe the recorded actions.

The source runtime is `6805ef9e` plus the one-candidate fix `43b19bf7`, with UI
`264e128d3eee69421e733ee59048275e4c802f73` and iowarp-core 2.3.1. Public guides
explicitly identify these controls as a development preview, unavailable in beta
5.2. The one-candidate boundary is also checked against actual LM requests in
the variant integration tests.

Permanent archive:
`D:/Libraries/Videos/clio_recordings/2026-10-10-docs-task-walkthroughs/`.
It retains unmodified raw takes and action timestamps, actual downloaded files,
variant/message records, authoring files, published assets, hashes, and browser
review evidence. It excludes credentials, browser profiles, node_modules and
disposable core state.

Rejected takes are retained for provenance:

- `best-of-n.mp4`: capture failed on the initial composer locator.
- `best-of-n-2.mp4`: exposed the candidate-count instruction conflict; not a
  successful demonstration.
- `best-of-n-3.mp4`: genuine successful run, rejected for empty initial framing.
- `refinement.mp4`: genuine successful refinement, rejected because forced
  centering clipped the comparison heading and left excessive empty space.

`capture-docs-walkthroughs.mjs` drives production controls and native recording;
it refuses to overwrite a raw take. Its refinement scene uses normal locator
scrolling rather than forced centering. `review-docs-walkthroughs.mjs` plays each
encoded video completely, embedded and fullscreen, samples progress, retains
review screenshots, and checks the guides at 390 pixels. Tests also check media,
captions, posters, navigation order and example downloads.

The downloaded dashboard HTML is tested with networking disabled. It retains
all five station records, two charts, and linked selection. External basemap
tiles are not bundled: the background is unavailable offline while station
markers remain usable. This limit is visible in the recording and explained in
the guide and captions. The session review similarly reports uncaptured
dependencies; it is not described as a complete executable environment.

Reuse the existing Python environment and installed Chrome. Set
`CLIO_DOCS_EVIDENCE`, `CLIO_DOCS_ARCHIVE` and `DEMO_CHROME_PATH` before capturing.
Use the isolated service in `serve-workflow-review.py`, with its evidence and
agent home pointed to a bounded disposable directory. Close it with
`POST /review/close` and reap only its private core after recording. Stop owned
previews when review completes. Do not create worktrees or duplicate dependency
environments for this shoot.
