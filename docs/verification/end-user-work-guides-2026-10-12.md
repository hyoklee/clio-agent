# End-user questions and work guides

Date: 12 October 2026. Website source: `site/` in the current checkout.
Status: local documentation changes, uncommitted and unpublished.

## Reader coverage

Four linked guides are added under Use CLIO:

- `questions.mdx`: text, single choice, confirmation, connected-tool multiple
  selection and forms, URL consent, visual A2UI enrichment, independent open
  questions, answering ownership, and waiting versus independent work.
- `following-work.mdx`: tools, tasks, child agents, todos, command/output,
  cancellation versus waiting, and the difference between a terminal status and
  evidence that an assignment succeeded.
- `injections.mdx`: recorded context additions, every named UI label plus
  humanized tool-use guidance, and examples of task results and scheduled wakes.
- `workspace-panels.mdx`: compact Data/Work, full Work, Observability's
  Evidence/Timeline/Gantt/Context, opened content tabs, and remembered disclosures.

Sessions, widgets/interaction, evidence, and long-running work link to the new
pages. The previous sessions statement that nothing could continue until a
question was answered is corrected. No runtime or UI behavior is changed by
this documentation work.

## Contract checked against implementation

`ask_user_tool.py` currently defaults to `response_mode="blocking"`. Its native
kinds are freeform, choice, and confirmation. Async mode publishes a durable
question immediately and returns its identity; answers use the ordinary queue.
An attached A2UI surface is a presentation/input dimension, not an additional
native kind. Only the declared answer action submits its structured answer.

`interaction_types.py`, `elicitation_schema.py`, `routes/interactions.py`, and
the production question response components provide the connected-tool forms,
multiple selection, and URL consent distinctions. Permission review, plan
review, and draft selection retain their own controls.

The proposed contract where every ask returns a durable handle immediately and
the agent explicitly waits on that question is **not implemented in this
checkout**. `wait_tasks` accepts actual task handles, not question handles.
The public guides describe existing modes and do not promise the proposed API.

UI source reviewed: `conversation-harness-injection.tsx`, `tool-invocation.tsx`,
`tool-terminal-result.tsx`, `open-questions-tracker.tsx`, `open-question-list.tsx`,
`session-evidence-popover.tsx`, `session-work.tsx`, `observability-dock.tsx`,
`context-canvas-panel.tsx`, and `workbench-shared.ts`.

## Media and evidence limits

Seven images accompany the guides: four new detail captures and three reused
authentic product captures. The new images show a genuine recorded question,
command/output, and loop instruction in current production components, plus
the actual widget gallery. Replays and fictional examples are labelled in
captions. The question, command, and instruction text are preserved.

No model inference, OPAL prompt, onboarding command, task execution, question
submission, or session deletion was performed. These captures are not fresh
runtime acceptance. In particular, the Choice Picker image illustrates a
control; it is not a complete visual-question submission walkthrough. A future
public-safe live shoot should show an image/chart plus fields, submission, the
recorded structured answer, and continued work. Multiple open questions also
merit a dedicated capture once live demos resume.

Archive:
`D:/Libraries/Videos/clio_recordings/2026-10-12-user-work-guides/`.
The source records and display projections are retained separately from the
images. Rejected technical-dialog framing and extra gallery space remain in
`rejected/`. The site capture manifest records SHA-256 checksums and source
identity, including dirty source-file hashes rather than relying on HEAD alone.

## Review

- `pnpm check`: passed, zero errors/warnings and six existing hints.
- `pnpm build`: passed, 85 pages, all internal links valid. The bundler reports
  module-directive warnings; they are not claimed as a warning-free build.
- Production preview on port 4323: all four guides reviewed at 1440 and 390 CSS
  pixels. No document-width overflow. All seven screenshots loaded and enlarged
  through the actual viewer. Dark question detail and light Work detail inspected.
- Screenshot captions, ordinary-language prompts, gallery links, sidebar entries,
  and updated crosslinks checked. No new middot separators.
- Test suites were not run, following the user's earlier instruction.

The existing large Gantt/Work screenshots provide an overview at embedded size;
their full-size viewers expose the detailed text. A future release capture can
replace these with focused captures once its interface is settled.

Publication still follows the website's main-branch release path. This work
does not establish that develop, main, the installed product, or the public site
contains these new guides.
