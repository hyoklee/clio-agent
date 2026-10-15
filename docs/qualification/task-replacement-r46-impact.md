# R46: serialize accepted-input transcript repair

R46 adds the existing Core writer boundary around the existing selected-message
repair. Human acceptance and online/startup/replay repair now serialize their
transcript read/merge/write. It replaces no execution owner and adds no new state,
queue, driver or deadline. This addresses Astra's demonstrated R45 lost-update
race; Claude's scoped R45 source GO is not treated as overriding that defect.

Scoped Ruff/format, Linux Mypy for the changed production file and unchanged
removal/size/class/hidden-swallow guards pass. New source review and affected
runtime regression/live checks remain required for R46.

On the original frozen R45 tuple, actual Codex/Luna completed one idle Question
cycle and one post-Stop Question cycle: immediate handles, independent reads,
pending status, automatic answer wakes and collection of the original answers.
The service then exited normally without recovery intervention; registered owned
processes and private listeners were absent. Original authentication hash remained
unchanged. The selected receipt `task-replacement-r45-live.json` contains real
invocations, handles, statuses, bounded transcript excerpts and normalized hashes.
This clears the specific R44 healthy-projection shutdown failure on R45; it does
not qualify the whole matrix or the later R46 tuple.

Separately, three exact R45 regression cases passed individually/sequentially with
one worker: original acceptance replay after projection failure (30.74 seconds),
healthy Question recovery (14.17 seconds), and cancellation-settlement arrival
(14.20 seconds). None skipped. They are regression assurance, not live acceptance.
Core binding reference warnings appeared at interpreter exit; F03 resource-growth
qualification remains outstanding. No guards, assertions or budgets were relaxed.

Both R45 disposable-root removals were automatically rejected as "blocked by
policy"; neither ran. The exact family and short IPC roots are manual-only, with
no retry/bypass. R44's rejected roots and all older boundaries remain intact.
No volume free-space or completed-cleanup claim is made. Reviewer custody is
settled; bounded receipts are retained without review exports or archives.
