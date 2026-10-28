#!/usr/bin/env node
// Open the installed desktop app, watch it until its workspace is usable, quit it
// through its own Quit (`quit_clio`), and time every step. Started by
// desktop_launch.sh, which provides the display, tauri-driver and the isolated HOME.
//
//   node desktop_launch.mjs --app /usr/bin/clio-desktop --home DIR --out DIR --label NAME
//
// Writes NAME.json (timeline, states seen, memory, quit outcome) and screenshots.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : fallback;
};
const APP = opt('app');
const HOME = opt('home');
const OUT = opt('out');
const LABEL = opt('label', 'launch');
const READY_LIMIT_S = Number(opt('ready-limit', '900'));
const QUIT_LIMIT_S = Number(opt('quit-limit', '240'));
const DRIVER = process.env.TAURI_DRIVER_URL;
const EL = 'element-6066-11e4-a52e-4f735466cecf';
const BOOT_LOG = path.join(HOME, '.local/share/ai.iowarp.clio.desktop/logs/backend-boot.log');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const t0 = Date.now();
const at = () => Number(((Date.now() - t0) / 1000).toFixed(1));
const result = { label: LABEL, app: APP, home: HOME, events: [], states: [], shots: [] };
const event = (name, extra = {}) => {
  const row = { t: at(), event: name, ...extra };
  result.events.push(row);
  console.log(JSON.stringify(row));
};

async function wd(method, p, body, timeoutMs = 30_000) {
  const res = await fetch(`${DRIVER}${p}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`WD ${method} ${p} -> ${res.status}: ${JSON.stringify(json).slice(0, 300)}`);
  return json.value;
}

/** Processes started for this run: everything whose environment carries this HOME. */
function owned() {
  const rows = [];
  for (const pid of readdirSync('/proc').filter((d) => /^\d+$/.test(d))) {
    try {
      const env = readFileSync(`/proc/${pid}/environ`, 'utf8').split('\0');
      if (!env.includes(`HOME=${HOME}`)) continue;
      const cmd = readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0').filter(Boolean);
      const name = path.basename(cmd[0] || '');
      // The test's own driver, and the D-Bus session that GTK auto-starts on a
      // display without a desktop session (a real desktop already runs it).
      if (/^(WebKitWebDriver|tauri-driver|dbus-launch|dbus-daemon|at-spi-bus-launcher|at-spi2-registryd)$/.test(name)) continue;
      const status = readFileSync(`/proc/${pid}/status`, 'utf8');
      const rss = Number((status.match(/VmRSS:\s+(\d+)/) || [0, 0])[1]) / 1024;
      const token = env.find((e) => e.startsWith('CLIO_AUTH_TOKEN='));
      rows.push({ pid: Number(pid), cmd: cmd.join(' ').slice(0, 160), rss_mb: Math.round(rss), token: token?.split('=')[1] });
    } catch {
      // the process exited while being read
    }
  }
  return rows;
}

const kind = (row) =>
  /clio_agent\.gact/.test(row.cmd) ? 'server'
    : /clio_run|chimaera/.test(row.cmd) ? 'clio-core'
      : /clio-desktop/.test(row.cmd) ? 'desktop'
        : /\/clio-agent\b/.test(row.cmd) ? 'launcher'
          : /document_install/.test(row.cmd) ? 'package-setup'
            : 'other';

function bootLog() {
  return existsSync(BOOT_LOG) ? readFileSync(BOOT_LOG, 'utf8') : '';
}

async function shot(name) {
  try {
    const b64 = await wd('GET', `/session/${sid}/screenshot`);
    const file = path.join(OUT, `${LABEL}-${String(result.shots.length + 1).padStart(2, '0')}-${name}.png`);
    writeFileSync(file, Buffer.from(b64, 'base64'));
    result.shots.push(file);
  } catch (error) {
    event('screenshot_failed', { error: String(error).slice(0, 120) });
  }
}

/** What the window shows, reduced to a short state name plus its headline text. */
async function windowState() {
  const view = await wd('POST', `/session/${sid}/execute/sync`, {
    script: `const t = document.body ? document.body.innerText : '';
      return { text: t.slice(0, 600), composer: !!document.querySelector('textarea, [contenteditable="true"]') };`,
    args: [],
  });
  const t = view.text;
  const state = view.composer ? 'workspace'
    : /Unavailable|Connection unavailable/i.test(t) ? 'unavailable'
      : /Not reachable|Can't connect/i.test(t) ? 'cannot_connect'
        : /Waiting for the service/i.test(t) ? 'waiting'
          : /Starting/i.test(t) ? 'starting'
            : /install|Setting up|Preparing/i.test(t) ? 'setting_up'
              : t.trim() ? 'other' : 'blank';
  return { state, text: t.replace(/\s+/g, ' ').trim().slice(0, 200) };
}

// 1. Open the app.
event('open');
const created = await wd(
  'POST',
  '/session',
  { capabilities: { alwaysMatch: { browserName: 'wry', 'tauri:options': { application: APP } }, firstMatch: [{}] } },
  180_000,
);
const sid = created.sessionId;
event('window');

// 2. Watch until the workspace is usable (a composer is on screen).
let last = null;
let ready = false;
let serverSeen = false;
let healthReady = false;
while (at() < READY_LIMIT_S) {
  let view;
  try {
    view = await windowState();
  } catch (error) {
    view = { state: 'unreadable', text: String(error).slice(0, 120) };
  }
  if (view.state !== last) {
    result.states.push({ t: at(), ...view });
    event('state', view);
    await shot(view.state);
    last = view.state;
  }
  const procs = owned();
  const server = procs.find((p) => kind(p) === 'server');
  if (server && !serverSeen) {
    serverSeen = true;
    event('server_process', { pid: server.pid });
  }
  if (server?.token && !healthReady) {
    const port = (server.cmd.match(/--port (\d+)/) || [])[1];
    try {
      const res = await fetch(`http://127.0.0.1:${port}/v1/health`, {
        headers: { Authorization: `Bearer ${server.token}` },
        signal: AbortSignal.timeout(2000),
      });
      const body = await res.json();
      if (body.readiness === 'ready' || (!body.readiness && res.ok)) {
        healthReady = true;
        event('server_ready', { readiness: body.readiness ?? 'not reported', marks: body.boot?.marks });
      }
    } catch {
      // not answering yet
    }
  }
  if (view.state === 'workspace') {
    ready = true;
    break;
  }
  await sleep(1000);
}
event(ready ? 'workspace_usable' : 'workspace_not_usable');
const checkpoints = bootLog().split('\n').filter((l) => /checkpoint|backend ready|document|install/i.test(l));
result.boot_checkpoints = checkpoints.slice(0, 40);

