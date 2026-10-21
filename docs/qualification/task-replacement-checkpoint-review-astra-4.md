# Independent Astra checkpoint review

Reviewed core a7f2c86fd3131c58fbe90367968dbea5f1e0990b and GACT32044a387472b1495f60a24c862c6b9e4292abc3. Source review only; no runtime acceptance. Reviewer chat: Review task architecture plan; turn01a13715-b83c-79a0-9b55-a2b0f169a912.

**The R2 direction is a meaningful simplification, but I would fix four foundation defects before building further on it.** I reviewed checkpoint `a7f2c86f` against the approved removal baseline `4804dd6f`; GACT remains at `32044a38`.

1. **[P1] Input commitment can consume withdrawn or already delivered mail.**  
   [`task_history.py:183`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history.py:183) checks content identity but never checks withdrawal or prior acknowledgement. Stage an input, successfully withdraw it, then commit the staged input: it still succeeds. Two independently staged batches can likewise commit the same notification. Check eligibility under the existing writer lock, while preserving replay of the same committed input.

2. **[P1] Shutdown can cancel accepted-task adoption and discard its failure.**  
   [`task_client.py:184`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/tools/task_client.py:184) drains adoptions with an unshielded `gather`. Cancelling `close()` or context exit propagates cancellation into those adoptions. Additionally, `return_exceptions=True` discards failures from adoptions whose original caller has already departed. Retain accepted identity and surface recording uncertainty until custody is resolved. The current cancellation test releases adoption *before* closing, so it misses this case.

3. **[P2] The “rebuildable” input index is necessary to recover acknowledgements.**  
   [`task_history.py:265`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_history.py:265) discovers committed recipient inputs exclusively through `task_index` locators. Rebuilding that index loses discovery of existing commitments and makes acknowledged mail appear pending. Canonical input records must be discoverable independently; regenerate locators from them.

4. **[P2] Choice Questions can complete without a choice.**  
   [`questions.py:74`](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/questions.py:74) allows metadata-only or attachment-only replies to complete an option-only Question. Validate the required answer shape by Question kind before persisting completion.

The architectural improvement is real: the shared record layer stays passive, FastMCP owns task driving, and Question commands use the common record. **Keep that separation.** These corrections belong inside the existing writer and adapter; they do not require another registry, coordinator or recovery framework.

The stable dependency move is reasonable from source inspection. Add explicit coverage for FastMCP 4.1’s authentication ownership changes and 30-minute HTTP idle expiry. The installed environment still contains the beta versions, so existing static checks cannot establish stable-runtime compatibility. [Release notes](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.1.0)

Application wiring, workloads, authorization, conversation admission, migration and UI remain declared construction work—not additional defects in this checkpoint. I inspected the new foundation modules, corresponding tests and relevant ARC/SDK paths. **No files changed or tests/services run; this is source review, not runtime qualification.**

On your earlier question: compaction condenses conversation context so a long-running chat can continue; details may need checking again against source. [Official explanation](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide#compaction)


