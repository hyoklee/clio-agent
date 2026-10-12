# Feature documentation coverage

Checked on 2026-10-09 against the public site, current `main`, and the reviewed
feature branches. This is the maintenance map for the website, not a release
announcement. Publishing site content does not release product functionality.

| Feature | Reader entry points | Evidence and availability |
| --- | --- | --- |
| Best of N and Refine | Overview workflow guides; `docs/best-of-n.mdx`; sessions guide | Real Codex/Luna generation in the draft review: five individual user-judged candidates and three model-judged candidates. The draft corrections are in [backend PR 1661](https://github.com/iowarp/clio-agent/pull/1661) and [UI PR 556](https://github.com/iowarp/gact-tui/pull/556), not beta 5.2. |
| Saved dashboards | Overview workflow guides; `docs/dashboards.mdx`; linked-data guide | Real agent-authored reports, saved artifact viewer, tabs, PNG and bundled HTML in [backend PR 1663](https://github.com/iowarp/clio-agent/pull/1663) and [UI PR 558](https://github.com/iowarp/gact-tui/pull/558). The guide uses an untouched, explicitly synthetic capture; see `src/assets/captures/README.md`. Not beta 5.2. |
| Visual review loop | Dashboard guide | Supported mounted-view control and image delivery in [backend PR 1666](https://github.com/iowarp/clio-agent/pull/1666) and [UI PR 566](https://github.com/iowarp/gact-tui/pull/566). Keep preview status until release acceptance is complete. Do not advertise arbitrary controls or generic annotation overlays. |
| Exports and downloads | Overview workflow guides; `docs/exports.mdx`; sessions and file guides | Existing public session-export walkthrough retained. Transcript/Effects/Full are existing scopes. Named checkboxes and native download routing are development changes in PR 1661/UI 556; Windows uses native history, macOS/Linux use the folder. No automatic opening of files. |
| Final artifacts and review evidence | Exports guide | Latest deliverable selection and purpose-labelled retained evidence in PR 1666/UI 566. Requested images/PDFs remain deliverables. Not beta 5.2. |
| Questions and visual answers | `docs/questions.mdx`; sessions; widget interaction guide | Source checked 2026-10-12: native text/choice/confirmation, MCP forms/multiple selection/URL consent, and A2UI question surfaces. Current blocking and async modes are distinguished. Always-async posting plus an explicit question wait is a proposal, not documented as shipped. Captures replay a retained real question and show the real gallery control; no new model run. |
| Tools, tasks, and todos | `docs/following-work.mdx`; sessions; long-running work | Source checked 2026-10-12: task waits default to no deadline; terminal state does not establish assignment success; current todos differ from execution. Screenshot replays the actual command, output, and presentation from the public fictional workflow qualification. Development layout, unmerged local changes. |
| Context injections | `docs/injections.mdx`; long-running work | All named injection labels in the current UI are mapped to user-facing purposes, including tool-use guidance. A real recorded loop wake is replayed in the current production row. Development grouping is distinguished from older display. |
| Right-hand panels | `docs/workspace-panels.mdx`; evidence; sessions | Compact Data/Work, full Work, Observability's Evidence/Timeline/Gantt/Context, and opened content tabs checked in current source. Existing authentic captures retained with stated provenance. No claim of fresh OPAL inference, release, or deployment. |

When one of these changes ships:

1. Check the published installer/backend and pinned UI commit, not only the merge.
2. Update the affected guide's availability note and the overview guide status.
3. Review prompts, visible control labels, desktop/browser differences, and actual
   saved output. Refresh captures from that release when labels or layout change.
4. Run the site's unit tests, type check, production/link build, and browser tests.
5. Verify Pages deployment after an authorized merge to `main`.

For later user-visible features, add or update a reader entry point in the same
feature campaign. Record the source and limitations for media; do not present a
test fixture as a real user workflow. Follow `WRITING.md` and the capture plan.
