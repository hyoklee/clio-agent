# Task waits and transcript continuity — 2026-10-12

## Cause

The retained parent called `wait_tasks` with `return_when="all"` and
`timeout_s=0`. Zero requests an immediate snapshot. The returned receipt had one
pending child, no results and `timed_out: true`. The parent then wrote from its own
README/manifest evidence; that text was not a returned child audit.

Omitting the timeout or passing `null` commits to an unbounded wait. That runtime
behavior remains unchanged. The shared tool description and runtime instructions
now explicitly distinguish the two and direct agents to wait when their answer
depends on the child result.

The follow-up default declaration explicitly publishes `timeout_s: null` and
`return_when: all`. The native schema wrapper preserves the public default when
adding nullability. Read-only inspection of the real declaration, both before
and after observer wrapping, confirmed that only `tasks` is required, the default
is JSON null, and the tool/parameter descriptions state the unbounded default.
The callable continues to use Python `None`; zero remains an explicit status poll.

## Changes

- Recorded zero-time waits show **Check task status**, pending-task and collected-
  result counts, and a neutral clock. Raw arguments and results remain available.
- Delegation appears inside the normal tool bundle, with its recorded agent name,
  expandable assignment/result, and child-conversation link.
- An interim answer keeps a clickable child row with assignment and current state
  visible beneath it. Pending children suppress the completion footer.
- Question/tool boundaries and later automatic continuations do not produce empty
  completion footers. Zero-token placeholders are omitted.
- Adjacent Markdown thinking headings have a visible separator. Controller
  injections use a compact disclosure, with exact details retained inside it.
- Injections now sit inside the expandable activity collection. Its summary names
  received results, reminders, and goal/loop/schedule events alongside tool work.
  Consecutive standalone harness entries join the next response without crossing
  a human-message or conversation boundary. Their original message anchors remain.

## Verification

No pytest, Vitest or Playwright test suites were executed, at the user's direction.
Focused regression cases were added for wait presentation, delegation and thinking
headings. Python Ruff and scoped mypy passed; frontend type checking, production
web/offline builds, scoped Oxlint, and presentation/component/file-size guards passed.
The native desktop debug build and agent wheel build passed.

The retained conversation was reviewed directly in the browser: its old wait
receipt now shows the pending count, its thinking heading has the separator, its
delegate row names the actual agent (`main`), and its child link opens the exact
child conversation. No model prompt was submitted during this review.

A separate, explicitly labelled **UI preview · Sample conversation and running
state** exercised production transcript components with generic sample data.
Manual browser review covered running, permission-needed and completed child
states, child-button dispatch, and a 620-pixel viewport without horizontal page
overflow. Running/permission states had a visible progress row and no completion
footer; completion removed the row and restored the footer. This is rendered UI
state evidence, not a new scientific or live agent execution.

Local preview: `task-wait-ui-preview-2026-10-12.png` in the task's Codex
visualizations directory. It contains no private dataset content.

The follow-up `injections-activity-preview-2026-10-12.png` shows one expanded
collection containing received results, thinking, a command, and a reminder in
that order. Manual browser review confirmed both injections are descendants of
the collection, exact-details content remains readable, and a 620-pixel viewport
has no horizontal page overflow. A result awaiting the next response retains its
own **Received results** activity disclosure. Focused placement/summary regression
cases were added and existing injection/compaction expectations updated; suites
remain unexecuted as requested.

The retained OPAL transcript was then reviewed with the grouping change: its
activity summaries include received results/reminders; expanding the result
collections revealed five injection rows, all inside the activity timeline and
none outside it. No new agent turn was started.

The question-resume follow-up keeps consecutive assistant segments under one
CLIO sender header, retaining their message IDs and content anchors. A new human
prompt, conversation change, or non-injection system message starts a separate
response. The selected answer is shown once when its transport text merely repeats
the option label; additional human comments remain visible.

In the retained question exchange, direct browser review found one recorded
"Yes, rerun and verify" answer, no duplicate Comment, and no new sender header on
the resumed segment. Injection, thinking, and tool disclosure arrows shared the
same measured horizontal coordinate; static activity icons also aligned.

