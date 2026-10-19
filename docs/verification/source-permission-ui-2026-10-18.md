# Source permission UI qualification

The preview on port 5219 was still serving the NDP topic branch at UI revision
`9c7a8423`, which preceded the integrated attention-request pager. Updating the
backend alone had not updated that UI. Separately, ordinary and NDP source
connections supplied no native permission summary, causing the permission gate
to display `destructive tool call: connected_data_connect`.

The served UI now uses the integrated develop baseline plus the existing Escape
and single-request pager fixes and the source presentation follow-up. Its
preview revision is `518c6e4fb649b87117a6198dd5faa479d6bab748`; the focused UI
review revision is `f934c955689cf703f86fbca62c5cc22f73f2d158` in
[UI #653](https://github.com/iowarp/gact-tui/pull/653). The preview checkout and
focused review branch contain identical versions of the three changed source
permission files. The running checkout was not switched during publication.

Source connection and download requests now supply `Connect <label>` and
`Download <label>` summaries. The UI shows the source, provider, actual access
mode and selected NDP resources. It also gives retained requests with known
legacy generic summaries a readable title. Technical details retain the
original tool input; approvals, policy scope and access enforcement are unchanged.

## Real agent acceptance

Two real Codex Sol conversations used the actual web composer, real local
folders and the normal native approval gate. No permission rows, model answers,
tool responses or browser screenshots were fabricated or injected. The folders
are empty acceptance inputs; no scientific measurements were generated.

Exact prompt in both workspaces:

> Attach both of these folders as read-only sources: D:\CLIO-Develop\ndp-permissions-20261018\folder-a named Folder A, and D:\CLIO-Develop\ndp-permissions-20261018\folder-b named Folder B. They are independent. Do not download or modify their contents.

- [Initial conversation](http://127.0.0.1:5219/workspaces/ws_03a88c87ff24/sessions/sess_3a88c3ad448c):
  the agent discovered the shared connection skill and requested two real source
  connections. Browser control and the user's open page became unresponsive
  during this check. The browser recovered after the user reopened it; the
  cause of that browser freeze was not established or claimed fixed. Cold backend
  startup also logged transient registry-lock contention. The restored page
  showed a readable `1 / 2` queue. Both requests were approved for the workspace
  through the UI before automated navigation reached them. They completed.
- [Fresh isolated recheck](http://127.0.0.1:5219/workspaces/ws_de90fd4dc55e/sessions/sess_32eedd959729):
  the model first tried an invalid `folder` provider, received validation errors,
  and independently retried with `local`. Two actual approval requests followed.
  Automation captured `1 / 2`, clicked Next and captured `2 / 2`, approved that
  request once, verified that the sole remaining request had no pager, then
  approved it once. The queue cleared and both connections completed. The input
  folders were neither downloaded nor modified.

The recheck used a new workspace so the initial workspace's user-approved policy
was preserved. No approval policy was reset or bypassed. This qualifies the
permission presentation and lifecycle, not broad scientific task correctness.

Evidence: `D:/CLIO-Develop/ndp-permissions-20261018/`, including `receipts.json`,
exact prompts, publication revision records, service logs and the original
`live-pager-1-of-2.jpg`, `live-pager-2-of-2.jpg` and
`live-single-request-no-pager.jpg` browser captures. The earlier screenshot
named `actual-pager-1-of-2.jpg` was captured after approvals had already resolved;
it is not evidence of an open pager.

## Regression evidence

- 13 Python checks passed without skips in `test_source_connect_runtime.py`
  and `test_ndp_agent_workflow.py`. These include actual pending permission
  summaries and NDP connection/download summary assertions over the local HTTP
  workflow. Ruff lint/format and Pyright passed for changed backend modules.
- 36 focused UI checks passed across the final runs: attention pagination,
  permission operation details, pending interactions and routing. The new
  permission-page test was corrected to assert visibility because inactive pages
  intentionally remain mounted to preserve drafts. No production behavior was
  weakened for that assertion. TypeScript and focused lint passed.
- The preview remains on port 5219 and the same backend/account/session data.
  No develop/main merge, homepage change or release was performed.
