import { expect, test } from '@playwright/test';

for (const [slug, title, messages] of [
  ['alta', /Alta seasonal/, 6],
  ['tahoe', /Tahoe/i, 6],
  ['konza', /Konza/i, 6],
  ['ares', /Ares/i, 14],
] as const) {
  test(`${slug}: public native archive renders saved results without contacting services`, async ({ page, baseURL }) => {
    const errors: string[] = [];
    const externalRequests: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => {
      if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(baseURL!).origin)
        externalRequests.push(request.url());
    });
    const response = await page.goto(`/conversations/ndp/${slug}/`);
    expect(response?.status()).toBe(200);
    expect(response?.headers()['content-type']).toContain('text/html');
    await expect(page.getByRole('tab', { name: 'Results', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { level: 1, name: title }).filter({ visible: true })).toBeVisible();
    await expect(page.getByText(new RegExp(`Transcript.*${messages} messages`)).filter({ visible: true })).toBeVisible();
    await page.getByRole('tab', { name: 'Results', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Saved results', exact: true })).toBeVisible();
    if (slug === 'alta') {
      const monthly = page.getByRole('region', { name: 'Interactive surface, Chart', exact: true }).filter({ hasText: 'Historical baseline' });
      await monthly.getByRole('button', { name: 'All complete months (17 Oct; 24 Nov-Apr)', exact: true }).click();
      await expect(monthly.getByRole('button', { name: 'All complete months (17 Oct; 24 Nov-Apr)', exact: true })).toHaveAttribute('aria-pressed', 'true');
      await expect(monthly.getByRole('img', { name: 'Monthly snowfall and historical spread: 7 rows', exact: true })).toBeVisible();
    }
    await page.screenshot({ path: test.info().outputPath(`${slug}-native-results.png`) });
    await page.getByRole('tab', { name: 'Evidence & skills', exact: true }).click();
    await expect(page.getByRole('tab', { name: 'Evidence & skills', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(errors).toEqual([]);
    expect(externalRequests).toEqual([]);
  });
}
