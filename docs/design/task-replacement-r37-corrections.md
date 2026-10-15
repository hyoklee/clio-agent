# R37: recover observation startup and keep discovery outside task locking

Both independent R36 reviews support the R2 architecture and reject source
readiness. The combined adjudication confirms three bounded corrections. Required
behavior, Q1–Q9/R1–R6, migration, F03 and CI remain in scope and unqualified.

| Existing owner | Correction | Required regression |
| --- | --- | --- |
| ARC reader/provenance observer | Use the existing complete semantic-event lane reader when recovering creation publication. | Small chunk capacity, lost publication reply, same-process/cache-evicted/reconstructed-store recovery; one creation event and one fanout across the complete lane. |
| HookDispatcher/SessionStore/conversation engine | Distinguish positively unattempted cancellation from interrupted observation effects. Restore pending only for the former. Preserve uncertainty and prohibit hook replay for the latter, while allowing stable-session continuation after required physical settlement. Carry uncertainty through confirmed Core context and existing publication. No new mandatory human acknowledgement or abandonment requirement. | Cancellation before any invocation, after visible effects and between hooks; pause/resume retains the assignment; restart links a successor in the same session; no inference before retirement and no effect replay. |
| Existing child preparation and submission | Resolve/validate target configuration off-loop outside the global writer. Re-enter for current authorization, identity, admission, evidence, depth and immutable-input checks before acceptance. Already accepted identities must remain reusable without rediscovery retargeting them. | Held discovery with independent query/Question/control progress; cancellation/configuration change during preparation; simultaneous identical submissions. |

The hook adapter's current process kill is best-effort. Thread retirement alone
cannot prove its subprocess tree settled. Reuse the existing Shell process-tree
ownership algorithm (`TaskProcessTree` and fresh spawn options) at the hook's
process-acquisition boundary, and preserve uncertainty if cleanup is not confirmed.
This is workload cleanup within the existing adapter, not a task kind, driver,
scheduler, registry or recovery service. Never reconstruct ownership from a PID.

F03 measures existing input-history scans and whole-session-file writes before any
optimization. Cohesion and file-size concerns do not justify another broad
partition. Update stale removed-owner comments without changing public contracts.

Current construction implements all three bounded corrections through the listed
existing owners. Startup uncertainty uses the ordinary Core attention/input path;
parent publication precedes the child's final preparation receipt. Hook cleanup
uses the existing OS process container and retires the original communicator
before another pipe drain. Discovery retains an atomic parent configuration and
rechecks it, the owning assignment and admission when acceptance resumes.

Fresh regression construction covers before/during/between-hook cancellation,
same-assignment resume and linked restart, missing physical settlement, a lost
parent-publication reply before child input, complete-lane creation recovery,
held discovery with independent controls, changed admission/configuration and
concurrent identical preparation. Real subprocess cases exercise cancellation,
explicit hook timeout and a descendant outliving its parent. These cases remain
unexecuted. No behavioral, native/model/browser qualification or installed-state
change ran. Scoped construction checks are recorded separately; they do not
establish source readiness or acceptance.
