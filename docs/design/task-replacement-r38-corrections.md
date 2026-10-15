# R38: finish the shared startup boundary

Combined R37 source acceptance is NO-GO. Astra identified two specific defects;
actual Claude Code Fable supported the architecture with explicit unread source
areas and non-blocking observations. Neither result establishes qualification.

| Finding | Existing replacement owner | Bounded correction and regression |
| --- | --- | --- |
| A child's own attention is excluded by parent/subscriber authorization. | Core session mailbox and conversation startup producer | Use trusted same-session hook input for the child's startup warning. Retain parent/subscriber attention publication and their authorization. Assert committed warning context without a self-subscription; partial parent publication still recovers. |
| Generic startup failure can falsely confirm settlement, allowing historical restart or later mail to create a successor. | Conversation failure recording, admission and assignment creation | Retain an uncertain nonterminal observation when startup cleanup lacks proof. Check the same existing SessionStore receipt at admission/promotion and before assignment creation. Cover current failed startup and older terminal rows, explicit restart, later input and reconstructed metadata/Core indexes. No new worker, gate store or acknowledgement workflow. |
| Unused delegation metadata writer survives deletion. | Removal manifest/guard | Remove delegation_return.py after confirming no production or test imports. Add its module to the existing static denylist. Current assignment lineage and result publication remain the owners. |

The Fable observation about message_intents.py is classified rather than treated
as a mutable-store defect: the file contains only historical PendingSteer,
QueuedMessage and error payload types. MessageIntentStore is absent and forbidden
by the guard. This remains historical decoding/public payload data, without
reserve, update, claim, consume, dispatch or persistence policy. Legacy tests
still importing the deleted mutable store must be rewritten, not given a fallback.

F03 retains all identified history-scan, staging and whole-session-write costs as
measurement obligations. Fable's lingering-attention/known-cleanup wait concern
also remains a specific source/regression follow-up; no speculative polling or
new reconciliation owner is introduced. The required behavior is already N10/N11:
unknown settlement can return uncertainty; known progressing cleanup keeps waiting.

R38 is initial construction. Regression bodies and every required live gate remain
unexecuted. Source acceptance requires another independent review of the corrected
tuple, including previously unread source paths. The execution checkout stays on
the frozen R37 review tuple while construction continues in the source writer.