The labelled `question-continuation-alignment-2026-10-12.png` preview uses production
components with generic sample data. It shows the answered question followed by
the reminder and resumed command under one CLIO header, with no completion footer
while the command is running. Manual review covered injection expansion, exact
details, thinking expansion, a new-human-message boundary, and a 620-pixel viewport
without horizontal overflow. Regression cases were added but not executed; scoped
Oxlint, frontend type checking, and production web/offline builds passed.

The next reasoning-row refinement removes the visible **Thinking** prefix. A
complete single-line thought uses a static icon-and-text row with wrapping, no
button, no hover action, and no disclosure arrow. A passage with additional text
keeps its disclosure. Its heading remains regular weight and uses the same font
and foreground color when open or closed. Literal underscores and recorded source
identity are retained.

Manual browser review of the labelled `reasoning-plain-rows-light-2026-10-12.png`
and `reasoning-plain-rows-dark-2026-10-12.png` previews confirmed zero buttons/arrows
on the complete short thought, a functional disclosure for the longer passage,
matching computed font family/color and weight 400 in both states, and no overflow
at 620 pixels. Selecting the static thought still resolved its exact recorded
source coordinates. These are generic sample previews of production components.
Regression cases and affected disclosure fixtures were updated; suites remain
unexecuted at the user's direction.

The retained live OPAL transcript was reviewed without submitting a prompt. Its
38 rendered reasoning entries were complete single-line thoughts: all 38 used
static rows, with zero reasoning disclosure buttons and no visible Thinking
prefixes. Longer-passage expansion was reviewed separately with the labelled
generic preview above.

Injection rows now read icon, **Injection**, then the event description, followed
by the right-aligned disclosure arrow. The todo event is named **Todo list
reminder**. The type label stays with its description on the left. Dot separators
were removed from the transcript formatting changed in this work, including
adjacent-heading summaries, task-wait summaries, subagent labels, and tooltips.
The recorded message/tool content remains unchanged.

Manual browser review of `injection-prefix-light-2026-10-12.png` and
`injection-prefix-dark-2026-10-12.png` confirmed the requested prefix order,
matching icon/arrow alignment, functional expansion and exact details, no dot
separator in the sample transcript, and no horizontal page overflow at 620 pixels.

## Todos and detailed wait receipts

Checklist calls now use **Update Todos**, with todo counts, Todo list/changes
disclosures and todo wording in removed-item accessibility labels. The backend
declaration and presenter agree; a narrow rendering adapter updates older
`write_todos` receipts without changing their recorded contents. Async work
continues to use the term task.

Wait titles now name **all** or **any** and show the requested public handles.
Selections and wait policy appear while a call is running. A zero-timeout call
is labelled **Check all tasks** or **Check any task**. Expanded receipts show the
deadline/poll policy, each pending handle as a historical snapshot, each returned
result body and any collection errors. Failed results/errors get a degraded
receipt with visible diagnostics. A completed subagent result says **Turn ended**,
retaining the child's output rather than inferring that its scientific assignment
succeeded. Original arguments and result bodies remain in technical details.
Compact disclosures no longer repeat their header counts or the wait handle list
before the individual outcomes.

Manual browser review used actual product components with clearly labelled,
generic sample receipts. `todos-wait-details-light-2026-10-12.png`,
`todos-wait-details-dark-2026-10-12.png` and
`todos-wait-details-narrow-2026-10-12.png` cover Todo transitions, an in-flight
unbounded all-wait, an immediate poll with no results, an any-wait with collected
text plus a pending task, and task failure/unknown-handle diagnostics. Expansion
and technical-details controls worked; no browser page errors occurred, no dot
separator was present, and document width stayed 620 at a 620-pixel viewport.

The retained OPAL parent was also inspected read-only in the browser: all visible
checklist controls used Update Todos, wait titles included all and actual handles,
and the retained zero-timeout receipt expanded to its named pending snapshot.
Stored messages were not rewritten and no new agent turn was submitted.

Scoped Ruff/format, Python type checking, frontend lint/type checking, the web
and offline builds, presentation/component/file-size guards and the native
desktop build passed. Relevant Python and UI regression cases were updated or
added, including disclosure rendering, but test suites remain unexecuted at the
user's direction. This is presentation verification, not renewed qualification
of wait execution or the OPAL investigation.

