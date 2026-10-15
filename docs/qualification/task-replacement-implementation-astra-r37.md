# R37 independent Astra source review

Reviewed core `51c056fef7a13a80446ceefa06b4a49d139abf06`, GACT `416601856a1e828f658fd59fe6bc5bc4f1129f05`, marketplace `999fdafa9d0f1214e3f9f4f98a6d4d4a8f8f3751`. Source review only; no behavioral qualification.

**Source: NO-GO — two actionable defects remain.** Architecture/removal remains supported for core `51c056fe`, GACT `41660185`, marketplace `999fdafa`.

1. **[P2] The resumed child does not receive its startup uncertainty warning.**
   [note_startup_interruption](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/conversation_assignments.py:110) writes `attention` mail addressed to the child, referencing its own assignment. But [SessionMail._authorized](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/session_mail.py:382) permits this notification only for the parent recipient or an explicit subscriber. A child is neither by default, so staging and input commitment exclude the warning even though initialization permits execution.

   Use the existing trusted same-session input route for the child’s warning; retain attention publication for parents/subscribers and preserve their authorization checks. Verify the warning actually reaches committed model context without a self-subscription. The new interruption test already attempts this assertion, but remains unexecuted.

2. **[P2] Already-failed startup bypasses the new settlement guard on restart.**
   The guard is called only from [_cancel_subtree](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/conversation_controls.py:565). A startup exception can leave `creation_hook_state="started"`, while [_finish_segment](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/conversation_assignments.py:355) records the assignment as failed with confirmed settlement. [restart](D:/Libraries/Documents/projects/clio-agent-task-qualification/src/clio_agent/gact/conversation_controls.py:361) skips cancellation for that terminal assignment and creates a successor, which then fails initialization again. Later eligible mail can likewise create a successor through `_admit`.

   Apply the existing startup settlement check at the shared conversation admission/successor boundary. Missing cleanup proof must remain uncertainty rather than becoming confirmed settlement through generic failure handling. Extend the regression beyond an active assignment: fail startup first, then attempt explicit restart and later-message admission, including reconstructed-store recovery.

The earlier corrections otherwise hold in source: complete-lane creation lookup, discovery outside the task writer with acceptance rechecks, known-unattempted versus interrupted startup receipts, and reuse of existing process-tree ownership.

The broader design still preserves stable sessions with finite linked assignments, shared authorized intersession messaging/observation/waits, and asynchronous Questions collected through those waits. I found no newly introduced scheduler, execution registry or competing delivery authority. The removed production owners remain absent.

**Qualification remains pending independently of these defects.** The regressions, migration, F03 measurements, exact-head CI and required live gates are unexecuted. Static checks do not establish acceptance. I made no edits and ran no tests or services; the D checkout remained clean at the reviewed commit.
