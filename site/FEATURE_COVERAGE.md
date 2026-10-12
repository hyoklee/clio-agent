# Feature documentation coverage

Checked on 2026-10-09 against the public site, current `main`, and the reviewed
feature branches. This is the maintenance map for the website, not a release
announcement. Publishing site content does not release product functionality.

| Feature | Reader entry points | Evidence and availability |
| --- | --- | --- |
| Agent-facing background tasks | `docs/tasks/`; sessions; files/connect; docs introduction | Development PR1704/UI590. All five kinds return accepted handles; reviewed runtime `fa294aff` and UI `ff8da5b6`. Core/cache-owned Linux model qualification is retained in the external ledger; full native/provider/transport acceptance is incomplete. |
| Subagent lifecycle and human intervention | `docs/tasks/subagents`; `docs/tasks/observe-and-wait` | Real Codex/Luna production UI run `codex-ui-progressive238`: five pause/resume cycles, physical subtree settlement and linked restart. Four untouched/hash-matched screenshots; media receipt `src/assets/captures/tasks/README.md`. MCP/Download/Indexing human cancellation each has five actual-model parent-notice cycles. |
| Session messages and discovery | `docs/tasks/messages`; memory and evidence | Five Codex and five Claude busy/idle cycles between independent root sessions in one workspace, using one blueprint. Cross-workflow execution is not qualified. Search is lexical; summary is metadata and recent excerpts, not a model-generated whole-session summary. |
| Root sessions as tasks and workflow subscriptions | `docs/tasks/session-coordination` | Explicit proposal. Root-run task projection, peer observation/waits and cross-workflow subscriptions are not implemented or live-qualified. Do not describe remote relay lifecycle or scheduler submission as full job completion. |
| Best of N and Refine | Overview workflow guides; `docs/best-of-n.mdx`; sessions guide | Real Codex/Luna generation in the draft review: five individual user-judged candidates and three model-judged candidates. The draft corrections are in [backend PR 1661](https://github.com/iowarp/clio-agent/pull/1661) and [UI PR 556](https://github.com/iowarp/gact-tui/pull/556), not beta 5.2. |
| Saved dashboards | Overview workflow guides; `docs/dashboards.mdx`; linked-data guide | Real agent-authored reports, saved artifact viewer, tabs, PNG and bundled HTML in [backend PR 1663](https://github.com/iowarp/clio-agent/pull/1663) and [UI PR 558](https://github.com/iowarp/gact-tui/pull/558). The guide uses an untouched, explicitly synthetic capture; see `src/assets/captures/README.md`. Not beta 5.2. |
| Visual review loop | Dashboard guide | Supported mounted-view control and image delivery in [backend PR 1666](https://github.com/iowarp/clio-agent/pull/1666) and [UI PR 566](https://github.com/iowarp/gact-tui/pull/566). Keep preview status until release acceptance is complete. Do not advertise arbitrary controls or generic annotation overlays. |
| Exports and downloads | Overview workflow guides; `docs/exports.mdx`; sessions and file guides | Existing public session-export walkthrough retained. Transcript/Effects/Full are existing scopes. Named checkboxes and native download routing are development changes in PR 1661/UI 556; Windows uses native history, macOS/Linux use the folder. No automatic opening of files. |
| Final artifacts and review evidence | Exports guide | Latest deliverable selection and purpose-labelled retained evidence in PR 1666/UI 566. Requested images/PDFs remain deliverables. Not beta 5.2. |

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
