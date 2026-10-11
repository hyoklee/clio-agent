/** Review the encoded recordings inside the built guides and in fullscreen. */
import { chromium } from '../node_modules/@playwright/test/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = resolve(process.env.CLIO_DOCS_REVIEW);
const base = process.env.CLIO_DOCS_URL ?? 'http://127.0.0.1:4389';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, colorScheme: 'light' });
await context.addInitScript(() => localStorage.setItem('starlight-theme', 'light'));
const page = await context.newPage();
const errors = [];
const playback = [];
page.on('pageerror', (error) => errors.push(error.message));
try {
  const recordings = [
    ['best-of-n', 'docs-best-of-n'], ['best-of-n', 'docs-refinement'],
    ['dashboards', 'docs-dashboard-html'], ['exports', 'docs-session-export'],
  ];
  for (const [slug, name] of recordings) {
    if (process.env.CLIO_DOCS_REVIEW_ONLY && !name.includes(process.env.CLIO_DOCS_REVIEW_ONLY)) continue;
    await page.goto(`${base}/docs/${slug}/`);
    const video = page.locator(`.sl-markdown-content video:has(source[src$="/${name}.mp4"])`);
    await video.scrollIntoViewIfNeeded();
    await page.evaluate(() => document.fonts.ready);
    await video.evaluate((element) => element.load());
    await video.evaluate((element) => new Promise((accept, reject) => {
      if (element.readyState >= 2) return accept();
      element.addEventListener('loadeddata', accept, { once: true });
      element.addEventListener('error', reject, { once: true });
    }));
    await page.screenshot({ path: resolve(output, `${name}-embedded.png`) });
    for (const mode of ['embedded', 'fullscreen']) {
      await video.evaluate(async (element, full) => {
        element.currentTime = 0;
        if (full) await element.requestFullscreen();
        element.textTracks[0].mode = 'showing';
        await element.play();
      }, mode === 'fullscreen');
      let previous = -1;
      let stalled = 0;
      const samples = [];
      const began = Date.now();
      for (let i = 0; i < 180; i++) {
        await page.waitForTimeout(250);
        const state = await video.evaluate((element) => ({
          time: element.currentTime, duration: element.duration, ended: element.ended,
          error: element.error?.message, width: element.videoWidth, height: element.videoHeight,
        }));
        if (state.error) throw new Error(state.error);
        stalled = state.time === previous && !state.ended ? stalled + 1 : 0;
        if (stalled > 12) throw new Error(`Playback stalled: ${slug} ${mode}`);
        previous = state.time;
        samples.push(state.time);
        if (i % 20 === 0) await page.screenshot({ path: resolve(output, `${name}-${mode}-${i}.jpg`), type: 'jpeg', quality: 75 });
        if (state.ended) {
          playback.push({ slug, name, mode, ...state, elapsed: (Date.now() - began) / 1000, samples });
          break;
        }
        if (i === 179) throw new Error(`Playback did not finish: ${slug} ${mode}`);
      }
      if (mode === 'fullscreen') await page.evaluate(() => document.exitFullscreen());
    }
    console.log(`Complete encoded playback: ${name}, embedded and fullscreen`);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [slug, name] of recordings) {
    if (process.env.CLIO_DOCS_REVIEW_ONLY && !name.includes(process.env.CLIO_DOCS_REVIEW_ONLY)) continue;
    await page.goto(`${base}/docs/${slug}/`);
    const video = page.locator(`.sl-markdown-content video:has(source[src$="/${name}.mp4"])`);
    await video.scrollIntoViewIfNeeded();
    await page.screenshot({ path: resolve(output, `${name}-mobile.png`) });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) throw new Error(`Mobile overflow: ${slug}`);
  }
  await writeFile(resolve(output, 'playback-review.json'), JSON.stringify({ base, errors, playback }, null, 2));
  if (errors.length) throw new Error(errors.join('\n'));
} finally {
  await browser.close();
}
