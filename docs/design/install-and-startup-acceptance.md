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
  - Time a silent install (`/S`) for the install cell. Run it interactively once to
    check that its provider and infrastructure pages show.
  - `desktop_launch.mjs` is Linux-specific in two places:
    - it finds the app's processes through `/proc`;
    - it reads the boot log under `~/.local/share/ai.iowarp.clio.desktop/logs`.
  - On Windows, `tauri-driver` drives the app through `msedgedriver`; processes come
    from `Get-Process` or `tasklist`; the boot log is under
    `%LOCALAPPDATA%\ai.iowarp.clio.desktop\logs`. The timing and screenshot logic needs
    no change.
- **Not measured on Linux and worth recording on Windows:**
  - the Windows protected-execution (sandbox) check, which still runs before the agent
    starts there;
  - Windows Defender scanning a fresh install.