## Run command and output sections

Run results now have a Command section and an Output section within one terminal
surface. Previously the command/head preview and a saved tail each received
separate preview/disclosure machinery. The saved tail now shares the Output
preview and its expansion control. Saved-file metadata/actions and process exit
status remain inside Output. Long commands expand independently. Run disclosures
use these bounded sections without a second, outer scrolling box hiding their
controls. Exact recorded text, ANSI handling and paginated content remain intact.

Manual browser review of labelled generic previews covered short output, long
commands, saved large output, command/output expansion and the selected-file
callback. Light/dark and 620-pixel captures are saved as
`run-command-output-light-2026-10-12.png`,
`run-command-output-dark-2026-10-12.png`, and
`run-command-output-narrow-2026-10-12.png`. No page errors occurred or horizontal
document overflow appeared. A retained saved-output call was inspected read-only
in the actual parent transcript: one Command section, one Output section, one
saved-file row inside Output, one output expansion control, and no nested outer
scrolling. Its Open full output action opened the recorded stdout file in the
Preview tab. No command or model turn was submitted. No retained paginated Run
was available in the inspected transcript, so live pagination was not exercised.

Frontend type checking, scoped lint and unchanged presentation/file-size/reuse
guards passed. Existing lifecycle regressions were updated to assert the shared
output section and a terminal primitive case covers recorded excerpt rendering;
test suites remain unexecuted at the user's direction.

## Installed state

### Work summary, completed todos and section indentation

The Work evidence panel no longer repeats its todo count in a generic Session
work row. Its summary keeps useful active goal/loop or scheduled-work information
without repeating the adjacent Todos count. A completed-only todo list shows
Show completed directly under the category; the redundant No current todos
paragraph is omitted. That paragraph inherited a generic accordion's prose
margin and caused the reported extra gap. Compact evidence sections now share
one content indentation, and the completed toggle uses the row's horizontal
padding. Evidence accordion content also uses its natural height: the shared
primitive's fixed measured height clipped rows when the nested completed list
expanded after the category had opened.

Manual browser review used production components with labelled sample data. It
covered four completed todos, expanding/hiding completed rows, two current and
two completed todos, and an active goal alongside the checklist. The child and
current todo rows had the same left coordinate; the count appeared once. The
goal summary retained its title without a duplicate count. A 620-pixel popup
expanded all four completed rows inside its visible bounds without horizontal
document overflow. No page errors
occurred. Captures are `work-completed-todos-light-2026-10-12.png`,
`work-todo-alignment-dark-2026-10-12.png` and
`work-completed-todos-narrow-2026-10-12.png` in the existing visualization
directory. These are component previews, not a native end-to-end run. A mutable
preview query fixture did not refresh correctly; fresh immutable fixtures were
used for the final mixed-status and active-goal review.

Frontend type checking, scoped lint and existing file-size/reuse/presentation
guards passed. Regression coverage was adjusted for completed-only lists and
todo-summary suppression while preserving active goals. No test suites or OPAL
model turns were run.

The desktop build passed and was installed in CLIO Develop. All conversations
were idle or already in error before restart, and the delegated child task was
terminal. After restart, health returned HTTP 200, the retained parent remained
idle, and all four recorded runs were completed. Build metadata records
`work_inventory_spacing_fix: true`. The agent wheel is unchanged. These UI
changes remain local and unmerged. The preview browser and frontend server were
stopped; Cargo cleanup removed 6.3 GiB of temporary build files.

### Compact question list in the tracker and Work

The question tracker now opens on hover as well as click, keyboard activation
and touch. It uses the installed Base UI popover's hover support instead of
custom pointer timers. Each pending human question has a clipped preview that
opens its answer dialog, a go-to icon when its loaded transcript source is
available, and a separate disclosure arrow for the full text. Long lists scroll.

The same question list is included in the Work evidence panel and full Work tab,
fed by the workspace's existing live interaction inventory and answer handlers.
Resolved questions leave both surfaces. Full Work retains questions while its
other inventory loads or reports an error. Its question area is bounded so a
long list does not displace the remaining work controls.

