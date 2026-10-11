# Conversation relationships acceptance — 11 October 2026

## Delivered behavior

- Observability's existing **Gantt** surface switches to **Relationships** and back.
- User branches and parent-owned delegated agents have distinct relationship labels and arrows.
- Nodes select a conversation inspector with navigation and a saved fork-source link.
- The current conversation's available outputs open their existing artifact Preview, Versions and Lineage views.
- Families containing user branches show recorded turn durations and saved branch creation milestones in Gantt. **Execution details** retains the latest execution's tool view.
- Rounded Gantt connectors use actual source and target geometry, the same full time-axis width as the bars, and routes that avoid other bar bodies. Missing endpoints do not produce floating lines.
- A new fork saves its immediate source, actual last copied message, copied count, title and creation time. The child transcript displays one checkpoint after that message. Empty forks have an empty-history checkpoint.
- A parent's later rewind does not alter the child's historical checkpoint. Older branches without saved origin data do not receive invented checkpoints or creation times.
- Selection survives view swaps and the responsive desktop/mobile canvas remount.

This does not change asynchronous task ownership, lifecycle controls, user-fork restrictions on managed sessions, file snapshot semantics, or artifact lineage storage.

## Automated checks

- Backend: **78 passed** across `test_conversation_origin.py`, `test_fork_and_search.py`, `test_session_fork_policy.py`, and `test_message_marks.py`.
- Frontend: **82 passed** across 12 focused suites covering checkpoint placement, family selection and bounds, real turn projection, connector geometry, toggling, ownership labels, live-event query invalidation, workspace projections and shared provenance-provider selection. The final provider/workspace rerun passed **22 tests**.
- Backend Ruff check/format passed. Mypy passed for the three changed production Python files (`--follow-imports=skip`).
- Frontend TypeScript build and repository lint/ownership/component/file-size guards passed.

Commands use the existing environments: `uv run --no-sync`, and `pnpm exec` in `external/gact-tui/web`. No extra worktree or dependency checkout was created.

## Real service and model acceptance

Driver: `scripts/live_verification/conversation_relationships.py` against an isolated production CLIO service on port 17963, Python 3.14.6, private clio-core, actual Codex/Luna authentication and inference. These are fictional calibration readings, not private research data.

| Case | Observed result |
| --- | --- |
| Baseline readings 10, 12, 14 | Actual model mean **12**, saved Markdown artifact |
| Message-level offset branch | Copied exactly two messages; model mean **14**, derived artifact declaring the baseline input |
| Nested whole-conversation fork | Immediate source is the offset branch; model mean **17** |
| Sibling excluding reading 14 | Independent model mean **11** |
| Original after creating branches | Still two baseline messages |
| Parent rewind before its baseline answer | Child retained its copied messages and exact saved fork origin |
| Parent continuation after rewind | Actual model mean **12** |
| Offset branch continuation | Actual model recalled its own +2 method and mean **14** |

All **13 service verdicts passed**. The initial artifact prompt requested an unsupported `markdown` kind; the real model reported this and registered the Markdown file as `other`. The retained transcript includes that error. The repeatable driver now requests the supported `other` kind.

A controlled service restart preserved all four conversations, the exact saved origin and the copied source message. The real-browser acceptance was rerun against the restarted service; this persistence check reused the recorded real responses rather than claiming fresh inference.

The native execution provider returned a complete, untruncated family snapshot with six actual turn spans. A smaller manual diagnostic query truncated the record; the UI uses its existing 10,000-event budget and labels incomplete/truncated snapshots.

## Browser and visual acceptance

`external/gact-tui/web/tests/deployment/live/conversation-relationships.spec.ts` ran against that real service and the production React UI, without route interception, injected transcripts or substituted model replies.

The final Chromium run passed checkpoint persistence, six recorded turn bars, three attached fork connectors, all activity rows inside the chart, four ReactFlow nodes and three real edges, source/target graph port alignment, selection retention across view swaps and responsive remounts, actual output lineage, nested-conversation navigation, and reload. No page errors were recorded.

- Gantt arrowhead gaps: at most **1 pixel horizontally**, **0 vertically**.
- Relationships source/target port gaps: **0 pixels**.
- Widths: **1440, 1024, 736 and 390 pixels**; no page overflow, all graph nodes fit after resizing.
- Visual review rejected intermediate captures with overlapping milestone labels, clipped stacked rows, stale graph fit and a narrow output pane. The delivered captures show all named rows, connected arrows, a fitted family graph and a maximized lineage pane.

| Public capture | Framing |
| --- | --- |
| `docs-fork-checkpoint.png` | Child header, copied offset answer, checkpoint, new request and actual nested answer; unrelated sidebar omitted |
| `docs-conversation-family-gantt.png` | Observability tabs, switch, four complete rows and legend; empty lower canvas cropped |
| `docs-conversation-relationships.png` | Same Observability frame, full family and selected conversation's outputs |
| `docs-conversation-output-lineage.png` | Maximized artifact pane with Preview/Versions/Lineage, real baseline-to-offset chain and fit controls |

Original full frames, exact API requests/responses, provenance JSON, browser verdict, source identities and isolated service state are retained in `C:/clio-relationships-20261011`. Only the four reviewed PNGs are copied into `site/src/assets/captures/` (under 400 KB combined). No OPAL data was used.

## Website documentation

The branch/rewind guide includes the checkpoint, switch, ownership distinction, real response timing, incomplete-record behavior, parent rewind semantics and the connection to artifact lineage, with all four product captures. Evidence and Sessions link to that walkthrough.

The site build and browser guide checks validate image loading, enlarged image dialogs, keyboard dismissal/focus return, cross-guide navigation and 390/1440-pixel layout. Website publication still follows the normal `develop` to `main` release; this acceptance does not claim a public deployment or installed Desktop update.

Site results: Astro check **0 errors / 0 warnings** (six existing hints), production build **80 pages** with valid internal links, and **2 browser tests passed**. The four enlarged screenshots were reviewed in the built guide on desktop and mobile. `CLIO_SITE_TEST_PORT=4393` kept this run separate from an existing preview on 4389.

The website unit suite also passed **30 tests**. The family's provenance query follows the execution provider selected by the user; a dedicated hook integration test checks changing from native to Flowcept without silently retaining the old provider.

## Resource closure

The owned backend, private core, Vite server and temporary docs preview were stopped; their four ports no longer listen. No worktree was created. Removing the stopped service's disposable `home` and `private-core` directories (about **519 MB** on C:) was rejected by automatic approval review with only `blocked by policy`. They were retained rather than deleted through a different mechanism. Small acceptance records and reviewed captures remain available alongside them.
