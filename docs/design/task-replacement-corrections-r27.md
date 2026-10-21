# R27: close the reviewed input and control boundaries

Both source reviews of core `8f40aa8d` / GACT `557aecd3` returned NO-GO.
Fable supports the architecture in principle and judges the replacement
genuinely simpler. Astra's adjudication confirms two additional defects and
rejects changing the preserved any-wait contract. These reviews do not approve
the corrections below or establish runtime acceptance.

| Confirmed defect | Correction in the existing owner/boundary | Removed behavior | Fresh proof |
| --- | --- | --- | --- |
| Revocation can filter a notice out while committing its entire tool observation | Validate every collected member; retain trusted read identities across the short MCP call and reauthorize even subsequent reads; reject incomplete observation acknowledgements in the confirmed writer | Silent collection filtering and proof from an empty/subset selection | Single/mixed results, before/after prior delivery, writer rejection and model-context redaction |
| An unanswered cancellation RPC can hold the serial recovery worker | Bound cancellation RPC delivery in the existing SDK adapter; owners keep uncertainty and physical settlement separately | Unbounded cancellation RPC delivery | Actual native task survives an unanswered control RPC and settles only after release |
| REST ignores the returned result cursor | Forward the optional cursor to the existing result reader | Repeated first-page response | Exact Unicode reconstruction through the actual ASGI route |
| Permanent ownership/validation failure is treated as a recording outage | Validate supported ownership before control effects; enter recording recovery only when the writer is held | Permanently invalid cancellation reconciliation and false acceptance | Historical unavailable execution, with and without a Core hold |
| Parent uncertainty survives a descendant returning to known cleanup | Conversation owner clears only the resolved attention episode after rechecking current member evidence; it still waits for cleanup | Stale uncertainty short-circuiting waits | Unknown → known pending cleanup → confirmed subtree settlement |

Live and replayed cancellation use one membership-selection algorithm. No new
worker, execution state machine, database or recovery queue is added. The
permitted owner-local reattachment entries remain. Historical continuation
custody is validation, and shipped GACT aliases remain passive projections.

`return_when="any"` continues to return an independent member error immediately
while retaining valid pending work. Baseline `5475042f` explicitly used
`settled or errors`; R2 did not authorize changing it. A focused public-contract
case records this preserved behavior.

The R26 boundary family has eleven selected cases passing after a test-only
off-loop assertion correction. The original failure is retained. The retained
history case measured 1,004 tasks, 6.631 s replay, two exact-query snapshot reads
and nine active-query reads. Unrelated-session growth, final integrated races,
CI and Q1–Q9 remain separate required gates. Review packages include the plan,
acceptance ledger and committed correction maps; reviewer reports are omitted
from the independent Fable package.
