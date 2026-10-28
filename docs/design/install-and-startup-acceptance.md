# Install and startup acceptance matrix (0.9.5)

The acceptance bar for the 0.9.5 install and startup work (#1875, iowarp/gact-tui#691):
three entry points, each measured cold and repeat, against upper limits. This page
records how the matrix was measured on Linux, the result, and how to reproduce it on
another OS. Open items found along the way are in #1887.

## The matrix

| Row | What is timed | Upper limit |
|---|---|---|
| Install | the install script, start to finish | 180 s |
| Agent | `clio-agent serve` launch → functional (below) | 30 s |
| Desktop | desktop app launch → workspace usable (composer on screen) | 60 s |

The limits are upper bounds; lower is better.

- **Cold:** the first run after install. Nothing of CLIO's is running or cached in its
  data folders. The OS file cache is not dropped.
- **Repeat:** the same thing again on the same machine and store.
- **Functional (agent):**
  1. `/v1/health` reports `readiness: ready`;
  2. `GET /v1/sessions?limit=30` (the conversation list's first page) answers;
  3. `GET /v1/sessions/{id}/messages?limit=50` for the newest conversation answers.
- **Usable (desktop):** the workspace with its composer is on screen. The conversation
  list fills within about 10 s of that.

## Result on Linux (2026-10-28)

**Code:** clio-agent `f5dbf2cd`, gact-tui `fa393da0`, both rebased on `develop`.

**Machine:** a 4-core x86_64 Linux cloud container with 15 GB RAM, idle (load ≈ 0), with nothing else running.

| | Cold | Repeat | Limit | Pass |
|---|---|---|---|---|
| Install | 148 s | 54 s | 180 s | yes |
| Agent | 22.5 s | 10.3 s, 10.8 s | 30 s | yes |
| Desktop | 29.9 s | 18.5 s | 60 s | yes |
| *Desktop package install (`apt install ./CLIO Desktop.deb`)* | *32.8 s* | *31.0 s* | | |

Details:

- **Install:**
  - Cold: isolated `HOME` with empty uv, Go and npm caches, and no uv on `PATH` (the
    installer brings its own).
  - The TUI builds in the background: 70 s cold, 8 s repeat.
  - `clio-agent migrate`: 6 s cold, 4 s repeat (nothing owed).
  - The repeat updates the installer's own clone in place.
- **Agent:**
  - Store: the 903-conversation reference store below, with no model provider set.
  - The conversation list's first page (30 of 903) answered in 4–8 ms. The newest
    conversation's first page answered in 24–31 ms.
  - A brand-new empty home was ready in 7.1 s.
- **Desktop:**
  - The `.deb` was built from the same heads and installed with the older package
    removed first. Both launches ran against the same store, under Xvfb.
  - Quit: server and clio-core gone in 2.3 s, everything in 6.6 s, nothing forced.
- **Seen, not explained:**
  - In both desktop launches the agent picker still read "Loading agents…" about 10 s
    after the workspace opened.
  - On the cold launch, the landing page showed for about 3 s between two
    "Starting CLIO" screens.
  - These are tracked in #1887.

## Result on Windows (2026-10-28)

**Code:** source install and agent: clio-agent `c6cb5535`, with its pinned gact-tui
`fa393da0`; bundled desktop: gact-tui `59a0c97c` and the same clio-agent production
source. Local test-fixture repairs do not change the measured product. The local
unsigned NSIS package has version `0.7.3`; the release pipeline supplies the release
version. [Build identity and hash](evidence/windows-startup-2026-10-28/desktop-build.json).

**Machine:** Windows 11 Home, Ryzen 5 3600 (6 cores / 12 threads), 31.95 GiB RAM,
D: NTFS on a 953.87 GiB NVMe SSD. WMI reports build 26300; the native Windows
identity used by MXC reports `10.0.26100.9711`. This was a desktop with background
user workloads, not an idle cloud runner. No independent build or test workload overlapped
the acceptance timers.

| | Cold | Repeat | Limit | Pass |
|---|---|---|---|---|
| Install | 242.0 s | 26.2 s | 180 s | cold no / repeat yes |
| Agent | 35.3 s | 29.3 s | 30 s | cold no / repeat yes |
| Desktop | 120.8 s | 29.9 s | 60 s | cold no / repeat yes |
| *Desktop package install (`/S`)* | *183.5 s, exit 2* | *73.2 s, exit 0* | | *cold failed* |

Windows acceptance has **not passed**: all three cold timings exceed their limits,
and a fresh desktop package install failed its Office check.

- **Cold and repeat:** the corrected cold source install used a new empty
  `HOME`, `USERPROFILE`, `LOCALAPPDATA`, `APPDATA`, `CLIO_BIN_DIR` and uv/Go/npm
  caches, with no uv on `PATH`. `CODEX_HOME` explicitly matched `HOME/.codex`.
  Repeat reused that profile and updated the installer's clone. These runs followed
  earlier diagnostic attempts; OS file caches and Defender reputation caches were
  not reset. System Python 3.14.6, Git, Go and Node were already installed.
- **Install cost:** uv prepared 206 packages in 50.90 s and installed them in
  14.49 s. Cold Office preparation occupied about 106 s alongside the other
  document setup. The installer reports "TUI built in 211 s" cold / 24 s repeat,
  but its clock runs from background launch until `Complete-TuiBuild` collects the
  process; it does not use the compiler's exit time. The final join's log messages
  arrive almost together, so those figures do not establish compiler wall time
  or an additional 211 s wait. Earlier compiler contention was not measured.
  Overlapping durations must not be summed. The final MXC phase took about 1.8 s
  until all managed packages were verified; repeat reused the verified receipt.
- **Protected execution:** CLIO used its own bundled Codex 0.162.1. The earlier
  454.1/31.1 s failed installs omitted explicit `CODEX_HOME` from the simulated
  profile. Capturing the unchanged probe exposed a configuration-loading error,
  `default_permissions requires a [permissions] table`, before any witnesses ran.
  With matching `CODEX_HOME`, the same binary/profile/argv passed all seven real
  filesystem, descendant and network witnesses in 1.014 s. The desktop bundle's
  real requalification also passed (1.412 s). No protection was disabled and no
  machine-installed Codex was substituted. The 454.1 s total included 238 s of
  dependency preparation; protected execution was its final failure, not that
  entire duration.
- **Defender:** enabled throughout, with no exclusions added. A sample during the
  first failed install reported aggregate process CPU 537% (about 5.37 logical
  cores); a corrected-cold sample reported 0%, and the fresh NSIS sample 56%.
  These snapshots establish varying scanning activity, not an exact number of
  wall-clock seconds attributable to Defender.
- **Reference store and agent:** generated locally at `D:\cw\r2` with the default
  scripted workload in 863.4 s: 908 conversations and 70 open records. No model
  provider was configured. Installed-agent migration completed before timing.
  The bounded list returned 30 of 908 in 17/15 ms; opening the newest conversation's
  first message page took 38/39 ms. Both runs reached readiness `ready`.
  Generation still logged transient `WinError 10048`, quarantine and recovery
  errors even with no competing Core workload; an earlier generation failed
  without a summary. Successful generation does not erase those failures.
- **Agent shutdown:** the server exited gracefully after 11.0/10.0 s. The first
  run left an owned `uv sync` preparing the default SearXNG environment after the
  server exited; it required forced termination after an additional wait. Repeat
  left no owned descendants. Server exit alone did not establish complete cleanup.
- **Desktop package:** the fresh managed CLIO NSIS install failed after 183.5 s
  because the extracted `soffice.com --version` exceeded its unchanged 30 s
  timeout. This is separate from the earlier profile's sandbox failure. An initial
  local build also omitted native CLIO backend generation and embedded neutral
  connect mode; its screenshots are retained as diagnostics and excluded from
  acceptance. The corrected desktop was rebuilt with `gen-brand-backend.mjs` and
  the full branded Tauri build.
- **Desktop launch:** cold is the first GUI launch after the successful repeat
  package setup, on the reference store; repeat reuses the same profile and store.
  Windows checked managed packages before starting the backend: 88.821 s on the
  cold launch, including preparing document tools for the reference store's home
  (the installer had prepared its own default home). The backend answered
  capabilities at 104.218 s, and the composer appeared at 120.8 s. Both launches
  subsequently verified readiness `ready` and 30 of 908 conversations, with eight
  visible conversation links after the 10 s settle. No model provider was set.
  Screenshots use the WebDriver's 932 × 499 viewport.
  [Cold workspace](evidence/windows-startup-2026-10-28/desktop-cold-05-workspace.png),
  [repeat workspace](evidence/windows-startup-2026-10-28/desktop-repeat-05-workspace.png).
- **Desktop quit:** Core exited after 6.4/6.3 s, server after 10.5/10.4 s, all
  observed app descendants after 18.6/18.5 s. Nothing was forced; both driver
  cleanup receipts confirm no application or driver survivors.
- **Also seen:** both launches briefly showed the landing page between startup
  screens. The agent picker still said "Loading agents…" after settling, as on
  Linux. These observations remain on #1887.

[Raw measurements, logs and screenshots](evidence/windows-startup-2026-10-28)
are retained. Slow or broken product findings are tracked in
[#1887](https://github.com/iowarp/clio-agent/issues/1887#issuecomment-6461556314).

### Authorized Windows repairs and remeasurement

The Windows product repairs were subsequently authorized. They remain on
`codex/windows-startup-acceptance` in clio-agent PR #1889 and gact-tui PR #697,
based on the develop heads above. The baseline table remains a record of develop;
candidate measurements must not be presented as already merged behavior.

The source installer now starts a small lock-resolved worker that prepares the
real Office, Python, Node and GitHub package caches alongside the main dependency
sync. It joins that worker and still verifies packages and protected execution
before saving the installation receipt. Failure and interruption retire the worker.
The same startup-graph precompiler used by the bundled runtime prepares only the
modules startup actually loads, alongside migration and final setup. Its bytecode
still validates the source hash. The TUI duration now uses the compiler process's
actual exit time.

Office uses an isolated disposable profile. On Windows, the checksum-pinned MSI
is read as a database and its embedded CAB decompressed directly into validated
private application/font paths, without MSI registration actions. The longer-path
fallback expands into staging and moves the files; no fixed Windows buffer is
truncated. All application languages and bundled fonts are retained. A diagnostic
of direct extraction took 33.328 s for 19,467 files; its real version probe and
HTML-to-PDF conversion passed, with 117 bundled TrueType fonts. This diagnostic
does not replace the end-to-end install timing.

The desktop now checks real Windows protection before backend startup, then checks
document packages alongside the backend. Old runtimes without the new
protection-only option retain the full blocking check. Protection failures remain
failures; startup does not request elevation. The Office check retains its 30 s
timeout.

Intermediate source-install results, each with another empty profile/cache set:

| Candidate | Cold | Outcome |
|---|---|---|
| `74fea6f3` | 235.860 s | exit 0; exceeds 180 s; Office overlap alone was insufficient |
| `4a949ff9` | 187.036 s | exit 1; minimal worker's uv lookup eagerly imported the infrastructure stack |
| `7c866113` | 194.434 s | exit 0; full dependency bytecode compilation took 30.40 s before migration |
| `3b86557f` | 210.147 s | exit 0; parallel full-tree compilation took 92.9 s and did not improve installation |
| `d9a476623` | 194.277 s | exit 0; another full render was discovered on the machine afterwards; no continuous CPU sample for this run |

The infrastructure import was repaired in `7c866113`: platform helpers no longer
import service dependencies just to locate CLIO's own uv; public infrastructure
class exports keep their identity. A live minimal-worker retry prepared all managed
packages. Focused Windows validation passed 103 tests plus a UTF-16 path-limit
check; changed-module Ruff/mypy passed. The later startup-graph change passed 48
worker/policy/precompiler checks, and a real installed-environment diagnostic
prepared 2,642 modules in 25.773 s. This diagnostic used an already installed
environment and is not a cold install number.

The same `d9a476623` candidate was remeasured with another empty profile/cache
set after that render finished. Preflight total CPU was 22%; continuous telemetry
during installation observed no ffmpeg process. OS/Defender caches were not
dropped, and Defender stayed enabled. Cold mean total CPU was 68.0% including
the installer's work, with a 100% peak. No owned descendants survived either run.
The earlier elapsed measurements are retained; their CPU load was not recorded
continuously, so no exact slowdown is attributed to the competing render.

| | Cold | Repeat | Limit | Pass |
|---|---|---|---|---|
| Install (candidate `d9a476623`) | 162.103 s | 28.349 s | 180 s | yes |
| Agent | pending | pending | 30 s | pending |
| Desktop | pending | pending | 60 s | pending |

The source-install row passes. Windows acceptance remains incomplete until the
installed-agent, rebuilt bundled-desktop and fresh bundled-setup checks pass.

[Repair measurements and diagnostics](evidence/windows-startup-repair-2026-10-28)
retain the intermediate failures. Defender remained enabled; a sample during the
`7c866113` run reported aggregate process CPU 486% (about 4.86 logical cores),
without attributing an exact amount of wall time to scanning.

## The reference store

The agent and desktop rows run on a generated long-lived store, not an empty one:

```sh
uv run python scripts/create_reference_store.py --out <dir> --core-port 29091 --capacity 2GB
```

It drives CLIO's real write paths with a **scripted model**, so it makes no model calls.
It holds:
- 150 flows of 4 children each;
- 100 chats of 6 turns;
- 20 open children;
- 10 interrupted fan-outs.

That makes about 903 conversations, and generating it took 23 min. It writes `<dir>/env.sh` with the
variables a server needs to open it (`CLIO_AGENT_HOME`, `CLIO_RUNTIME_STATE_DIR`,
`CLIO_DEFAULT_MARKETPLACE`, `CLIO_CORE_PORT`, `CLIO_ARC_CTE_FILE_CAPACITY`).

**Rules for working with the store:**
- **Copying:** generate a new store rather than copy one. `scripts/copy_reference_store.py SRC DST`
  (branch `claude/migrate-fast`, not on `develop` yet) is the only safe copy; never use `cp`. The clio-core config and its write-ahead pool log hold absolute paths, so
  a plain copy reads and writes the original store.
- **Model provider:** leave none configured for these timings. With a provider, the
  obligations lane resumes the store's interrupted work through it, which spends model
  calls.

## How it was run (Linux)

**1. Install, cold then repeat.** Use a fresh directory as `HOME`, with only system
tools on `PATH`. Copy the script out of the checkout first: run from a checkout, it
installs that checkout in place instead of cloning.

```sh
export HOME=$PWD/home XDG_CACHE_HOME=$HOME/.cache XDG_DATA_HOME=$HOME/.local/share \
       XDG_CONFIG_HOME=$HOME/.config CLIO_BIN_DIR=$HOME/bin PATH=/usr/bin:/bin
time bash ./install.sh --source --ref claude/install-and-startup   # cold (on develop: --dev --source)
time bash ./install.sh --source --ref claude/install-and-startup   # repeat
```

**2. Agent, cold then repeat.**
1. Open the store with the installed copy: `source <store>/env.sh`.
2. Make sure no `CLIO_LM_PROVIDER` / `CLIO_LM_MODEL` is set.
3. Run `clio-agent migrate`.
4. Run the measurement twice:

```sh
python scripts/acceptance/measure_functional_start.py \
    --clio-agent $HOME/.local/share/clio-agent/app/clio-agent/.venv/bin/clio-agent \
    --port 19101 --out agent-cold.json
```

The script launches `clio-agent serve`, polls `/v1/health` every 0.25 s, and times the
conversation list and the first conversation page. It then stops the server and writes
the result JSON with the server log beside it. The cold row above came from the first
start after install (`scripts/measure_startup.py --in-place` on the same store); the
repeats came from this script.

**3. Desktop, cold then repeat.**
1. Build the bundled `.deb` the way `clio-bundles.yml` does:
   `install/build-gact-runtime.sh` into `desktop/src-tauri/gact-runtime`, then
   `pnpm --filter @clio/desktop tauri build --bundles deb` with the CLIO brand config.
2. Remove any older package, then `time apt install ./CLIO\ Desktop*.deb`.
3. Launch twice with the same fresh `HOME`:

```sh
EXTRA_ENV="$(grep -o '[A-Z_]*=[^ ]*' <store>/env.sh | tr '\n' ' ')" OUT=$PWD/desktop-results \
  bash scripts/acceptance/desktop_launch.sh desk-cold  $PWD/deskhome /usr/bin/clio-desktop
EXTRA_ENV=... OUT=... \
  bash scripts/acceptance/desktop_launch.sh desk-repeat $PWD/deskhome /usr/bin/clio-desktop
```

`desktop_launch.sh` starts Xvfb, a keyring and `tauri-driver`, then runs
`desktop_launch.mjs`. That script opens the app and records each screen it shows, with
a screenshot. It marks `workspace_usable` once the composer is on screen, quits through
the app's own Quit, and records how long each process takes to exit. `EXTRA_ENV` passes
the store's variables to the app, whose backend inherits them.

## Reproducing on Windows

The method carries over. What differs:

- **Install:**
  - Run `install/install.ps1` with the same options. For `develop`: `-Dev -Source`
    (or `--dev --source`).
  - For a cold run, give it a fresh user profile or set `HOME`, `LOCALAPPDATA` and
    `CLIO_BIN_DIR` to empty folders.
  - When simulating that profile with environment variables on an existing Windows
    account, also set `USERPROFILE` and `CODEX_HOME` (`$env:CODEX_HOME =
    "$env:HOME\.codex"`). CLIO and its bundled Codex must resolve the same directory
    for the generated permission layers. This selects a configuration home; Codex's
    executable still comes from CLIO's bundle.
  - Time it with `Measure-Command`.
  - The repeat is the same command again.
- **Agent:**
  - `measure_functional_start.py` runs on Windows as is. It starts the server in a new
    process group and stops it with CTRL_BREAK, falling back to `taskkill /T`.
  - Point `--clio-agent` at `...\clio-agent\.venv\Scripts\clio-agent.exe`.
  - Set the store's variables in PowerShell (`$env:CLIO_AGENT_HOME = ...`).
- **Reference store:**
  - Generate it on Windows with `create_reference_store.py`; don't copy a Linux one,
    because the store holds absolute paths.
  - Generation takes 20–30 min.
- **Desktop:**
  - Build or download the bundled NSIS installer (`CLIO Desktop_*_x64-setup.exe`).
  - Time a silent install (`/S`) for the separate desktop package-install row. Run it interactively once to
    check that its provider and infrastructure pages show.
  - Use `desktop_launch.ps1` with `tauri-driver` and an `msedgedriver` matching the
    installed WebView2 version. Set the reference store's five variables in the
    calling PowerShell session first, leaving no model provider configured:

    ```powershell
    & scripts/acceptance/desktop_launch.ps1 `
      -App 'D:\CLIO-Desktop\clio-desktop.exe' `
      -HomeDir 'D:\acceptance\desktop-home' `
      -LocalAppData 'D:\acceptance\desktop-local' `
      -NativeDriver 'D:\acceptance\drivers\msedgedriver.exe' `
      -Out 'D:\acceptance\desktop-results' -Label desktop-cold
    # Repeat with the same folders and -Label desktop-repeat.
    ```

  - The shared `desktop_launch.mjs` records the same usable-workspace event and
    screenshots on both platforms. Windows process evidence combines `Get-Process`
    working sets with CIM executable paths, parent IDs and creation times. A PID
    reused by another process is excluded from ownership and cleanup.
  - The wrapper sets `HOME`, `USERPROFILE`, `CODEX_HOME`, `LOCALAPPDATA`, `APPDATA`, temporary
    folders and WebView2's user-data folder. Reuse those folders for repeat.
    The driver asks the running app for Tauri's `AppLog` directory rather than
    assuming the caller's `LOCALAPPDATA` or .NET known-folder result matches it.
    In this simulated profile the actual log was
    `D:\cw\mp\home\AppData\Local\ai.iowarp.clio.desktop\logs\backend-boot.log`;
    `LOCALAPPDATA` was `D:\cw\mp\local`. The cold run's initially selected stale
    log is excluded; its actual log was collected separately through the same
    live directory query. Repeat resolves the path automatically. `-BootLog`
    overrides discovery when an explicit path is needed.
  - Quit goes through the app's `quit_clio` command. The result JSON records
    survivors before cleanup; the wrapper's separate cleanup receipt records any
    forced termination. A timed-out workspace or surviving app process exits 1.
- **Not measured on Linux and worth recording on Windows:**
  - the Windows protected-execution (sandbox) check, which still runs before the agent
    starts there;
  - Windows Defender scanning a fresh install.
