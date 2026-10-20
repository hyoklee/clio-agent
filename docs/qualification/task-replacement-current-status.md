# Tasks replacement status

## Current disposition — 2026-10-20 19:25 UTC

**Initial implementation DONE. The completed fb tuple has green regression CI
and 30 scoped race passes. The new upstream/read-lock repair batch needs its own
CI and affected live acceptance. NO GO for release or daily installation.**

Latest completed live tuple: agent `fb2052275b900357dd96c9f896fa03b37ee141bb`; GACT `86214905b4fd99b184ac0b5b6e4e9506f6bd7bf6`;
marketplace `2c172233a9f895e41f7de121a3871d282a5fc0a2`. Develop through550bfd744
is integrated. Python3.14.6 / Core2.3.2 / FastMCP+tasks4.1.0 / MCP2.0.0 /
Docket0.26.2 / DSPy3.4.0 / Claude SDK0.2.159. Production Python digest:
`c61c5babe5aefc9c9b82ca823b1b57facc59f0bcb7857d6cc887a2344f9eb140`. R635 confirms57→d784→fb has identical
production/dependencies/schema/GACT; d784 changed one regression's observation
boundary, fb changed documentation/media. The current integration batch adds develop dcba0b857 (three upstream commits)
and changes two existing passive read locks, with two new constructed regression
cases. It introduces no owner, worker, registry or execution policy. Current-batch
CI and live acceptance are pending; earlier passes are not relabeled.

CI [39475590134](https://github.com/iowarp/clio-agent/actions/runs/39475590134)
completed **24 successful jobs**. All 12 XML reports:39,966 passed executions,
zero failures/errors and150 exclusions (50 per interpreter). Exclusions are not
passes. GACT86214905 CI/schema/both workspace runs passed. No local pytest/Vitest
loop ran. [Pages39478374630](https://github.com/iowarp/clio-agent/actions/runs/39478374630)
passed build/checks/browser tests; deployment and main-only uploads were skipped.

Completed fb-tuple race scopes: **30/30**. R1=5(R604), R2=5/R4=5(R594),
R3=5(R636), R6=5(scoped R597/R611/R622). R606: five actual-model pre/post recipient-input crash/restart repetitions PASS, same original assignment and Question, one input commitment, no replay.
The two failed R6 families remain failed despite accepted individual cases.
R611's five-second query timeout remains unexplained; R622 did not reproduce it.
R622 case5 model prose reversed command labels; canonical physical/handle outcomes
are retained separately and are not proof of accurate prose.

Claude Opus R592/R596 reviews executed after the human refreshed login. Both
finished and their disposable profiles were removed; original credentials/source
were preserved. These are scoped reviews, not a clean whole-candidate verdict.
Astra remains stopped.

The human explicitly deferred durable-provider recovery for this release on
2026-10-20. No surviving-provider-job claim is made. Available NDP downloads
and ordinary external MCP input/reconnect remain in release scope.

## Accepted scopes and unresolved failures

- R604 and R636 each passed 5 actual Codex/Luna repetitions, with frozen source,
  task prompt and auth. Services/supervisors exited0, all listeners/processes
  retired, exact roots removed567,580,276 and564,878,438bytes respectively.
- R605 failed health preflight before any model. It was physically retired and
 273,743,896bytes removed. R636 corrected only loopback request routing to match
  the successful R604 harness; no product/assertion/deadline changes.
- R574/R579 active-reviewer Stop is scoped accepted: reviewer running at Stop,
  physical retirement14.271seconds later, protected effect absent. The204 is an
  acknowledgement, not immediate physical retirement.
- R648 SPOTTER parent Stop PASS at fb: the real watcher held an unanswered
  Question; the parent's actual clearance-wait stack was captured before Stop;
  the parent worker retired and protected write stayed absent while watcher and
  Question remained active. Separate cleanup then settled all work, service exited
  0, all eight listeners were absent and 814,456,956 bytes were removed. R638's
  fresh-session dormant-watcher prerequisite failed and was cleaned; R648 used
  the normal mid-session arming wake. R599's quoted child-instruction model
  failure remains distinct; no additional engine policy was added to force it.
- R539/R543 Codex and R550 actual Opus demonstrated reading a cancelled child's
  transcript, messaging its original handle and linked continuation retaining
  17.25/34.5 context without operation replay. R516/R520 scoped discovery,
  recorded outcome and722-byte artifact reads after restart. They retain their
  original revisions and require explicit current-source impact adjudication.
- R632/R633 real-service Runs filtering, keyboard disclosure and exact cancelled
  child navigation/transcript access passed with no browser errors. Admission was
  closed, so no inference, fresh phone, Shift-click or UI cancellation proof is
  claimed. The selected1280x720 light-mode75,009-byte JPEG is on the website.
- HaikuR542/R546 remain failed model lanes, not authentication/capacity failures.

## Remaining gates

1. Finish the integration/read-lock batch, its CI and affected live acceptance.
   Adjudicate child-directed notice interpretation and the R611 responsiveness
   finding using actual evidence, without claiming the lock correction caused it.
2. Finish unaccepted races and final-source Q1–Q9/migration/uncertainty mapping.
   Earlier accepted scopes are not blanket acceptance of changed input paths.
3. Finish current-source coordination/summary/artifact coverage and deny/revoke
   before injection. Preserve separate owner/subscriber delivery and exact grants.
4. Q6 ordinary external MCP input/reconnect remains required. N12 durable-provider
   recovery is explicitly deferred by the human for this release; NDP streaming
   does not prove a surviving provider job and is not described that way.
5. Resolve remaining Opus concerns: shared-HTTP pre-task input identity, recovery
   with unrecorded adoption, passive mailbox contention and uncertainty display.
   Several conditional findings have source explanations, not universal verdicts:
   trusted child creation grants message-only return rights; veto holds differ
   from Stop; Shell strips human API credentials; native roots fail closed for
   unsupported elicitation. Do not report untested routes as passing.
6. Complete final integrated UI/source-impact review, required-exclusion
   disposition and accurate cleanup receipts before any publication decision.

## Custody and reporting

R604/R605/R636/R606/R638/R648 disposable roots are absent. Quiescent allocation24961 was closed
after physical cleanup; R640 records allocation24962 for remaining work. Every
new family records processes/ports/data before launch. Settle and remove its
disposable roots afterward. Preserve canonical product history, original auth,
daily Desktop, defaults, released pins, human files and every prohibited or
manual-only path. No archives, prohibited cleanup retries or installed changes.

This file, `task-replacement-acceptance.md` and
`task-replacement-live-experiments.md` are the canonical reporting set.
Bounded raw/scoped receipts live in the D qualification checkout under
`.pytest-runtime/static/`. Earlier checkpoints remain in Git history rather than
being duplicated as conflicting current sections.
