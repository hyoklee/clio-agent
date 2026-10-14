**NO-GO for production source `ad560ef2`: one P1 and seven P2 findings.** The later `7768ec40` commit does not change production source.

1. **[P1] Interrupted evidence-spawn acceptance cannot resume.**  
   `_new_assignment` first commits an assignment with empty `input_evidence`; the pins are persisted in a subsequent snapshot. If that second write fails, retrying the same invocation reaches `previous.input_evidence != pins` and rejects the original request as changed. The retained child has no delegation mail, and startup skips its idle assignment. Persist the pins in the initial assignment details before its first authoritative snapshot.  
   Locations: [initial assignment and subsequent evidence write](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:324), [retry rejection](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/conversation_assignments.py:285).

2. **[P2] New arrivals on an earlier task can starve later observation rows.**  
   Every page restarts at the first handle. With `row_limit=1`, if that task produces another change before each read, it repeatedly takes the slot while an already-available second task remains omitted. A pattern wait can consequently miss the second task’s existing match indefinitely. Preserve a scan position or observation round in the existing cursor so omitted members precede fresh changes on already-served members.  
   Location: [fixed handle order and row-limit check](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_observations.py:43).

3. **[P2] Pattern matching loses matches split by output pagination.**  
   `output_page` splits a logical chunk at the remaining character budget, but the waiter searches each returned fragment independently. For example, another row can leave two characters of budget, splitting `READY` into `RE` and `ADY`. Neither page matches, although the complete output already exists; after draining it, the waiter sleeps. Preserve bounded matching context across fragments, or avoid splitting a small logical chunk merely because the preceding row consumed its budget.  
   Locations: [fragment boundary](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_output_pages.py:69), [page-local matching](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:305).

4. **[P2] Timeout drops the pattern-search recovery metadata.**  
   The normal return includes `search_start_cursor` and `scanned_pages`. The `TimeoutError` path constructs a fresh response without either, after advancing past nonmatching pages. A caller receives an advanced cursor—often with no rows—without the promised information for recovering the undisclosed pages. Include the same search metadata on this return path.  
   Location: [timeout response](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_operations.py:321).

5. **[P2] Blueprint-only fanout entries still fail public schema validation.**  
   The callable supports omitted `agent` through `assignment.get("agent", "")`, but the nested schema still requires both `agent` and `task`. Released calls such as `spawns=[{"blueprint_id": "...", "task": "..."}]` therefore fail before reaching the common resolver. The new test invokes `.func` and supplies `agent`, so it misses this boundary.  
   Location: [required fanout fields](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:657).

6. **[P2] The released `spawned` array silently loses failed members.**  
   The released implementation returned one row per input member, including failures. The new response filters `spawned` to rows containing a handle, putting failures only in the new `outcomes` field. Existing consumers lose failure information and positional correspondence. Preserve all member outcomes in the legacy array; an additional canonical field is fine.  
   Location: [fanout response](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_declarations.py:595).

7. **[P2] The transcript records different delegation text from the committed model input.**  
   The new renderer commits the original assignment, quoted evidence and usable retrieval cursors. Afterward, `emit_injection` still receives the original staging JSON from `staged.injections`. The transcript therefore omits the actual evidence text and cursors while presenting itself as the exact injected content. Emit the included, committed rendered text.  
   Locations: [delegation rendering](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:425), [stale staging-text emission](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/clio_react_record.py:471).

8. **[P2] Result pagination doubles the bounded content in model context.**  
   Each page places the same fragment in both `result.preview` and `chunk`. At the default bound, that is 24,000 content characters plus metadata for a nominal 12,000-character page. Your proposed single-copy correction is appropriate; adapt the legacy preview envelope without duplicating the fragment.  
   Location: [duplicated fragment](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/task_result_content.py:103).

For item 8, **I did not find a model-path cursor-loss defect**: the built-in boundary preserves structured content, the recorder stores it, and the model projection serializes the complete object. The generic MCP spill limiter is not on this path. Transcript previews have their own clipping. [Built-in return](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/builtin_boundary.py:194), [model serialization](C:/Users/jaime/.codex/worktrees/agent-facing-async-tasks/clio-agent/src/clio_agent/gact/agents/recorded_media.py:102).

The committed-evidence proof, successor reference inheritance, task-local output provenance, and exclusion from source collection follow the agreed architecture. These findings can be corrected within those existing paths.

Read-only source review; I ran no tests, services or models. The reported focused passes do not constitute live acceptance.
