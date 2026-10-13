# Protected execution and question controls

On 2026-10-13 the recorded OPAL shell attempt at 15:53 failed because Windows
protection was still unverified. The successful verification receipt was written
at 15:59:24 CDT. Leaving Infrastructure did not cancel setup. A manual call through
the normal built-in shell path subsequently returned `protected-shell-ready` with
exit code zero, with the real Windows fence active. No model inference was run.

## Changes

- All four entry points use `runtime/sandbox_cli.py:provision_codex_windows` and
  its shared `codex_desktop_access.py:ensure_runtime_access` default. Previously,
  startup supplied the cached grant function while button/CLI calls selected
  unconditional per-user recursive grants. Now unchanged directory/ACL receipts
  are reused; changed roots receive one inherited RX grant for both sandbox users.
  The redundant `/T` previously wrote explicit grants at every descendant while
  Windows also propagated inherited root permissions. Root inheritance now leaves
  protected child ACLs intact. Allowing
  elevation no longer forces a fresh native MXC probe. Failed runtime grants are
  unsuccessful for every caller. Actual first-repair and repeat-call timings are
  retained in the local receipt directory's `shared-setup-timings.json`.
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

## Measured setup cost

The old recursive real-machine probe spent 91 seconds on UV tools and 47 seconds
on UV Python, then timed out after another 120 seconds on the tool cache. It was
not a successful setup. Inherited root access repaired the remaining tool cache
in 20.7 seconds; a subsequent Temp repair took about 20 seconds. These measurements
used an existing account/enforcement receipt, not a fresh installation.

With all root receipts current, the same machine measured startup at 0.377 seconds,
the Infrastructure button owner at 0.566 seconds and CLI setup at 0.388 seconds.
All ten grant records were reused. A real Windows filesystem check confirmed
inherited RX on existing and newly created children and unchanged protected child
ACLs, consistent with [Windows inheritance semantics](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces).
