# Tasks: short requests and portable conversations

Recorded October 20, 2026, America/Chicago. These are new documentation examples,
not a replacement for the finite Tasks acceptance ledger or a release announcement.

## Frozen service and real conversations

- Agent source: `b73861a6f610c5ba640ede4f6c1956a7a0e259c9` (production code unchanged
  from qualified `601ef47b669ca6bacd86aca319f7b9fbe1cbfc7d`).
- GACT: `86214905b4fd99b184ac0b5b6e4e9506f6bd7bf6`.
- Marketplace: `2c172233a9f895e41f7de121a3871d282a5fc0a2`, unmodified Base Agent 0.2.8.
- Python 3.14.6 / iowarp-core 2.3.2 / FastMCP and fastmcp-tasks 4.1.0 /
  MCP 2.0.0 / Docket 0.26.2. Codex direct SSE, `gpt-6-luna`.
- Plain production `clio_agent.gact.app.run_server` on an owned Ares compute
  allocation. No task/runtime/model adapter overrides or scripted model replies.
- Workspace `ws_72bd21201dba`; planner `sess_5ab30f200c1d`; reviewer
  `sess_f7626ee04750`. Authenticated operator grants in each direction provided
  read/observe/message rights, without control. Tools were preapproved only in
  this disposable illustrative workspace.

The complete human requests are in the exports and the website walkthrough.
They specify outcomes rather than tool names, IDs, expected answers or call order.
The operator's October 30 answer is demonstration data, not the user's real
calendar preference. The budget and simulation are explicitly synthetic.

| Actual behavior | Recorded observation |
| --- | --- |
| Discover and inspect a peer | Planner called `query_tasks(scope="authorized", query="Budget review")`, then `observe_tasks(view="transcript", history="session")`. |
| Message an independent session | Planner messaged the original reviewer handle. Reviewer continued after its initial response and replied to the planner's stable session. |
| Late review | Planner first reported that the revised review had not arrived; a later attributed peer result woke it and produced a separate correction. Both responses remain present. |
| Inspect summary and deliverable | Planner read the reviewer's recorded summary and artifact listing, then read the actual saved note before sharing its versioned link. |
| Background Shell | `python cost_simulation.py` returned `task_b863e30913cd4468ae89025181154e85`, accepted/running/executing; the model then posted a Question and drafted a run-sheet. Actual output records eight million samples and the synthetic assumptions. |
| Asynchronous Question | `ask_user` returned a durable input-required handle immediately. Question `task_2a4b1de6b1b9fcfd6c4315fed896f31017feefbf19f28092f9f411c311325fda` remained pending after the response. The operator's answer at 00:28:25 UTC committed into the same active assignment and woke the model to update the run-sheet. |
| Artifact revisions | First and corrected budget plans plus provisional and dated run-sheets are retained as distinct recorded artifact versions. |

## Native exports, without rewriting history

Used the actual compiled production `SessionHistoryRepository.prepareSessionArchive`
with `captureSessionReview`, the matching `offline-review.js`/CSS and the production
`export-download` route. Mode is **Transcript**: standalone HTML, without Effects
or Full backup ZIPs. No exported message, error, observation or payload was edited.

| Website file under `site/public/conversations/tasks/` | Bytes | SHA256 |
| --- | ---: | --- |
| `workshop-planner.html` | 15,496,750 | `60581e58c8d2a89983a6744174e650ca1238108e5fb9f155c825399b844db460` |
| `budget-review.html` | 12,083,048 | `c56ac1aadc1ef72940bcef79da361cc8471bca8d4d781a744e2dbad34696135d` |

Decompressed export payloads contain the actual transcript, transcript views,
manifest, response snapshot and embedded tool outputs. Both snapshots report
zero capture failures. Raw and decompressed payload scans found neither the
operator bearer nor original authentication token values. The original auth file
hash remained unchanged; no refresh token was forwarded.

