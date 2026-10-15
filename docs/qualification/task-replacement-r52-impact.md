# R52 — one final-output recording handoff

Base: core `b16d1356833f56bad9d5d175bffe04dc64ed21fb`, unchanged GACT
`0a4ca5d5915a0add61cd5048b742161092468481` / marketplace
`1a9b8d0337217950a2b44c303a8d22547d52d756` and dependency tuple.

All six R51 focused cases passed individually, sequentially, one worker. This
includes the corrected stale-incarnation case, actual registered FastMCP storage
callable with a controlled provider failure, plan-wait Stop, obsolete approvals
and lost-flush/hook effects. These are regression assurance, not model qualification.

Astra accepted the three R50 corrections but found one new R51 blocker: a
visibility read before recording recovery could lose the original completed reply
on an RPC error. R52 removes that read and duplicate recovery construction from
finalization. The existing final-message recorder captures confirmation plus its
publication callback once. Normal, paused and failed finalization delegate the
same handoff. Its necessary epoch read is inside retained confirmation; original
minter visibility remains pinned. Intentional clear/rewind can withdraw deferred
publication. No new owner, worker or state machine.

Three fresh cases cover initial epoch-read outage, publication outage and
intentional clear after confirmed output. Required checks/review and affected
actual-model traces still apply to the resulting commit, not to its predecessor.
Full Q1–Q9/R1–R6, regression migration, exact-head CI and release acceptance remain
unfinished. No source-only verdict or old trace is counted as full qualification.
