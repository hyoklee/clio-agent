/** Record current product controls and inspect the actual downloaded files. */
import puppeteer from 'puppeteer';
import { chromium } from '../node_modules/@playwright/test/index.mjs';
import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { installPointerGuide } from './pointer-guide.mjs';

const scene = process.argv[2] ?? 'inspect';
const output = resolve(process.env.CLIO_DOCS_EVIDENCE);
const runtime = JSON.parse(await readFile(resolve(output, 'runtime.json'), 'utf8'));
const archive = resolve(process.env.CLIO_DOCS_ARCHIVE);
await mkdir(resolve(archive, 'raw'), { recursive: true });
await mkdir(resolve(archive, 'evidence'), { recursive: true });
await mkdir(resolve(archive, 'downloads'), { recursive: true });
const browser = await puppeteer.launch({
  headless: true, executablePath: process.env.DEMO_CHROME_PATH,
  defaultViewport: { width: 1280, height: 960, deviceScaleFactor: 1 },
});
const native = await browser.newPage();
await native.goto('about:blank#docs-capture');
const client = await native.createCDPSession();
await client.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: resolve(archive, 'downloads'), eventsEnabled: true });
const playwright = await chromium.connectOverCDP(browser.wsEndpoint());
const context = playwright.contexts()[0];
const page = context.pages().find((item) => item.url().endsWith('#docs-capture'));
if (!page) throw new Error('Cannot find the native recording target');
page.setDefaultTimeout(20000);
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
let recorder;
let takeName;
let start;
const marks = [];
async function click(locator) {
  console.log('Click', locator.toString());
  await locator.waitFor();
  const bounds = await locator.boundingBox();
  if (!bounds) throw new Error('Control has no visible bounds');
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2, { steps: 18 });
  await page.waitForTimeout(350);
  await locator.click();
  await page.waitForTimeout(450);
}
async function mark(label) { marks.push({ label, seconds: (Date.now() - start) / 1000 }); }
async function shot(name, locator = page) {
  // Native recording and clipped screenshots can interfere with the captured
  // surface. Extract stills from the raw video after recording instead.
  if (recorder) return;
  const options = { path: resolve(archive, 'evidence', `${name}.png`), animations: 'disabled' };
  if (locator !== page) {
    const bounds = await locator.boundingBox();
    if (!bounds || bounds.y < 0 || bounds.y + bounds.height > 960) throw new Error('Screenshot would clip its subject');
    options.clip = bounds;
  }
  await page.screenshot(options);
}
async function record(name) {
  takeName = name;
  for (let suffix = 2; ; suffix++) {
    try { await access(resolve(archive, 'raw', `${takeName}.mp4`)); takeName = `${name}-${suffix}`; }
    catch (error) { if (error.code === 'ENOENT') break; throw error; }
  }
  recorder = await native.record({ path: resolve(archive, 'raw', `${takeName}.mp4`), frameRate: 30, maxWidth: 1280, maxHeight: 960 });
  start = Date.now();
  await mark('Start');
}
async function stop(name) {
  await mark('End');
  await recorder.stop();
  recorder = undefined;
  await writeFile(resolve(archive, 'raw', `${takeName}.json`), JSON.stringify({ scene, source: `${takeName}.mp4`, marks, errors }, null, 2));
}
async function dashboard() {
  await click(page.getByRole('button', { name: 'Evidence layout: None', exact: true }));
  await click(page.getByRole('button', { name: 'Evidence layout: Bottom', exact: true }));
  await click(page.getByRole('button', { name: /Open Morning availability/ }));
  await click(page.getByRole('button', { name: 'Maximize canvas', exact: true }));
  await page.locator('.vega-embed canvas, .vega-embed svg').first().waitFor();
  await page.waitForTimeout(1600);
}
async function download(name) {
  const received = page.waitForEvent('download', { timeout: 60000 });
  await click(page.getByRole('menuitem', { name, exact: true }));
  const item = await received;
  const filename = resolve(archive, 'downloads', item.suggestedFilename());
  await item.saveAs(filename);
  for (let attempt = 0; attempt < 100; attempt++) {
    try { await access(filename); return filename; }
    catch { await page.waitForTimeout(200); }
  }
  throw new Error(`Download did not finish: ${filename}`);
}
async function exportDashboard() {
  await dashboard();
  await page.waitForFunction(() => [...document.querySelectorAll('[data-slot="a2ui-map-surface"]')].every((el) => el.__clioMap?.loaded() && el.__clioMap?.areTilesLoaded()));
  await click(page.getByRole('button', { name: 'Download file', exact: true }));
  await page.screenshot({ path: resolve(archive, 'evidence', 'dashboard-export-menu.png'), clip: { x: 0, y: 0, width: 1280, height: 450 } });
  const png = await download('PNG image (displayed view)');
  await page.waitForTimeout(500);
  await record('dashboard-html');
  await mark('Open download menu');
  await click(page.getByRole('button', { name: 'Download file', exact: true }));
  await page.waitForTimeout(2000);
  const html = await download('HTML dashboard (all tabs and data)');
  await mark('HTML downloaded');
  await page.waitForTimeout(600);
  await client.send('Network.enable');
  await client.send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
  await page.goto(pathToFileURL(html).href);
  await native.evaluate(installPointerGuide);
  await page.locator('[data-slot="a2ui-chart-view"]').first().waitFor();
  await page.waitForTimeout(1000);
  await mark('Opened downloaded HTML offline');
  await page.getByRole('button', { name: 'Select Fernhill', exact: true }).scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await click(page.getByRole('button', { name: 'Select Fernhill', exact: true }));
  await mark('Select Fernhill offline');
  await page.waitForTimeout(4500);
  await shot('dashboard-html-offline');
  await stop('dashboard-html');
  await writeFile(resolve(archive, 'downloads', 'dashboard-exports.json'), JSON.stringify({ png, html, offline: true, errors }, null, 2));
}
async function draftAlternatives() {
  if (!(await page.getByRole('button', { name: 'Change model', exact: true }).innerText()).includes('Luna')) {
    await click(page.getByRole('button', { name: 'Change model', exact: true }));
    await page.getByRole('combobox', { name: 'Search providers and models' }).fill('Luna');
    await click(page.getByText('gpt-6-luna', { exact: true }));
  }
  await click(page.locator('[data-slot="sidebar-trigger"]'));
  await record('best-of-n');
  await mark('Type request');
  const composer = page.locator('[contenteditable="true"]');
  await click(composer);
  await composer.pressSequentially('Use Best of N: 3 candidates, one 2-sentence introduction each. Facts: fictional bike counts total 54; Hill -37, Downtown +37, 6–9 am; Fernhill empty at 8:15. No trip inference. Let me choose.', { delay: 16 });
  await click(page.getByRole('button', { name: 'Submit', exact: true }));
  await mark('Generation submitted');
  console.log('Waiting for real Codex/Luna candidates');
  await page.getByRole('button', { name: 'Pick Draft 1', exact: true }).waitFor({ timeout: 90000 });
  await mark('Candidates ready');
  const block = page.getByRole('group', { name: 'Alternative drafts', exact: true }).last();
  await block.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);
  await shot('best-of-n-candidates', block);
  await click(block.getByRole('tab', { name: /^Draft 2/ }));
  await page.waitForTimeout(2500);
  await click(block.getByRole('tab', { name: /^Draft 3/ }));
  await page.waitForTimeout(2500);
  await click(block.getByRole('button', { name: /Evaluation criteria/ }));
  await page.waitForTimeout(2500);
  await shot('best-of-n-criteria', block);
  await click(page.getByRole('button', { name: 'Pick Draft 3', exact: true }));
  await mark('Picked Draft 3');
  await page.waitForTimeout(5000);
  await shot('best-of-n-selected');
  await stop('best-of-n');
}
async function sessionMenu() {
  await click(page.getByRole('button', { name: 'Actions for Compare report introductions — Best of N', exact: true }));
  await click(page.getByRole('menuitem', { name: 'Export session', exact: true }));
}
async function refineDraft() {
  if (!(await page.getByRole('button', { name: 'Change model', exact: true }).innerText()).includes('Luna')) {
    await click(page.getByRole('button', { name: 'Change model', exact: true }));
    await page.getByRole('combobox', { name: 'Search providers and models' }).fill('Luna');
    await click(page.getByText('gpt-6-luna', { exact: true }));
  }
  await click(page.locator('[data-slot="sidebar-trigger"]'));
  await record('refinement');
  await mark('Type refinement request');
  const composer = page.locator('[contenteditable="true"]');
  await click(composer);
  await composer.pressSequentially('Use user-judged refinement, up to 3 drafts, one at a time. Write one 2-sentence report introduction. Facts: fictional station snapshots total 54 bikes; Hill -37, Downtown +37 from 6–9 am; Fernhill first empty at 8:15. Start with concise technical wording. Let me comment before accepting.', { delay: 12 });
  await click(page.getByRole('button', { name: 'Submit', exact: true }));
  await mark('First draft submitted');
  await page.getByRole('button', { name: 'Pick Draft 1', exact: true }).waitFor({ timeout: 90000 });
  await mark('First draft ready');
  const block = page.getByRole('group', { name: 'Alternative drafts', exact: true }).last();
  await block.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);
  await shot('refinement-first-draft', block);
  await page.waitForTimeout(2500);
  const feedback = block.getByPlaceholder('What should change?', { exact: true });
  await click(feedback);
  await feedback.pressSequentially('For a nontechnical colleague: use plain language, keep all figures, and say these snapshots do not prove individual bike journeys.', { delay: 20 });
  await mark('Feedback entered');
  await page.waitForTimeout(2000);
  await shot('refinement-feedback', block);
  await click(block.getByRole('button', { name: 'Refine Draft 1', exact: true }));
  await mark('Refine Draft clicked');
  await page.getByRole('button', { name: 'Pick Draft 2', exact: true }).waitFor({ timeout: 90000 });
  await mark('Revised draft ready');
  await block.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1200);
  await shot('refinement-revised-draft', block);
  await page.waitForTimeout(4000);
  await click(block.getByRole('button', { name: 'Pick Draft 2', exact: true }));
  await mark('Revised draft accepted');
  await page.waitForTimeout(5000);
  await shot('refinement-selected');
  await stop('refinement');
}
async function exportSession() {
  await click(page.locator('[data-slot="sidebar-trigger"]'));
  await sessionMenu();
  await page.screenshot({ path: resolve(archive, 'evidence', 'session-export-menu.png'), clip: { x: 56, y: 0, width: 1150, height: 540 } });
  await click(page.getByRole('menuitemcheckbox', { name: 'Include session artifacts', exact: true }));
  await page.screenshot({ path: resolve(archive, 'evidence', 'session-export-zip.png'), clip: { x: 56, y: 0, width: 1150, height: 540 } });
  const zip = await download('Download ZIP');
  await record('session-export');
  await sessionMenu();
  const artifacts = page.getByRole('menuitemcheckbox', { name: 'Include session artifacts', exact: true });
  if (await artifacts.getAttribute('aria-checked') === 'true') await click(artifacts);
  await page.waitForTimeout(1500);
  const html = await download('Download HTML');
  await mark('Transcript HTML downloaded');
  await page.waitForTimeout(500);
  await client.send('Network.enable');
  await client.send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
  await page.goto(pathToFileURL(html).href);
  await native.evaluate(installPointerGuide);
  await page.waitForTimeout(1500);
  await mark('Downloaded review opened offline');
  await shot('session-review-offline');
  await page.waitForTimeout(4500);
  await stop('session-export');
  await writeFile(resolve(archive, 'downloads', 'session-exports.json'), JSON.stringify({ zip, html, offline: true, errors }, null, 2));
}
async function inspect() {
  await writeFile(resolve(archive, 'evidence', `${scene}-controls.json`), JSON.stringify(await page.locator('button,input,textarea,[role="menuitem"],[role="menuitemcheckbox"],[contenteditable="true"]').evaluateAll((elements) => elements.map((el) => {
    const r = el.getBoundingClientRect();
    return { text: el.innerText, aria: el.getAttribute('aria-label'), title: el.getAttribute('title'), placeholder: el.getAttribute('placeholder'), role: el.getAttribute('role'), x: r.x, y: r.y, width: r.width, height: r.height };
  }).filter((el) => el.width && el.height)), null, 2));
  await shot(scene);
  console.log((await page.locator('body').innerText()).slice(-11000));
}
try {
  await page.addInitScript((port) => {
    localStorage.setItem('clio.recent-connections', JSON.stringify([`http://127.0.0.1:${port}`]));
    localStorage.setItem('theme', 'light');
  }, runtime.backend_port);
  const session = scene.startsWith('draft') || scene === 'refinement' || scene === 'export-session' ? runtime.sessions.drafts : runtime.sessions.dashboard;
  await page.goto(`http://127.0.0.1:${runtime.ui_port}/workspaces/ws_default/sessions/${session}`);
  await page.getByRole('button', { name: /Session actions/ }).first().waitFor();
  await native.evaluate(installPointerGuide);
  if (scene === 'dashboard') {
    await dashboard();
    await click(page.getByRole('button', { name: 'Download file', exact: true }));
  }
  if (scene === 'drafts') {
    await click(page.getByRole('button', { name: 'Change model', exact: true }));
    await page.getByRole('combobox', { name: 'Search providers and models' }).fill('Luna');
    await page.waitForTimeout(700);
    await click(page.getByText('gpt-6-luna', { exact: true }));
  }
  if (scene === 'export-dashboard') await exportDashboard();
  if (scene === 'drafts-run') await draftAlternatives();
  if (scene === 'drafts-capture') {
    await click(page.locator('[data-slot="sidebar-trigger"]'));
    const block = page.getByRole('group', { name: 'Alternative drafts', exact: true }).last();
    await block.evaluate((element) => element.scrollIntoView({ block: 'center', behavior: 'instant' }));
    await page.waitForTimeout(1000);
    await shot('best-of-n-published', block);
  }
  if (scene === 'export-session') await exportSession();
  if (scene === 'refinement') await refineDraft();
  await inspect();
} catch (error) {
  await inspect();
  throw error;
} finally {
  if (recorder) await recorder.stop();
  await browser.close();
}
