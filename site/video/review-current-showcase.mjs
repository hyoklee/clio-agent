/** Capture fictional files through the current, unmodified product UI. */
import { chromium } from '../node_modules/@playwright/test/index.mjs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = resolve(process.env.CLIO_SHOWCASE_EVIDENCE ?? 'out/current-showcase');
const scene = process.env.CLIO_CAPTURE_SCENE ?? 'dashboard';
if (!['lineage', 'dashboard', 'report', 'data'].includes(scene)) throw new Error('Unknown capture scene');
await mkdir(output, { recursive: true });
const runtime = JSON.parse(await readFile(resolve(process.env.CLIO_SHOWCASE_RUNTIME ?? resolve(output, 'runtime'), 'runtime.json'), 'utf8'));
if (!runtime.synthetic_only) throw new Error('Website captures require a synthetic-only service');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({
  viewport: { width: scene === 'report' || scene === 'data' ? 1120 : 1440, height: scene === 'dashboard' ? 1280 : scene === 'lineage' ? 560 : scene === 'data' ? 820 : 520 },
  deviceScaleFactor: 1, colorScheme: 'light',
});
await context.addInitScript((port) => {
  localStorage.setItem('clio.recent-connections', JSON.stringify([`http://127.0.0.1:${port}`]));
  localStorage.setItem('theme', 'light');
}, runtime.backend_port);
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
try {
  const example = runtime.example;
  await page.goto(`http://127.0.0.1:${runtime.ui_port}/workspaces/${example.workspace_id}/sessions/${example.session_id}`);
  await page.getByRole('button', { name: /Session actions/ }).waitFor({ timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.getByRole('button', { name: 'Evidence layout: None', exact: true }).click();
  if (scene === 'data') {
    await page.getByRole('button', { name: 'Open full details', exact: true }).click();
    await page.getByRole('button', { name: 'Maximize canvas', exact: true }).click();
    const evidence = page.getByRole('tabpanel', {name:'Evidence',exact:true});
    await evidence.getByRole('button', {name:'Artifacts, 6 recorded',exact:true}).click();
    await evidence.getByRole('button', {name:'Open morning-findings.md',exact:true}).waitFor();
    const source = evidence.getByRole('button', {name:'Open bike-stations.csv',exact:true});
    await source.waitFor();
    const bounds = await source.boundingBox();
    if (!bounds || bounds.y + bounds.height > 820) throw new Error('Capture would clip the source file');
  } else {
    await page.getByRole('button', { name: 'Evidence layout: Bottom', exact: true }).click();
    const name = scene === 'dashboard' ? /Open Morning availability/ : 'Open morning-findings.md';
    await page.getByRole('button', { name }).click();
    await page.getByRole('button', { name: 'Maximize canvas', exact: true }).click();
    if (scene === 'lineage') {
      await page.getByRole('tab', { name: 'Lineage', exact: true }).click();
      await page.getByRole('region', { name: 'Artifact lineage graph', exact: true }).waitFor();
      await page.getByRole('button', { name: /Fit view/i }).click();
      if (await page.locator('.react-flow__node').count() !== 9 || await page.locator('.react-flow__edge').count() !== 10) {
        throw new Error('Expected all three declared evidence branches and their report join');
      }
    } else if (scene === 'dashboard') {
      await page.locator('.vega-embed canvas, .vega-embed svg').first().waitFor();
      await page.waitForFunction(() => {
        const surfaces = [...document.querySelectorAll('[data-slot="a2ui-map-surface"]')];
        return surfaces.length > 0 && surfaces.every((surface) =>
          surface.__clioMap?.loaded() && surface.__clioMap?.areTilesLoaded()
            && !surface.__clioMapFailure,
        );
      }, null, {timeout:60000});
    } else {
      await page.getByRole('heading', {name:'Where bikes leave and accumulate'}).waitFor();
    }
  }
  await page.waitForTimeout(1200);
  const body = await page.locator('body').innerText();
  if (/opal/i.test(body)) throw new Error('Private research context must never enter a website capture');
  if (errors.length) throw new Error(errors.join('\n'));
  if (scene === 'lineage') {
    const nodes = await page.locator('.react-flow__node').evaluateAll((items) => items.map((node) => {
      const rect = node.getBoundingClientRect();
      return {left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom};
    }));
    if (nodes.some((rect) => rect.left < 0 || rect.right > 1440 || rect.top < 75 || rect.bottom > 560)) throw new Error('Capture would clip a lineage node');
  }
  await page.screenshot({path:resolve(output, `${scene}.png`),animations:'disabled'});
  await writeFile(resolve(output, `${scene}.txt`), body);
  console.log(JSON.stringify({output,scene,errors}));
} finally {
  await browser.close();
}