Manual browser review used labelled sample data and the production tracker,
evidence panel, Work tab and answer dialog. Twelve questions exercised hover
without stealing typing focus, moving into the popup, individual expansion,
source-link navigation, opening the second question's answer dialog, keyboard
open/Escape/focus restoration, hover dismissal, transfer into full Work, and live
resolution. Touch opening/expansion at 390 pixels and the 620-pixel layout fit
without horizontal document overflow. Light, dark, narrow and Work-tab captures
are named `questions-hover-expanded-light-2026-10-12.png`,
`questions-hover-dark-2026-10-12.png`, `questions-hover-narrow-2026-10-12.png`, and
`questions-work-tab-light-2026-10-12.png` in the existing visualization directory.
No page errors occurred. This is component-preview evidence, not a native-app
end-to-end run. No real question response or OPAL model turn was submitted.

Frontend type checking, scoped lint and existing file-size/reuse/presentation
guards passed. Question-mode and transcript-navigation regressions were updated,
including hover/disclosure and live questions in Work. Test suites remain
unexecuted at the user's direction.

The desktop build passed and the question-list update was installed locally in
Develop. All workspaces were checked immediately before restart; conversations
were idle or already in error and background tasks terminal. Build metadata
records `question_list_hover_and_work_fix: true`. The installed agent wheel is
unchanged. GitHub was checked live: agent PR #1723 and UI PR #598 were merged to
develop on 2026-10-12. Remote develop remains at 4cd92841 (agent) and dbe5903c
(UI). The subsequent working changes, including this question-list update,
remain uncommitted on their local branches with no PR; installation is not a
merge to develop.
After restart health returned HTTP 200 and the retained parent stayed idle.
The review browser and frontend server were stopped, and Cargo cleanup removed
5.6 GiB of temporary build files.

### Evidence layout restoration after side tabs

The selected Data/Work layout is now a saved preference. Losing the transcript
gutter hides docked evidence without clearing that selection. Closing the side
tab or restoring viewport width brings the selected panels back. Explicitly
hiding evidence still selects none. Opening a file or full view from evidence
preserves the layout, and automatic hiding does not move focus to its launcher.

Manual browser review used labelled sample data, the production evidence popover,
and its actual DOM measurement/ResizeObserver behavior. It covered Data alone,
Work alone and both panels; top-level and nested collapsed sections; opening a
file from evidence; side-tab open/close; narrow/wide resizing; saved selection
after reload; and explicit dismissal retained after side-tab changes and reload.
Tool calls remained collapsed by default. No page errors or horizontal overflow
were observed. Light, dark and side-tab captures are saved as
`evidence-layout-restored-light-2026-10-12.png`,
`evidence-layout-restored-dark-2026-10-12.png`, and
`evidence-layout-side-tab-2026-10-12.png` in the existing visualization directory.
This was a browser component preview, not an automated native-app acceptance run.

Frontend type checking, scoped lint and unchanged file-size/reuse/presentation
guards passed. Regression coverage was updated for gutter loss/restoration and
side-canvas open/close with each layout. Suites remain unexecuted at the user's
direction. OPAL runs remain paused.

The desktop build passed and was installed in Develop. All workspaces were
checked idle or already in error with terminal background tasks immediately
before restart. After restart, health returned HTTP 200 and the retained parent
remained idle. Build metadata records `evidence_layout_restoration_fix: true`.
This change updates only the desktop UI; the installed agent wheel is unchanged.
The review browser/server were stopped, and Cargo cleanup removed 5.6 GiB of
temporary build files.

### Evidence disclosure preferences and current todos

Evidence menus now keep explicit expanded/collapsed choices in a small local UI
preference, including Data/Work, their evidence categories, connected sources,
and the full Work view. Tool calls start collapsed. Categories that temporarily
disappear retain their preference. Storage failures keep the in-memory choice.

The evidence menu, Work view and transcript checklist results share todo status
icons and group completed items behind Show completed. Counts describe remaining
work: 3/5 current means two completed and three unfinished. Removed checklist
entries remain recorded separately and do not count as current work. Status-change
history remains available in the accessible icon explanation and raw receipt.

