# Transcript continuation grouping, 2026-10-12

The retained parent session `sess_6fe306b2a851` has 10 stored messages and
`next_cursor: null`. The desktop transcript repository requests the full message
ledger without a page limit. The reported split does not require a new session.

Two recorded `delegate.completed` parts describe the same child run
`task_2f24afe6ba09`: `live_handoff_fd110ff5cb21` on the initial assistant message
and `live_handoff_dec3f51e4c14` on its result continuation. Stored-handoff
reconciliation closes the original launch while result delivery records the
return again on the consuming turn. The UI previously displayed both records.

The question answer is a correlated native resume envelope for
`ques_405a2d38db4c`, with an answered interaction linked to invocation
`call_5a3ef42fec0a`. Earlier response continuity suppressed the repeated sender
and intermediate footer, but each message still constructed its own operations
disclosure. This produced a second collection after the answered question.

The UI now folds duplicate terminal child returns at their latest recorded
position and joins adjacent operations across internal continuation messages.
The first disclosure identity stays stable as the continuation streams. Public
answer text, actual human prompts, model boundaries, interruptions, and explicit
full-detail views retain their positions. Original ledger records are retained.
The virtualizer keeps the owning activity row mounted for a streaming continuation.
Correlated native async-answer envelopes follow the same continuity projection.
This does not change the runtime's current blocking/async question API contract.

Manual browser review used the actual saved transcript and its resolved
interaction, without submitting any new model turn or OPAL command. It confirmed:

- All 40 recorded tool calls render once, with 40 unique invocation identities.
- The child return renders once. The completed-handoff-only collection after
  the interim answer disappears.
- The answered question, reminder, rerun and verification share one disclosure.
- A preview-only pending-to-answered transition invokes its local answer handler
  once, rejoins one collection, and has no completion footer while waiting.
- A preview of a correlated async answer also retains one collection and one
  human prompt.
- An 84-message sample including the retained continuation enters virtualization;
  both the streaming anchor and owning activity row remain mounted, the collection
  is visible and reports ongoing work, and no completion footer appears.
- Light/dark and 620-pixel views were inspected; the narrow view has no horizontal
  page overflow. The final preview has no page errors.

Captures and the read-only snapshot are retained under
`C:\Users\jaime\.codex\visualizations\2026\10\08\01a11d11-9c09-7051-915b-2d70dba80656`:

- `transcript-child-return-folded-2026-10-12.png`
- `transcript-question-continuation-dark-2026-10-12.png`
- `transcript-question-continuation-light-2026-10-12.png`
- `transcript-question-continuation-narrow-2026-10-12.png`
- `transcript-continuation-streaming-long-2026-10-12.png`

Frontend type checking, scoped lint, whitespace, file-size, component-reuse and
presentation guards passed. Regression cases were added for duplicate handoffs,
multi-turn activity placement, preserved boundaries and async answer envelopes.
Test suites remain unexecuted at the user's direction. Browser replay evidence
is distinct from native-app acceptance and fresh model execution.

The final web/offline and native desktop builds passed and were installed in
`D:\CLIO-Develop\clio-desktop.exe`. Immediately before restart, the parent and
child sessions were idle, the default-workspace session was already in error,
and all four background runs and the child task were terminal. After restart,
health returned HTTP 200 and the retained parent remained idle. The installed
agent wheel was unchanged. Local changes remain uncommitted and unmerged.

Installed desktop SHA-256:
`f6c246934a6b498c2041d573934f1459568bf3b0575705ed0eaca12691f6ec00`.
Build provenance records `continued_activity_grouping_fix` and
`duplicate_child_return_fold_fix` in `D:\CLIO-Develop\source.json`.
The browser preview and Vite server were stopped after review.
Cleanup removed 6.3 GiB from the verified disposable Cargo target directory.
