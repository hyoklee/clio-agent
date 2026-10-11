import { expect, test } from '@playwright/test';

for (const width of [390, 1440]) {
  test(`conversation relationships guide loads real captures and enlarged views at ${width}px`, async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('starlight-theme', 'light'));
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/docs/branch-and-rewind/');
    await expect(page.getByRole('heading', { level: 1, name: 'Branch and rewind conversations' })).toBeVisible();
    const captures = [
      'Copied offset calculation',
      'Relationships view with Calibration baseline',
      'Conversation family Gantt with five named conversations',
      "The offset branch's artifact Lineage tab",
    ];
    for (const [index, title] of captures.entries()) {
      const button = page.getByRole('button', { name: new RegExp(`^View larger: ${title}`) });
      await button.scrollIntoViewIfNeeded();
      await expect(button).toBeEnabled();
      const image = button.getByRole('img');
      await expect.poll(() => image.evaluate((element) => (element as HTMLImageElement).complete && (element as HTMLImageElement).naturalWidth > 0)).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await button.click();
      const dialog = page.getByRole('dialog');
      await expect(dialog.getByRole('img')).toBeVisible();
      await expect(dialog.getByRole('link', { name: 'Open full-size image (new tab)' })).toHaveAttribute('href', /\.webp$/);
      if (width === 1440 || index === 1) await page.screenshot({ path: test.info().outputPath(`capture-${index}-${width}.png`) });
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      await expect(button).toBeFocused();
    }
    await page.goto('/docs/evidence/');
    await page.getByRole('link', { name: 'branching walkthrough and screenshots' }).click();
    await expect(page).toHaveURL(/\/docs\/branch-and-rewind\/#find-and-compare-related-conversations$/);
    await expect(page.getByRole('heading', { name: 'Find and compare related conversations', exact: true })).toBeInViewport();
  });
}
