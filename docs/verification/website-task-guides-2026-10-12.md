# Website task and coordination guides, 2026-10-12

## Session coordination refresh

The current guides describe implemented finite `Session` run handles, authorized
peer query/observation/waits and independent `notify=True` subscriptions. The
sidebar, section navigation, overview and messaging guide no longer call those
features an unimplemented proposal. The possible Slurm workflow remains explicitly
an example requiring a scheduler adapter. Five Codex/Luna cycles across independent
root sessions with distinct single-expert blueprints qualify their concrete route;
they do not establish a distributed workflow graph or every provider/platform.

Astro check passed with zero errors/warnings and five existing hints. The
82-page production build passed internal-link validation. Three focused Chromium
cases passed individually/sequentially, one worker, zero skips: ownership and
subscription disclosure, all six guide routes at 390px and at 1440px. The first
ownership case exposed an ambiguous test locator after the navigation label
changed; the locator now selects the prose paragraph link explicitly. Assertions
for permissions, subscription arguments and qualification limits remain required.
The refreshed coordination page was visually inspected at both widths.

This reused the existing build copy and frozen dependencies. The test runner's
`pnpm preview` launcher failed before executing a case; direct Astro preview
worked, and a temporary test configuration used that owned production server.
The preview and browser processes ended. The earlier rejected build-root cleanup
remains prohibited; no removal was retried, and no second build copy was created.

## Original guide qualification

Six linked website guides explain background work, observation and waits,
subagent lifecycle controls, messages and feedback, task-capable tools and
sources, and the proposed session coordination model. They live under
`/docs/tasks/`, with a dedicated sidebar group and links from the existing
sessions, memory, source connection and introduction pages.

The guides describe immediate handles, next-model-iteration delivery, automatic
idle wakes, Stop independence, separate pause and cancellation, cancellation
settlement, linked restarts without replay, and attributed parent notices for
human controls. Optional tool and memory details use collapsed disclosures.
Two-column comparisons remain readable on phones.

Five guides explicitly identify development-build behavior and incomplete
provider/platform qualification. The coordination proposal explicitly identifies
root sessions as tasks, peer waits and cross-workflow subscriptions as
unimplemented. Existing same-workspace, same-blueprint peer messaging evidence
is not presented as cross-workflow acceptance.

## Screenshots and source

Four untouched production-service PNGs illustrate running tasks, a paused child
with a running shell command, expanded assignment details and cancellation
confirmation. Images link to their original full size; portrait captures stay
at readable widths on desktops. The existing JPG screenshot API remains supported.

`site/src/assets/captures/tasks/README.md` records the original filenames,
SHA-256 hashes, runtime/UI identities and retained qualification receipt.
Every website copy and built media file matches its original by SHA-256.
These are recorded Codex/Luna qualification assignments, not fabricated scientific
results or new platform acceptance. This website update changes no runtime code.

## Validation

- Astro check: zero errors and warnings, five existing hints. The first attempt
  lacked the separate video package's dependencies; linking the existing installed
  package resolved those setup errors without changing source or dependencies.
- Production build: 82 pages, valid internal links and regenerated Pagefind index.
  The isolated build initially lacked the real `pyproject.toml` and staged widget
  gallery. Both existing inputs were supplied before the successful builds.
- Six focused Playwright cases passed individually and sequentially with one
  worker, zero failures and zero skips. Four cases visit all six pages at 390px
  and 1440px in light/dark themes. The remaining cases check full-size PNG links,
  keyboard disclosure, an existing JPG guide, Stop/pause/cancel text, proposal
  labelling and links from existing docs.
- Actual rendered review covered all six guides on desktop and phone, plus dark
  theme checks. It caught cramped three-column tables; the final two-column
  versions were rebuilt, recaptured and rechecked. Twenty-four final full-page
  browser captures are retained.
- All 346 authored website files matched the isolated build copy by SHA-256.
  `git diff --check` passed. No assertions, budgets, worker counts or guards were
  weakened; unchanged runtime/model qualification was not rerun for these docs.

Commands used the frozen installed dependencies, with Node's heap limited to
2 GiB for Astro and 1 GiB for focused browser cases:

```powershell
node node_modules/astro/bin/astro.mjs check
node node_modules/astro/bin/astro.mjs build
# Run each of the six named cases separately, sequentially:
node node_modules/@playwright/test/cli.js test e2e/task-guides.spec.ts --grep <case> --workers=1
```

## Custody and publication

Evidence, failed setup logs, final check/build logs, six structured browser
reports, source/media hashes and browser captures are retained at
`C:/Users/jaime/.codex/recovery/clio-task-docs-20261012-114238/`.
`qualification.json` verifies source-copy and media custody and ended review
process owners. Automatic approval review rejected guarded removal of the new
isolated build copy and its two dependency junctions as `blocked by policy`.
The command did not run. `cleanup.json` records the retained root and rejection;
no other shell, helper, move or parent operation may retry or bypass that removal.
Shared installed dependencies remain retained. The preview and test processes
have ended; retaining this directory does not keep a website service running.

The website changes belong to `codex/agent-facing-async-tasks` and draft core
PR1704 into `develop`. They are locally built and reviewed, not deployed.
The draft's advanced-develop conflict and full Tasks qualification gaps remain.
No merge, release, installer launch, installed client/auth/default/pin change,
native model launch, retired service restart or earlier blocked/manual cleanup
was performed. The monitor remains paused.
