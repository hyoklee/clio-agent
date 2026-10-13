# Protected execution and question controls

On 2026-10-13 the recorded OPAL shell attempt at 15:53 failed because Windows
protection was still unverified. The successful verification receipt was written
at 15:59:24 CDT. Leaving Infrastructure did not cancel setup. A manual call through
the normal built-in shell path subsequently returned `protected-shell-ready` with
exit code zero, with the real Windows fence active. No model inference was run.

## Changes

- Prepare Windows protection off the event loop before constructing the agent or
  configuring its provider. This covers local/headless launches without a desktop
  installer hook. Shared startup callers await one operation. Routine startup
  does not request elevation; first-time legacy account creation still needs real
  Windows administrator approval.
- Publish current setup step, start time, elapsed time and retained outcome through
  `/v1/system/sandbox`. Navigating away leaves the service worker running. The
  workspace notification follows it and reports the outcome or required restart.
- Render question prompts and options with the same Markdown, math and content
  links as responses. Reduce card spacing; reveal optional comments on request;
  preserve drafted comments when switching choices. Long prompts scroll rather
  than being cut off after three lines.
- Update Infrastructure directions to **CLIO hosts**, and explain that **Bypass
  checks** skips action approvals while source-access restrictions still apply.
- Update the public questions, permissions, troubleshooting and CLI guides, with a
  current seeded interface capture clearly distinguished from model analysis.

## Scope and qualification

The UI change is [gact-tui PR #609](https://github.com/iowarp/gact-tui/pull/609).
This change does not modify CLIO Core, the separate asynchronous-task rewrite,
OPAL data, or scientific analysis. It does not disable any protection.

Local validation comprises lint, type/static checks, docs checks/build, real shell
acceptance and manual browser interaction at desktop and phone widths. Automated
suites are reserved for hosted CI. Merge and local-install receipts are retained
under `D:/CLIO-Develop/protected-execution-questions-20261013/`, with screenshot
originals under `D:/Libraries/Videos/clio_recordings/2026-10-13-compact-questions/`.
