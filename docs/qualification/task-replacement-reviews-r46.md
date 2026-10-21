# R46 source review and correction boundary

Both reviewers give source NO-GO for `1914da40` / GACT `faddba47` / marketplace
`43af7a01`. The existing Core task-writer lock now serializes repair with human
acceptance. It does not serialize assistant finalization or A2UI transcript
appenders. REST replay can still rebuild a stale whole transcript while one of
those owners appends, removing the new row from memory/file/Core. Rewriting the
whole atom lane can also collide with content streamed before finalization.

Astra completed turn `01a1409c-480b-7ac3-bdad-405db98151b4` in the existing review
chat. Claude Code used actual `claude-fable-5-1`, session
`e7f933f5-d17f-4347-b907-6edfd7a49170`, PID 50748, exit 0. Neither review ran tests
or production qualification. Their review exclusions remain separate from source
acceptance; native/provider/bridge/migration/UI coverage is not inferred.

Claude additionally identified an unverified startup-order question around
file-off transcript reconciliation and the similar pre-existing replacement in
legacy acceptance. These are recorded without treating an unconfirmed ordering
hypothesis as a demonstrated failure. The root correction must remove online
whole-transcript rewriting, rather than add locks to every task/output producer.
Independent read-only architecture advice is requested before another source
correction.

The exact original-acceptance replay regression passed again on R46 in 29.93
seconds, individually with one worker and no skip. This is regression assurance;
it neither clears the demonstrated race nor qualifies R46. R45's two actual model
Question cycles and unassisted shutdown remain evidence of their frozen revision.
