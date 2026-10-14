import { expect, test } from '@playwright/test';

const types = ['Choice', 'Text', 'Confirmation', 'Multiple choices', 'Form', 'Link', 'Visual question'];

for (const width of [390, 1440]) {
  test(`question examples cycle without overlapping at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.goto('/docs/questions/');
    const tabs = page.getByRole('tablist', { name: 'Question types' });
    await tabs.scrollIntoViewIfNeeded();
    await expect(tabs.getByRole('tab', { name: 'Choice', exact: true })).toBeEnabled();
    const sources = new Set<string | null>();
    for (const name of types) {
      const tab = tabs.getByRole('tab', { name, exact: true });
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      const image = page.getByRole('tabpanel').getByRole('img');
      await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth > 0)).toBe(true);
      sources.add(await image.getAttribute('src'));
    }
    expect(sources.size).toBe(7);
    const next = page.getByRole('button', { name: 'Next question example', exact: true });
    await next.click();
    await expect(tabs.getByRole('tab', { name: 'Choice', exact: true })).toHaveAttribute('aria-selected', 'true');
    await page.getByRole('button', { name: 'Previous question example', exact: true }).click();
    await expect(tabs.getByRole('tab', { name: 'Visual question', exact: true })).toHaveAttribute('aria-selected', 'true');

    const lastTabBottom = await tabs.getByRole('tab').evaluateAll((elements) => Math.max(...elements.map((element) => element.getBoundingClientRect().bottom)));
    expect((await next.boundingBox())!.y).toBeGreaterThanOrEqual(lastTabBottom - 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);

    await tabs.getByRole('tab', { name: 'Form', exact: true }).click();
    const capture = page.getByRole('tabpanel').getByRole('button', { name: /^View larger:/ });
    await expect(capture).toBeEnabled();
    await capture.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('dates, grouping and switch are submitted together');
    const image = dialog.getByRole('img');
    expect((await page.request.get((await image.getAttribute('src'))!)).ok()).toBe(true);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(capture).toBeFocused();
  });
}

test('question gallery waits for handlers before accepting its first click', async ({ page }) => {
  let releaseScripts!: () => void;
  const scriptsReady = new Promise<void>((resolve) => { releaseScripts = resolve; });
  await page.route('**/_astro/*.js', async (route) => {
    await scriptsReady;
    await route.continue();
  });
  try {
    await page.goto('/docs/questions/', { waitUntil: 'commit' });
    const next = page.getByRole('button', { name: 'Next question example', exact: true });
    await next.scrollIntoViewIfNeeded();
    await expect(next).toBeDisabled();
    releaseScripts();
    await expect(next).toBeEnabled();
    await next.click();
    await expect(page.getByRole('tab', { name: 'Text', exact: true })).toHaveAttribute('aria-selected', 'true');
  } finally {
    releaseScripts();
  }
});