Browser inspection opened both native viewers and the reviewer's captured
Markdown artifact. The latter rendered its complete figures and caveats without
the live service. Browser console error list was empty on this inspection.

The website walkthrough itself rendered at measured 1315×900 and 387×843 CSS
viewports, with matching document/scroll widths and no console errors. Following
its **Open Workshop planner** link opened the unchanged native HTML and its
interactive viewer. The selected light-mode [phone capture](media/tasks-walkthrough-phone.jpg)
is 55,290 bytes, SHA256 `84c5c4497ed8eec57565122319f53832ffe02ea5a1051fb6f7013156b0f617e4`.

### Retained rough edges

- The model altered one opaque cursor: its position key omitted a character
  from the selected handle. The runtime rejected it with `Task context cursor
  positions are invalid`. This is retained as a failed tool call, not a successful
  pagination demonstration.
- The model also asked for a differently named revised plan. The reviewer
  reported that it was absent and reviewed the available `updated-plan.md` instead.
  The planner's initial contingency reduction and later attendance tradeoff are
  retained; no real saving or vendor acceptance is claimed.
- The archive's three-tab header exceeds a narrow phone viewport (observed
  document width 387, scroll width 448). Desktop inspection had no horizontal
  overflow. This is an archive presentation limitation, not a passed phone gate.
- The planner's `artifact://workspace/name@version` peer link renders as text in
  this archive viewer. The note's own artifact card opens in **Budget review**;
  the planner's local plan/run-sheet cards are also present. Live workspace paths
  and controls are not promised to work offline.

## Prompt discussion with Claude

Before any prompt change, actual Claude Opus 5.5 independently inspected the
shared task snippet, injection boundary, coverage and representative domain
expert prompts. Its recommendation was **no prompt changes**.

`gact/agents/clio_react.py` appends `task_guidance(tool_names)` after capable
root/child expert prompts. The shared `clio.runtime.tasks.md` already describes
discovery, exact-target messaging, transcript/summary/artifact views, asynchronous
Questions, background handles, automatic wakes and lifecycle controls. Existing
coverage checks the shipped React experts and distinct bridge boundaries.

No domain `main.md` duplication, prompt edit, runtime change, dependency change
or released pin change was made for these examples. This review is source
evidence; it is not fresh live execution of every marketplace agent.

## Build and cleanup

The new walkthrough and both existing Tasks pages rendered in a fresh D-owned
site copy. A whole-site local build first lacked the repository version metadata,
then reached the unchanged widget gallery without its generated `widget-docs.html`.
These were incomplete local build prerequisites, not passes. The existing Pages
CI builds that pinned gallery before building the complete site; its current-head
result is tracked separately. No widget stub, assertion reduction or source
workaround was added.

All model tasks settled before shutdown. Four bounded service/setup receipts
retain the earlier task-starting response, ambiguous blueprint ID and a supervisor
process-inspection race; none was repaired by changing production code. The final
run used readiness, a qualified blueprint identity and race-safe process inspection.

Ares allocation 24986 ended. The exact fresh showcase root, environment, cache,
credentials, Core state and workspaces were removed: **103,366 regular files,
5,611,576,843 logical bytes**, with 1,637 links not followed. No archive was created.
The SSH tunnel and local private operator profile were also removed; port 19172
had no remaining listener. Original Desktop, authentication and unrelated data
were preserved. Local site-build/preview cleanup is recorded in the final receipt.
Both local preview listeners were retired. The exact fresh site copy, dependencies,
package store, generated build/cache, duplicate exports and temporary raw transcript
copies were removed: 62,878 regular files / 1,550,145,066 logical bytes. Only the
two canonical HTML files, selected phone capture and bounded receipts remain.

Bounded D-repository receipts: R910 (Claude), R940/R943 (native exports/privacy),
R944 (no active tasks), R948 (Ares retirement), R950 (tunnel/auth), and the final
website/browser/cleanup receipt. Only the selected native conversations and
documentation media belong in the feature branch. No deployment, merge, tag or
installation is part of this documentation change.
