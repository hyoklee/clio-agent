# Science ledger: default delegation, fork, the science log and two published studies

Rows follow [delegation-fork-science-plan.md](delegation-fork-science-plan.md) and its [Addendum A](delegation-fork-science-addendum-a.md). A row passes only with recorded evidence: test names and results, commands, session ids and task handles, saved transcripts and exports under `.cloud-run/<row>/`, and for UI work the screenshots that were read. Status is `pending`, `passed`, `failed` or `blocked`. A live row records whether its prompt was tool-directed (mechanism only, not evidence of agent judgement) or a plain request (judgement).

## Decisions

| ID | Decision | Source | Evidence | Status |
| --- | --- | --- | --- | --- |
| FD1 | The science log is written through the task layer's one writer. Each entry is a `science.entry` semantic event in the event log of the session that wrote it (its branch), recorded by `TaskHistory` with the same confirmed-write path as `task.observed`. Study-wide lookups are derived `task_lookup` records under a `sci.` prefix, built and re-checked the way `gact/task_index_records.py` builds task lookups; a study's member sessions are its task tree (`TaskIndex.members`). Nothing is replayed at boot. | Phase 0 | `gact/task_history.py` `_record`/`confirm_write`; `gact/task_index_records.py` (lookup rows are derived hints re-checked against event logs) | pending |
| FD2 | Every branch of a study reads the whole study's entries while it runs and writes only its own branch. The method skill tells a branch to form its own hypothesis and design before reading the others, and Evidence says when it relied on another branch's result. Replaces "none while running". | Addendum A | | pending |
| FD3 | Reframes need no approval by default. A study that wants approval sets `approve_edits`, which also gates forks inside the workflow. | Plan defaults | | pending |
| FD4 | A budget is optional: one shared pool per study when the root Question declares one, charged by Observations; an Observation that would overspend it is rejected with `budget_exhausted`. | Plan defaults | | pending |
| FD5 | Fork naming: `<step>~<n>` in workflows; `<title> (fork)` for conversations. | Plan defaults | | pending |
| FD6 | An agent's fork of a root conversation is shown in the left panel like a person's fork, with the agent as author. | Plan defaults | | pending |
| FD7 | Roles and forks run on the caller's model unless the spawn names one. | Plan defaults | | pending |
| FD8 | The showcase studies run on a Sonnet-class Claude model chosen from `list_models` at run time and set on the root session; children, steps and forks inherit it. | Plan defaults | | pending |
| FD9 | An invalid guess or an out-of-range setting is a tool error. | Plan defaults | | pending |
| FD10 | A session is delegated when `session_kind` is `agent` (spawned work, flow members, workflow steps). Conversations, branches and side sessions are root sessions, because a person reads them. Fragment `session` scope is applied when the session's prompt is built, not in the resolution, because a `self` child shares its parent's exact resolution and digest. | Phase 0 | `gact/session_kind.py`; `gact/spawn_context.py` (`self` pins the parent's digest); `tests/test_plugins/test_resolve.py::test_a_fragment_scoped_to_root_or_delegated_sessions_reaches_only_those`; live: `GET /v1/sessions/{sid}/agent` for `sess_2682c110b724` (root: rendering and A2UI list present, `delegation.child` absent) and its `explore` child `sess_90e2aeee7331ecf30ace3e5a58037f10` (`session_scope: delegated`, rendering absent, `delegation.child` present) | passed |
| FD11 | `effects="read"` runs the child with the server-owned approval profile `READ_ONLY_SIDE_PROFILE`, so the side session's read-only gate (`is_read_only`; deny reason `read_only_side_session_denied`) and its withheld spawn and workflow controls apply unchanged. | Phase 0 | `gact/side_sessions.py`; `gact/spawn_context.py` (`read_only` sets `READ_ONLY_SIDE_PROFILE` at child creation); live `sess_2682c110b724`: the `explore` child's `fs_write_file` was refused with "This session is read-only (a side conversation or a read-only role)", `.cloud-run/p1smoke/turn-sess_2682c110b724-*.txt`, and `probe.txt` was not created | passed |
| FD12 | Fragments scoped `session: root`: `core.rendering` (with its generated A2UI catalog list) and the A2UI view fragments gated on `create_a2ui_surface`: `visuals.evidence`, `visuals.figures`, `earthscope.views`, `abaqus.views`, `appl-core.views`. | Phase 0 | `grep -rl create_a2ui_surface` over marketplace `ai.iowarp.clio/prompt/*.md`; `plugins/builtin/core/ai.iowarp.clio/prompt/rendering.md` (`when: {session: root}`); marketplace `628af3f` | passed |
| FD13 | Marketplace cleanup verdicts, one per generic-looking subagent (table below). | Phase 0, Phase 1 | marketplace `628af3f`; `grep -rn data_analysis_expert external/clio-agent-marketplace --include=*.md --include=*.py --include=*.json` finds nothing | passed |
| FD14 | A child's Question needs no new delivery: `ask_user` in a child records the Question with `owner_session_id` the child and `attended_session_id` the root conversation, the root's question list covers its task tree, the root shows it under "Agent needs your attention" named after the child, and the person's answer reaches the child. No change made. | Phase 1 | Live (mechanism, tool-directed): root `sess_c640783ecd03`, child `sess_99cf763e56b6ff577f77ba73ebf157ad`, Question `task_45525b9a…`; `GET /v1/sessions/sess_c640783ecd03/questions?status=pending` lists it; `.cloud-run/shots/p1-q-2-root-with-child-question.png` (read); answered "Blue" in the UI (`p1-qa-2-after-answer.png`), root reported "The child's answer was blue" (`.cloud-run/p1smoke/q.out`) | passed |
| FD15 | Measurement exports are Parquet, with CSV on request. In an isolated run they go to the caller's node folder; otherwise to `<workspace>/.clio/science-log/<session_id>/`, deleted with the session. | Addendum A | | pending |
| FD16 | File hashes come from the artifact registry (`TransformRecord` used/generated edges keyed by `call_id`), recorded when the call that wrote the file completes. No command text is parsed. | Addendum A | `gact/artifacts/transforms.py`, `gact/artifacts/versions.py` | pending |
| FD17 | Workflow isolation is off unless the run is started with `isolate: true`; the method skill starts studies isolated. | Addendum A | | pending |
| FD18 | A fork in an isolated run clones its forker's folder copy-on-write where the filesystem supports it (`FICLONE`, `clonefile`, ReFS block cloning) and copies otherwise, never hard-linking; the method is recorded on the fork. | Addendum A | | pending |
| FD19 | Shared plugin MCP servers (`fleet` profile) are not confined per node. Declared output paths are grounded and checked against the node's folder at CLIO's tool boundary; a write a server makes on its own is not confined. | Addendum A | `gact/artifacts/designation.py` `ground_output_paths` | pending |
| FD21 | A read-only role keeps every native tool that declares itself read-only. `observe_tasks`, `wait_tasks`, `get_task_result` and `load_skill` now declare it (they change nothing outside the caller), so `explore` can load a skill and collect a background fetch. `ask_user` is not read-only: a read-only role reports open choices in its result instead of asking. | Phase 1 | `gact/task_declarations.py` (`read=True`), `gact/agents/skill_runtime.py` (`read_only=True`); `gact/agents/session_tool_posture.py` keeps only declared read-only natives | passed |
| FD22 | An omitted `agent` in `spawn_agent_task` or a `spawn_agents_parallel` item spawns `self` with `agent_flow: react` (D14): the caller's exact resolution, delta and model, never its selected flow. | Phase 1 | `tests/test_arc/test_spawn_tool_compatibility.py::test_single_and_batch_spawn_share_child_preparation_and_preserve_names`, `tests/test_arc/test_task_compatibility_review.py::test_public_fastmcp_fanout_keeps_failed_positions` | passed |
| FD23 | `derive="caller"` resolves a role to the caller's resolved plugins pinned to their exact versions (`=x.y.z`) and marketplace, skipping packs so a member the caller's delta removed stays removed; `derive` with `plugins`, an unknown `derive` or an unknown `effects` is a typed load error (`subagent_derive_conflict`, `subagent_derive_invalid`, `subagent_effects_invalid`) that `plugin check` reports. | Phase 1 | `tests/test_plugins/test_resolve.py::test_a_role_derives_the_callers_plugins_and_runs_read_only`, `::test_derive_and_effects_are_validated_at_load`; `clio-agent plugin check external/clio-agent-marketplace` → 55/55 passed | passed |
| FD20 | Work happens on branch `claude/delegation-fork-science` in clio-agent, gact-tui and the marketplace; draft PRs target `develop` in all three (the marketplace pin `d0d92981` is on its `develop`). | Phase 0 | `git log origin/claude/delegation-fork-science` in each repository | pending |

### FD13: subagent verdicts

| Subagent | Plugin | Prompt | `structured_outputs` | Reached by | Verdict and reason |
| --- | --- | --- | --- | --- | --- |
| `critic` | deep-research | 1,953 words | `workflow_state` | the `deep_research` flow | Keep: carries the typed audit contract the flow branches on |
| `evidence_critic` | factorio | 105 words | none | `evidence_researcher` (spawns it) | Keep: re-fetches sources with `web_search`/`web_fetch`, which its caller `evidence_researcher` does not carry, so a `review` derived from the caller could not check sources |
| `independent_reviewer` | factorio | 135 words | none | factorio's `coordinate-scientific-work` decision criteria | Keep: runs cheap checks with `shell_bash`, which the read-only profile denies; its `REVISION_REQUIRED`/`READY_FOR_SCIENTIST_REVIEW` verdict feeds the coordinator |
| `data_analysis_expert` | scientific-method | 210 words | none | factorio decision criteria and README, scientific-method `plugin.json` | Deleted (marketplace `628af3f`): its prompt restates the scientific-method skills it loads (`statistics`, `uncertainty-quantification`, `data-visualization`); a default spawn of a science agent carries those skills and the shell |

## Phase 0: what today's export shows

Sessions in `.cloud-run/phase0/`, exported through the conversation menu (`scripts/cloud/checks/export_session.mjs`) and opened offline with the network blocked (`scripts/cloud/export_check.mjs`). Prompts were tool-directed: these are mechanism runs.

- `sess_c57c2fffdf4a` ran a council (`task_c62b5da0…`), an arena (`task_1505568c…`) and a workflow (`task_e06f9450…`) with steps `draft`, `check` (editor, `approve_edits`) and `nested` (a council). Exports: `.cloud-run/phase0/exports/sess_c57c2fffdf4a.{html,zip}` (15.8 MB, 14.6 MB).
- `sess_8932d888ff64` (sent through the web UI) showed an A2UI bar chart and ran a three-level subagent tree (`task_d6f57f6c…` → `task_b04a642a…` → `task_ffefa759…`). Exports: `.cloud-run/phase0/exports/sess_8932d888ff64.{html,zip}`.

What the offline viewer does not show, against the export design's table:

| Work | Today offline | Screenshot |
| --- | --- | --- |
| A flow run (council, arena, workflow) | The run card reads "Not started yet": the run view (`GET /v1/sessions/{sid}/tasks/{handle}/flow`) is not recorded, so there is no railroad and no step state | `.cloud-run/shots/p0-flows-offline-2-conversation-activity.png` |
| A subagent and a subagent tree | Every descendant's transcript is appended flat after the root's, headed only "Parent" with the assignment. No child title, agent, model or handle; no link from the spawn to the child or back; no tree | `.cloud-run/shots/p0-flows-full-2-part1.png`, `-4-part3.png` |
| A workflow's edits | Nothing: proposals, approval Questions and stalls are part of the unrecorded run view | as above |
| A fork | No agent forks exist yet; a person's fork is exported as its own session with no link to its origin | n/a |
| A study | Not built yet | n/a |
| A2UI from a built-in catalog | Renders in Results (the chart) | `.cloud-run/shots/p0-tree-offline-3-results.png` |
| A2UI from a plugin catalog | Not exercised; the export does not record the session's resolved plugin catalogs | n/a |

Building the export also needs the offline renderer (`external/gact-tui/web` `pnpm build:offline`); without it the menu reports "The offline review renderer could not be loaded".

## Scenarios

| ID | Scenario | Prompt | Passes when | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | Factorio spawns with no `agent` | Mechanism | The child's resolution digest equals the parent's, and it calls an Abaqus tool | | pending |
| F2 | The standard agent delegates to `explore` | Mechanism | A write tool is denied with the read-only reason; findings come back | | pending |
| F3 | `planner` output goes to `run_workflow` | Mechanism | The workflow starts unchanged and its steps run | | pending |
| F4 | Compare a root and a delegated prompt in the prompt view | Mechanism | Rendering and A2UI guidance appear only in the root; `delegation.child` only in the child | | pending |
| F5 | A child raises a Question | Mechanism | It appears in the root session attributed to the child, and the answer reaches the child | | pending |
| F6 | An agent forks a root conversation | Mechanism | A new conversation appears in the left panel with the copied history and origin; the original continues | | pending |
| F7 | A delegated child forks | Mechanism | The parent's wait covers both, and the result lists both by handle | | pending |
| F8 | A workflow step forks mid-run, with `approve_edits` | Mechanism | The approval Question appears; after approval the fork is drawn beside its step, the dependent waits on both, and its input lists both answers | | pending |
| F9 | Restart the server after the fork in F8 | Mechanism | No duplicate fork; the run resumes on the same handles | | pending |
| F10 | Forks beyond **Forks per task** | Mechanism | `fork_limit_reached` is returned and nothing is created | | pending |
| F11 | A small study in a third domain, asked as a plain question | Judgement | Entries of every type appear in the tree; every claim cites entries; a citation of a missing entry is a typed error; every Observation cites calls and every quantitative claim cites an analysis over an exported file | | pending |
| F12 | A study that runs out of budget | Mechanism | The next Observation is rejected with `budget_exhausted`, and the branch concludes with what it has | | pending |
| F13 | The Wordle study, unbounded, on a Sonnet-class model | Judgement | The audit is clean, the independent check passes every Wordle criterion, and the recording exists | | pending |
| F14 | Restart during a Wordle run | Kickoff prompt | Steps and forks resume on the same handles, games resume through `game_state`, and the log has no duplicate entries | | pending |
| F15 | The hidden-law study, unbounded, on a Sonnet-class model | Judgement | The audit is clean, the scorer's output is recorded, the independent check passes every hidden-law criterion, and the recording exists | | pending |
| F16 | Build the site with every published session | No prompt | Every published export opens offline and shows everything in the export table for its run; site tests, type check, build and the conversation spec pass; the example page, the new and updated docs pages, the task conversations and the NDP pages render | | pending |
| F17 | A plain request in a large workspace that is easiest to answer by surveying many files first | Judgement | The agent delegates the survey on its own, to `explore` or the default, and the child's report, not the file contents, enters the root context | | pending |
| F18 | A plain request whose separable parts would flood one context | Judgement | The agent spawns children with no `agent` named or a role, writes each a self-contained task, and merges their reports | | pending |
| F19 | Export a session that ran a council, an arena and a workflow with an editor, an approval, a nested flow and a fork | Mechanism | Offline, each run's railroad matches the live one, every step opens its transcript and answer, and the proposals, approvals and fork appear where they happened | | pending |
| F20 | Export a session with a subagent tree three levels deep that includes a role, a fork and a model override | Mechanism | Offline, every descendant is reachable from its spawn and back, with its agent, model, assignment and result | | pending |
| F21 | Open the F11 study, and a session that is not in a study, in the web UI and in the native desktop app under Xvfb | No prompt | The Science log tab appears only for the study; the tree sits above the selected branch's entries; selecting a node opens that branch's entries; a citation jumps to the cited entry and to the transcript turn that wrote it; screenshots read from both | | pending |
| F22 | Write an Observation citing a real measurement call, with one value named by result field | Mechanism | Its sources list the call's tool, arguments, times, result digest and artifact versions, all matching the transcript and the artifact registry, and the named value equals the call's result | | pending |
| F23 | Write an Observation with no cited call, one citing a call from another branch, and, in a fork, one citing the forker's call from before the fork | Mechanism | `lineage_missing` and `lineage_call_outside_branch` for the first two, nothing written; the third accepted | | pending |
| F24 | `export_measurements` on a known set of Observations, in and outside an isolated run | Mechanism | Rows match the log, the manifest lists Observation ids and condition keys, the hash matches the file and its artifact version, and each file is where the defaults put it | | pending |
| F25 | An isolated workflow: two parallel steps write a same-named file; one writes outside its folder; a step forks; a merge reads its inputs | Mechanism | Both files exist in their own folders; the outside write is refused with the fence's reason; the fork's folder starts as a copy, cloned or copied as recorded; the merge reads both and writes only its own folder | | pending |
