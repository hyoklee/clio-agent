# NDP catalog disclosure and responsiveness

The live preview uses UI worktree `gact-pele-diagrams-1786` on port 5219 and
backend `clio-ndp-source` on port 8209. This change edits the actual picker;
no fixture catalog, UI response interception or generated screenshot was used
for the following browser checks. No model run or scientific analysis is claimed.

## Cause and changes

The API search route already delegates synchronous catalog work through
`asyncio.to_thread` in `routes/connected_storage.py`. Public CKAN queries use
`rows=30` and offsets. The 6,235 figure is a total count, not the number of
dataset rows fetched or rendered initially.

The actual first page contains **30 datasets and 4,941 resource records** in a
1,267,403-byte response. Previously all dataset rows started open, mounting all
resource checkboxes and full descriptions. This was a substantial browser
rendering workload despite catalog pagination.

The actual picker now:

- Starts unfiltered browsing with titles only; closed details are unmounted.
- Shows three description lines on opening, with full-text expansion only when
  layout measurement detects overflow.
- Opens its independently collapsible Resources section and renders ten resources
  initially; Show more reveals ten at a time.
- Starts search results and selected-resource views expanded, preserving selections.
- Skips constructing the text search index while browsing without a search query.
- Reports the number of dataset rows currently displayed, alongside the catalog
  total when available; Show more datasets retains incremental fetching.

## Actual runtime observations

`D:/CLIO-Develop/ndp-picker-20261019/live-query-timings.json` contains direct HTTP
timing receipts and `measure.py` reproduces them against the existing backend.
The blank search returned in 4.021 s; water and snow returned in 1.519 and 1.543 s.
Baseline health requests took 662-799 ms. Health requests during the blank search
completed in 624-889 ms, rather than waiting for the entire query. This small
sample supports concurrent request handling; it is not a general load benchmark
or evidence that upstream query latency has been removed.

The real user's Attach flow was opened at:
`http://127.0.0.1:5219/workspaces/ws_fd8714446f0d/sessions/sess_fe140dd3c979`.

- Initial catalog DOM: 30 dataset buttons, zero resource checkboxes and zero
  description paragraphs.
- Actual 100 Year Flood Zone description: 60 px at 20 px line height when
  collapsed; expanding the full description gives 260 px. Full text is retained.
- Selected the actual GeoJSON resource, collapsed and reopened its Resources
  section, and verified the selection remained checked. Then cleared it.
- Opened the actual 2015-2017 State of Utah Lidar Acquisition dataset, containing
  1,000 resource entries: initially ten checkbox controls, then twenty after Show
  more. Its other resource controls were not mounted.
- A real snow search expanded 30 displayed datasets with 142 resource checkboxes;
  clearing the search returned to 30 collapsed rows and zero checkboxes.
- Show more datasets fetched the next real page and displayed **60 of 6,235**
  datasets, still with zero resource checkboxes mounted while all rows were closed.

Actual screenshots are retained in the evidence directory as `browse-real-ui.png`,
`browse-real-ui-final.png` and `expanded-real-ui.png`. The existing Attach dialog still scrolls vertically
at 1280x720; this change does not claim a complete dialog-layout redesign.
No selection was attached, no dataset bytes were downloaded, and the backend,
existing accounts, Core daemon and user conversations were not restarted.

## Automated checks

Eighteen focused picker/row tests pass, covering selection custody, search,
catalog paging, keyboard expansion, independent resource disclosure, resource
paging, long-description disclosure and disabled selections. Web TypeScript,
web lint, formatting, file-size, component-reuse, presentation-override and icon
checks pass. Browser fixture selectors were updated for title-only buttons;
the fixture browser suite was not rerun. Live browser review above uses actual
catalog data rather than that suite.

Changes are local to the running preview; nothing was merged or released.
