# R54 — serialize obsolete-gate projection release

Base core `9e94f0eead3015077f039855eb4a3740f7358951`; GACT/marketplace/dependencies
unchanged. Astra accepted withdrawal handling but identified an obsolete cleanup
check/update outside the shared Core writer lock. This commit holds the existing
`history.serialized()` lock across checking the exact gate and clearing its
projection. A delayed cleanup cannot clear a concurrently installed replacement.

Two fresh tests had setup defects: their fixture did not install QuestionCommands,
and the obsolete header lacked a valid captured approval binding. Setup now uses
the real owner and a structurally valid binding that no longer matches the current
assignment. Invalid content is still a validation error, not an obsolete decision.
No assertions, timeouts, budgets, guards or production validation are weakened.

The frozen R53 service demonstrated actual Codex/Luna native Shell acceptance in
323 ms, independent file read/query/observation and expired wait before the 45 s
work settled, then result collection and actual completion-file hash. Question
idle/post-Stop checks are in progress. This is affected predecessor evidence, not
full R54 qualification; the changed obsolete-approval race needs its own check.
Other Q1–Q9/R1–R6, migrated regression suite, CI and release acceptance remain open.
