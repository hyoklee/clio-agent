**GO for initial production-source qualification** of core `af8e4b6c`, GACT `ce993164`, marketplace `9257bba`. I found no remaining concrete blocker in this correction review.

The three findings are addressed:

- **Stop:** captures the reservation before yielding, rechecks automatic promotion after preflight, and binds retirement to the original reservation. See [session_cancellation.py:24](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/routes/session_cancellation.py:24).
- **Evidence snapshots:** busy delivery uses the existing recorded-snapshot resolver, which still refuses inaccessible references. See [messaging.py:585](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/messaging.py:585).
- **Batching:** actual rendered text/media—including the initial head—is counted; the sole oversized-human exception preserves intact media; overflow remains pending. Commit still rechecks revisions, withdrawal, eligibility, and authorization. See [session_mail.py:127](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/session_mail.py:127).

**No design objection to the test migration boundary.** Classify individual scenarios, preserve independent algorithm assertions, and map retained behavior to replacement coverage. A removed-module import is evidence of coupling, not justification for deleting every test in that file. The inventory’s 1,037 tests must remain an affected-file count, not an obsolete-test or failure count.

I inspected source and authored regressions only. No edits, tests, imports, or services were run. This approval permits proceeding to test migration and qualification; **CI, fresh behavior/model/UI evidence, Q1–Q9/R1–R6, and release acceptance remain outstanding.**
