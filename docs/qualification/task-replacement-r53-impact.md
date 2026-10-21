# R53 — withdrawal and obsolete approvals

Base core `13ef4092ab167f36ddd94298bb5d1d9b2eddae3f`; GACT/marketplace and
dependencies unchanged from R52. The containing commit identifies this candidate.

Astra's R52 source finding: withdrawal returned like success and retained live
assistant fields. The existing recorder now returns an explicit confirmation
boolean and independently retires only the matching original live slot/transcript
on withdrawal, even if its waiter was stopped. Normal finalization stops before
goal processing; paused finalization returns a distinct withdrawal result and
cannot publish a plan approval. Deferred and immediate paths share that contract.

Fable's whole R51 review accepted the task/session/Question architecture and
previous corrections except one boot blocker: restoring an unposted approval
whose original input was superseded could repeatedly raise from gate admission.
The Question owner now recognizes a typed obsolete-gate decision, records the
historical Question cancelled with that reason, and continues restoring other
Questions. Presentation clears only a projection still pointing at that exact
obsolete handle. It does not apply the old decision or reinstall a gate. Core
recording failures and unrelated validation errors remain errors.

Fresh cases cover original visibility/publication outage, clear/rewind withdrawal
and live-slot retirement, goal/plan caller withdrawal, and idempotent obsolete
approval restoration alongside an independent open Question. R51's six focused
cases passed; new affected cases remain unexecuted at this source commit.

No registry, scheduling owner, universal state machine or compatibility fallback
is added. Source review and focused assurance remain separate from actual-model
qualification. Full regression migration, Q1–Q9/R1–R6, final CI and publication
remain outstanding. The two-hour implementation deadline is unchanged.