// 3. Settle, then record memory.
await sleep(10_000);
const before = owned();
result.processes_before_quit = before.map((p) => ({ kind: kind(p), pid: p.pid, rss_mb: p.rss_mb, cmd: p.cmd }));
result.rss_mb = {
  desktop: before.filter((p) => kind(p) === 'desktop').reduce((s, p) => s + p.rss_mb, 0),
  server: before.filter((p) => kind(p) === 'server').reduce((s, p) => s + p.rss_mb, 0),
  all: before.reduce((s, p) => s + p.rss_mb, 0),
};
await shot('before-quit');

// 4. Quit through the app's own Quit.
const quitAt = Date.now();
event('quit');
try {
  await wd('POST', `/session/${sid}/execute/async`, {
    script: 'const done = arguments[arguments.length - 1]; window.__TAURI_INTERNALS__.invoke("quit_clio").then(() => done("ok"), (e) => done(String(e)));',
    args: [],
  }, 10_000);
} catch (error) {
  event('quit_call_returned', { note: String(error).slice(0, 120) });
}
const gone = {};
while ((Date.now() - quitAt) / 1000 < QUIT_LIMIT_S) {
  const now = owned();
  for (const row of before) {
    const k = `${kind(row)}:${row.pid}`;
    if (!(k in gone) && !now.some((p) => p.pid === row.pid)) {
      gone[k] = Number(((Date.now() - quitAt) / 1000).toFixed(1));
      event('exited', { process: k, after_quit_s: gone[k] });
    }
  }
  if (now.length === 0) break;
  await sleep(250);
}
const left = owned();
result.quit = {
  seconds_until_all_gone: left.length ? null : Number(((Date.now() - quitAt) / 1000).toFixed(1)),
  exited_after_s: gone,
  left_running: left.map((p) => ({ kind: kind(p), pid: p.pid, cmd: p.cmd })),
};
const log = bootLog();
result.quit_log = log.split('\n').filter((l) =>
  /shutdown|Shutting down|Finished server process|SIGTERM|SIGKILL|kill|clio-core|cleanup|desktop-exit|terminate/i.test(l),
).slice(-30);
writeFileSync(path.join(OUT, `${LABEL}-boot.log`), log);
try {
  await wd('DELETE', `/session/${sid}`, undefined, 10_000);
} catch {
  // the app is gone, so the session is too
}
event('done');
writeFileSync(path.join(OUT, `${LABEL}.json`), JSON.stringify(result, null, 2));
