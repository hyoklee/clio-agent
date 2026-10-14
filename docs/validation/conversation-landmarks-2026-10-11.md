# Saved conversation landmarks

Scope: human navigation in regular CLIO conversations. A mark does not change
message content or the model's working context.

## Behavior

- The existing slim message rail shows a bold title and a bounded excerpt.
  A user's prompt previews its following answer where available. These are
  recorded excerpts; no new model request or generated summary is involved.
- Mark from a rail preview or the message action row. Only a service-acknowledged
  save fills the bookmark. Failed saves report an error and preserve saved state.
- The marked list jumps to the original message, including in narrow layouts.
- Session metadata stores per-message mark deltas under `message_marks`.
  Updates merge under the session store's lock to preserve other clients' marks.
- REST and SSE expose marks through the explicit public metadata projection;
  unrelated internal session metadata remains private.
- Forks copy marks only on copied messages, independently. Rewind and undo
  prune discarded messages' marks. Raw exports/imports preserve marks; HTML
  review renders saved marks as read-only indicators.

## Acceptance evidence

Evidence root:
`C:/Users/jaime/Documents/Codex/2026-10-11/conversation-landmarks-live/`.
The live browser uses the real service, Python 3.14.6, clio-core 2.3.1 and
recorded real Codex/Luna responses about fictional calibration readings. It
imports that recording through the service API. No production route or model
response is intercepted; this navigation acceptance makes no fresh inference.

`captures-complete/browser-verdict.json` records eleven successful outcomes:
preview, preview marking, cross-client SSE, message-action marking, reload,
service restart, marked-list jump, export/import, fork boundaries and independent
marks, rewind pruning, and a narrow marked outline without horizontal overflow.
Full originals accompany the focused guide images. `docs-verdict.json` and
`docs-rendered*.png` retain rendered guide review.

The first browser run found that GACT 0.3 omitted saved marks. The projection
now exposes only the approved public keys, with a regression test for REST
and SSE. Subsequent visual review reduced empty space in marked lists and
corrected title clipping. One restart assertion initially compared JSON key
order rather than values; the recording showed marks survived correctly, and
the assertion now compares the actual map contents.

## Checks

- Core: 14 mark tests plus 44 existing session/fork/rewind/export/projection tests.
- UI: 37 focused tests; repository: 3 transport contract tests.
- Python Ruff and scoped mypy; TypeScript checks for web/core; web lint and
  repository ownership, reuse, presentation and file-size guards.
- The Sessions and modes guide includes the actual controls, two reviewed
  screenshots, persistence semantics and the recorded-example qualification.

Runtime services are explicitly stopped after acceptance. Compact transcripts,
verdicts and capture originals are retained. Automatic approval review rejected
deleting the disposable runtime and type-check caches after resolved-path and
service-stop checks; 831 MiB remain on C: (see `cleanup.json`). No worktrees
were created for this change.
