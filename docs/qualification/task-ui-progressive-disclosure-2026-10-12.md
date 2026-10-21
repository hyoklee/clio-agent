# Task activity UI review

GACT's shared task surface now presents compact, clickable rows. The Work
popover counts a durable child task once, keeps long assignments behind row
disclosure, and puts backend identity behind a separate technical disclosure.
Conversation and canvas actions navigate to the recorded child. Lifecycle
confirmations identify the task and consequence first; full assignments are
available through **View assignment**.

The actual-service receipt uses core runtime
`fa294aff15870aa3cb64e4ac769bb4248ceba012` and GACT production code
`ff8da5b658c023f7ac7efab4607c152e87e66e2b`. No core runtime code changed for this
UI review. The core feature branch records the GACT documentation/capture commit
that contains this exact production tree.

See GACT's [review and actual screenshots](../../external/gact-tui/docs/screenshots/task-progressive-disclosure/README.md).
Final `codex-ui-progressive238` uses actual Codex/Luna-created Subagent and Shell
work on an isolated Linux/Python 3.14.6/Core 2.3.1 service. Desktop/phone review
passed keyboard disclosure, exact assignment/session identity, five pause/resume
cycles while accepted Shell work continued, dismissal, subtree cancellation,
physical worker absence and linked restart without operation replay. All eleven
captures were inspected; no page/HTTP errors or overflow were observed.

The receipt is retained at
`D:/Libraries/Videos/clio_recordings/2026-10-07-release-recovery/mcp-agent-tasks/task-ui234/qualification239.json`.
It includes frozen source/build identities, handles, model/backend outcomes,
capture hashes and ended-owner custody. All new private Core/cache owners are
retired. When writing the final cache receipt hit Errno 28, its existing archive
was moved to `C:/Users/jaime/.codex/recovery/mcp-agent-tasks`, checked against the
native archive hash, CRC and every member, and retirement resumed without replay.
Earlier UI-run cache archives were likewise relocated with hash receipts. No
recovery archive was deleted and no free-volume measurement is claimed.

Twenty-seven focused UI cases passed individually/sequentially; the six affected
confirmation cases passed again after the final refinement. Scoped lint/format,
TypeScript, six unchanged guards and both production builds passed. CI is recorded
per current PR head; historical CI and excluded tests are not new-head acceptance.

This completes the changed UI review on the stated route. The wider Tasks
qualification remains incomplete for the previously recorded protected
native/confinement, unavailable inference/relay and oversized-SSE routes. Earlier
failed UI attempts are preserved. Merge, release and installation are separate.