Manual browser review used labelled sample data and production components. It
confirmed default collapsed tool calls, explicit opening and closing retained
after dismissal/layout changes, top-level Work collapse retention, completed-todo
expansion retention, and an expanded Tool calls category retained across browser
reload. Reviewed light/dark and 620-pixel screenshots are named
`evidence-todos-current-{light,dark,narrow}-2026-10-12.png`. The final preview had
no page errors and no horizontal overflow at 620 pixels. Early preview setup
attempts used mismatched Vite React module URLs; those were corrected before
review and are not product-runtime failures.

Frontend type checking, scoped lint and unchanged reuse/file-size/presentation
guards passed. Focused regression coverage was added/adjusted for disclosure
remounts, absent categories, current counts and completed-todo grouping. Test
suites remain unexecuted at the user's direction; OPAL runs remain paused.

The evidence/todo desktop build passed and was installed in Develop. All
workspaces were checked idle or already in error with terminal background tasks
before restart. After restart, health returned HTTP 200 and the retained parent
stayed idle. The Cargo cache was cleaned (5.6 GiB) and the frontend review server
was stopped. Build metadata records `evidence_disclosure_preferences_fix` and
`current_todos_focus_fix`. The later task-link feedback was deferred at the user's
request to finish this change first; it is not part of this installed build.

The new desktop and agent wheel are installed in the existing CLIO Develop
environment. The service restarted, returned HTTP 200 from `/v1/health`, and the
retained parent was idle. Before restart, its four recorded tasks were terminal.
The installed Python module contains the new presentation code. Build provenance
is recorded in `D:\CLIO-Develop\source.json`; these are local branch changes,
not a merged release.

Installed desktop SHA-256:
`f6c246934a6b498c2041d573934f1459568bf3b0575705ed0eaca12691f6ec00`.
The later connection-switcher refinement is recorded in
`connection-switcher-2026-10-12.md`.
The subsequent operation-bundle continuity and child-return folding refinement
is recorded in `transcript-continuation-grouping-2026-10-12.md`.

The Command/Output desktop rebuild passed and is installed in Develop. After
restart, health returned HTTP 200 and the retained parent remained idle. This
refinement changed only the desktop UI; the installed agent wheel is unchanged.
The Cargo target directory was cleaned and the temporary frontend review server
was stopped. Build metadata records `run_command_output_sections_fix: true`.

The Todos/wait-detail desktop build and agent wheel are installed in Develop.
All workspaces were checked idle/terminal before restart; health returned HTTP
200 afterward and the retained parent stayed idle. The installed wait-presenter
module's SHA-256 matches the source file. Cargo cleanup removed another 5.6 GiB;
the temporary frontend review server was stopped. Build metadata records
`todos_and_wait_details_fix: true`.

The question-continuity/alignment desktop rebuild passed and was installed locally.
All workspaces were checked before restart: parent and child conversations were
idle, the default-workspace conversation was already in error, and recorded async
tasks were terminal. After restart, `/v1/health` returned HTTP 200 and the retained
parent remained idle. No new agent turn was submitted.

The plain-reasoning-row desktop build also passed and is installed in this Develop
environment. The restarted service returned HTTP 200; the retained parent stayed
idle. The Python agent runtime was unchanged for this UI refinement.

The injection-prefix and separator refinement also passed scoped lint, type
checking, web/offline builds, and the native desktop build. It is installed in
Develop; after restart health returned HTTP 200 and the retained parent was idle.
Cargo cleanup removed its 5.6 GiB cache. No test suites or agent turns were run.

Cargo cleanup removed 6.3 GiB after the initial installation and 5.6 GiB after
the injection-grouping rebuild, then another 5.6 GiB after the question-continuity
and alignment rebuild. The plain-reasoning rebuild's cache cleanup removed another
5.6 GiB. The restarted service returned HTTP 200 and the
retained session remained idle. The previously policy-blocked
generated Tauri configuration remains; no bypass was attempted. OPAL execution
remains paused. The revised agent instruction has not been qualified by a fresh
model run in this UI-only pass.
