# Regular conversation controls: live acceptance

Date: October 10, 2026 (America/Chicago; recorded UTC timestamps extend into October 11).
Scope: regular conversations and user-created branches. Task/subagent lifecycle
semantics are deliberately excluded. UI companion: iowarp/gact-tui#591.

## Result

**43 service assertions passed on the corrected implementation**, with real
Codex `gpt-6-luna` responses, Python 3.14.6 and clio-core 2.3.1. The final browser
run passed ten workflow outcomes against that real service. No model response
or production route was replaced by a fixture. All example readings are fictional.

Evidence was retained at
`C:/Users/jaime/Documents/Codex/2026-10-11/conversation-controls-live-1/`:

- `final-baseline/verdict.json`: 17/17, with exact requests and complete transcripts.
- `final-extended/verdict.json`: 26/26, including continuation after restarting the service.
- `captures/browser-verdict.json`: header/message branching, independent follow-up,
  return navigation, reload, cancel/confirm rewind, resumed context, and branch survival.
- `captures/originals/`: full browser originals; the five focused images published
  in the website guide are in `site/src/assets/captures/docs-conversation-*.png`.
- `docs-rendered.png` and `docs-rewind-section.png`: rendered guide review. All five
  captures loaded and the desktop page had no horizontal overflow.

The permanent user guide is [Branch and rewind](../../site/src/content/docs/docs/branch-and-rewind.mdx).

## Defects found and corrected

1. A missing/foreign fork target silently copied the whole transcript. The route
   now rejects the target before creating a branch; malformed targets receive a
   typed validation error. Source history and the session inventory stay unchanged.
2. Context reconstruction discarded every trailing user message. A branch/rewind
   ending at an unanswered question therefore displayed information the model
   could not recall. Reconstruction now excludes only the current request by ID.
3. Copied messages retained their parent's `session_id`. The browser filtered them
   out of the branch even though the service's ledger contained them. Copies now
   belong to the destination session, with historical message/turn IDs preserved.

The rewind confirmation also explicitly states that the selected message remains
and existing files and artifacts are kept. The previously requested managed-session
fork prohibition is enforced in the service and both UI entry points; its policy
tests are separate from regular-conversation live acceptance.

## Observed semantics

| Case | Live result |
|---|---|
| Earlier assistant-message branch | Copied history ends inclusively at that answer. Parent's later filter is absent. |
| Header/full-tail branch | Entire current history copied; independent writable composer. |
| User-message branch | Unanswered selected question remains available to the next real model turn. |
| Parent and branch continuation | Filtered parent recalls mean 11; offset branch recalls 14. Neither writes messages to the other. |
| Nested branch | New +5 branch recalls 17; its +2 parent still recalls 14. |
| Empty branch | New empty writable conversation, no invented messages. |
| Rewind and repeated rewind | Selected message kept; later messages removed; next answer recalls baseline mean 12. |
| User-message rewind | Selected question remains visible and available to the next turn. |
| API `include_target: true` | Selected message is removed too. This is not the UI's default. |
| Cancel confirmation | No history mutation. |
| Active real response | Rewind returns 409 while the conversation is running. |
| Unknown rewind / missing or foreign fork target | Rejected without mutation or an extra branch. |
| Service restart | All four transcripts persist byte-for-byte; real continuations retain means 12, 14, 11 and 17. |
| Compaction then rewind before the checkpoint | Continuation returns to original method and mean 12. |
| Shared workspace/file references | References copied; subsequent file contents stay changed after rewind. |
| Parent rewind after branching | Existing branch remains at its independent continuation; verified in browser after reload. |

The file-content check used an explicitly authored synthetic file changed by the
acceptance driver. It proves reference/workspace behavior, not rollback of an
external application or remote side effect. Settings/policy inheritance and saved
A2UI preservation are additionally covered by focused backend tests; no new live
claim about external side-effect reversal is made.

## Validation and reproduction

Backend suites: `test_context_recovery.py`, `test_fork_and_search.py`,
`test_session_rollback.py`, `test_session_fork_policy.py`, and `test_session_kind.py`.
The combined regression run passed 72 tests; after the final context/copy fixes,
the two changed suites passed all 18 current tests. The final malformed-target
test also passed. There were no skipped tests. clio-core emitted native binding
shutdown leak diagnostics despite successful pytest exits; this acceptance does
not claim that those binding lifetime diagnostics are resolved.

UI: 30 focused Vitest tests passed; the updated confirmation's three tests passed
again. TypeScript build, scoped Oxlint, frontend size guard, Ruff, Pyright, and the
Python file-size guard passed. Two targeted fixture browser checks passed
(ordinary branch navigation and managed-worker action visibility); these are
explicitly distinct from the real-service browser test. Astro check and build
passed, including internal link validation.

Start `scripts/live_verification/conversation_control_server.py --out <new-dir>`
through `uv run python`. It owns an isolated service on port 17961 and a private
bounded clio-core. Use an authenticated Codex account; the acceptance selects
Luna. Then run:

```powershell
uv run python scripts/live_verification/conversation_controls.py `
  --out <new-dir>/baseline --workspace <new-dir>/workspace
# Write restart.request under <new-dir>, wait for server.json's count to increase,
# and wait for the service/provider to finish startup before continuing.
uv run python scripts/live_verification/conversation_controls.py `
  --out <new-dir>/extended --workspace <new-dir>/workspace --extend <new-dir>/baseline
```

For the browser, set `CLIO_ENDPOINT`, `CLIO_UI_PORT=5187`,
`CLIO_CONVERSATION_STATE=<baseline>/acceptance-state.json`, and
`CLIO_CONVERSATION_CAPTURE_DIR=<capture-dir>`. From `external/gact-tui/web`, run
`pnpm exec playwright test -c playwright.live.config.ts conversation-controls.spec.ts`.
Use `CLIO_LIVE_UI_REUSE=1` only for the UI server you deliberately started.
The spec waits for the destination transcript to hydrate before sending a follow-up.

The early diagnostic runs remain in the evidence directory, including incorrect
harness expectations for v2 response codes and startup readiness, and the product
failures that led to the fixes. They are not counted as passing acceptance.

## Resource ownership

No worktree or large dependency environment was created. Existing Python/UI
dependencies were reused. The service wrapper owns its server and private core,
supports `stop.request`, and has a one-hour default maximum lifetime. At completion,
stop the two owned UI/docs development servers, reap the private core, preserve
compact transcripts/captures/traces, and remove private runtime state and the small
temporary pytest dependency cache. Do not remove another task's state or processes.
