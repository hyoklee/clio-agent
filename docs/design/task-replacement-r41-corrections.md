# R41 review corrections and retained regression migration

Parent core: `afe65d08`; GACT `41660185`; marketplace `43af7a01`.

Both R40 independent reviewers support the replacement ownership/removal design.
Their combined source verdict is NO-GO until these bounded corrections are reviewed:

- Astra: retire a durably observed inline invocation after its RPC/observer exits,
  including when cancellation uncertainty remains nonterminal. Preserve that
  uncertainty; retiring a stdio observation process is not remote cleanup proof.
  The same two-server regression now includes cancellation-before-reply.
- Actual Claude Code Fable: route Shell/Download/Indexing cancellation to their
  existing native owner before adoption or provider-continuation backend binding.
  The captured kind is immutable and requires no Core content read during an
  outage. Keep backend-based routing for other native work. No new owner is added.
  A constructed actual native-queue case holds adoption while one worker is
  occupied, calls the shared control and requires never-started settlement.
  This tests dispatch; actual Core-outage qualification remains separately required.

Migrate the retained storage REST acceptance/cancellation cases from the removed
journal to confirmed TaskHistory and the canonical query/result APIs. Read every
bounded result page before parsing, retain real bytes/hash and manifest counts,
and verify queued cancellation through native attempt receipts. Separate source
roots make this a worker-queue test rather than a same-source concurrency conflict.

Migrate the three tool metadata cases to current declarations. Default catalogs
exclude compatibility aliases; every executed shared/spawn/workflow operation has
a row. Keep the independent instrumentation, title and guard checks.

Scoped Ruff/format and Linux Mypy pass on six changed Python files. Behavioral
execution remains deferred. The import-only audit was incomplete by construction:
the expanded static attribute/name audit identified 51 candidate files at R40,
including 15 absent from the import-only list. Classify ownership and preserve
their lessons rather than deleting findings mechanically. The storage and tool
metadata migrations address two candidates; a full collection claim is unavailable.
F03, migration twice, CI, real UI and Q1–Q9/R1–R6 remain pending.
