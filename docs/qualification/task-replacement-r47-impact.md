# R47: repair one accepted message in its existing transcript owner

Both R46 reviewers rejected online whole-transcript replacement. Astra's separate
read-only architecture trace recommended a narrow idempotent operation in the
existing transcript owner: preserve current raw atoms under the existing lane lock
and generation writer, then update JSON/resident projections without replacing
concurrent output. Boundary-only repair would miss paused sessions and acknowledged
busy feedback. R47 implements that replacement; it adds no task store, scheduler,
delivery acknowledgement or producer-wide lock.

`transcript_projection.ensure_accepted_message` reads the current canonical lane
under its existing scope lock. It inserts/completes only the exact approved human
message, preserving every unrelated raw atom and existing relative order. Partial
messages, envelopes and retractions are not reconstructed from a resident cache.
The existing generation switch confirms the canonical change before cache writes.
An already complete durable message causes no generation rewrite. Ambiguous or
conflicting identities and retracted input fail explicitly rather than overwrite.

The optional MessageStore copy inserts under its existing lock; the resident view
inserts in place rather than swapping the list. All three representations use the
same first-later-timestamp placement rule and retain stable equal-time ties. Cache
presence alone never proves durable repair. Startup, segment preparation and REST
replay share this operation; selected busy human/composer input is repaired before
recipient-input commitment. Repair itself acknowledges nothing.

The legacy whole-view replacement option is removed from acceptance and its sole
caller/protocol. A transcript identity without confirmed Core acceptance now returns
an explicit conflict, preserving history instead of rewriting it or inferring a
safe new execution. Normal Core-first acceptance retains its existing append path.

The physical splice still copies a lane through the existing atomic generation
algorithm. Reads are proportional to that session's transcript; F03 measurements
remain necessary before a performance claim or further optimization. No new index,
checkpoint framework or competing execution authority is introduced.

Fresh regression construction covers raw partial/retraction preservation, a final
append interleaving, file-on/off projections, cached-only and partially durable
input, idempotent retry and pointer-switch failure with pending input retained.
Typed input fixtures now include the actual accepted message identity and resident
view. Assertions, timeouts, budgets and ratchet baselines are unchanged. These cases
remain unexecuted until separately recorded; they cannot qualify the implementation.

R47 requires independent source review, affected regression assurance and fresh
actual-model busy-feedback/Question/shutdown requalification. Earlier R44/R45 live
receipts do not qualify this replacement tuple. All exact rejected cleanup roots,
protected human files, installed-state and native/private boundaries remain intact.
