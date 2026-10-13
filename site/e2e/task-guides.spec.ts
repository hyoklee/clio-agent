import { expect, test } from '@playwright/test';

const guides = [
	{ slug: '', title: 'Background work', nav: 'Background work' },
	{ slug: 'observe-and-wait/', title: 'Observe and wait', nav: 'Observe and wait' },
	{ slug: 'subagents/', title: 'Subagent controls', nav: 'Subagents' },
	{ slug: 'messages/', title: 'Messages and feedback', nav: 'Messages' },
	{ slug: 'tools-and-sources/', title: 'Task-capable tools and sources', nav: 'Tools and sources' },
	{ slug: 'session-coordination/', title: 'Session coordination', nav: 'Session coordination' },
];

for (const theme of ['light', 'dark']) {
	for (const width of [390, 1440]) {
		test(`task guides navigate without overflow at ${width}px in ${theme}`, async ({ page }) => {
			const errors: string[] = [];
			page.on('pageerror', (error) => errors.push(error.message));
			page.on('response', (response) => {
				if (response.status() >= 400 && response.url().startsWith('http://127.0.0.1:')) {
					errors.push(`${response.status()} ${response.url()}`);
				}
			});
			await page.addInitScript((value) => localStorage.setItem('starlight-theme', value), theme);
			await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
			await page.goto('/docs/tasks/');
			for (const guide of guides) {
				const nav = page.getByRole('navigation', { name: 'Tasks and coordination guides' });
				await nav.getByRole('link', { name: guide.nav, exact: true }).click();
				await expect(page).toHaveURL(new RegExp(`/docs/tasks/${guide.slug}$`));
				await expect(page.getByRole('heading', { level: 1, name: guide.title, exact: true })).toBeVisible();
				await expect(nav.locator('[aria-current="page"]')).toHaveText(guide.nav);
				const note = page.locator('.sl-markdown-content .starlight-aside');
				await expect(note).toContainText(guide.slug === 'session-coordination/'
					? 'Development build; qualification has limits' : 'Development preview');
				await page.evaluate(async () => {
					await document.fonts.ready;
					for (const image of document.querySelectorAll<HTMLImageElement>('.guide-screenshot img')) {
						image.loading = 'eager';
						await image.decode();
					}
				});
				expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
				const figures = page.locator('.guide-screenshot');
				for (const figure of await figures.all()) {
					const image = figure.getByRole('img');
					expect(await image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
					if ((await figure.getAttribute('class'))?.includes('portrait')) {
						expect((await figure.boundingBox())!.width).toBeLessThanOrEqual(384);
					}
				}
				await page.screenshot({ path: test.info().outputPath(`${guide.slug.replace('/', '') || 'overview'}-${width}-${theme}.png`), fullPage: true });
			}
			if (width === 390) await page.getByRole('button', { name: 'Docs index', exact: true }).click();
			const sidebar = page.locator('#starlight__sidebar');
			for (const guide of guides) {
				await expect(sidebar.getByRole('link', { name: guide.title === 'Task-capable tools and sources' ? 'Tools and sources' : guide.title, exact: true })).toBeVisible();
			}
			expect(errors).toEqual([]);
		});
	}
}

test('task screenshots enlarge and optional tool details stay collapsed', async ({ page }) => {
	await page.goto('/docs/tasks/observe-and-wait/');
	const details = page.locator('details').filter({ has: page.locator('summary', { hasText: 'Agent tool reference' }) });
	await expect(details).not.toHaveAttribute('open');
	await details.locator('summary').focus();
	await page.keyboard.press('Enter');
	await expect(details).toHaveAttribute('open');
	await expect(details).toContainText('query_tasks("Subagent")');
	await expect(details).toContainText('These are tool arguments, not terminal commands.');
	for (const route of ['/docs/tasks/', '/docs/tasks/observe-and-wait/', '/docs/tasks/subagents/']) {
		await page.goto(route);
		for (const link of await page.getByRole('link', { name: /^Enlarge:/ }).all()) {
			const source = await link.getAttribute('href');
			const popupPromise = page.waitForEvent('popup');
			await link.click();
			const popup = await popupPromise;
			await popup.waitForLoadState();
			expect(new URL(popup.url()).pathname).toBe(source);
			await expect(popup.locator('img')).toBeVisible();
			expect(await popup.locator('img').evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
			await popup.close();
		}
	}
	// Existing JPG guides use the same component without the new optional props.
	await page.goto('/docs/files/connect/');
	const original = page.locator('.guide-screenshot img').first();
	await original.scrollIntoViewIfNeeded();
	await expect(original).toHaveAttribute('src', /\.jpg$/);
	await expect.poll(() => original.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
});

test('task guides distinguish Stop, peer read permissions and qualification at existing entry points', async ({ page }) => {
	await page.goto('/docs/sessions/');
	await page.locator('.sl-markdown-content').getByRole('link', { name: 'task development preview', exact: true }).last().click();
	await expect(page).toHaveURL(/\/docs\/tasks\/$/);
	const actions = page.locator('.sl-markdown-content table');
	await expect(actions.getByRole('row').filter({ hasText: 'Stop' })).toContainText('Tasks continue. A later result can wake the agent again.');
	await expect(actions.getByRole('row').filter({ hasText: 'Pause' })).toContainText('messages and results accumulate');
	await expect(actions.getByRole('row').filter({ hasText: 'Cancel task' })).toContainText('cancels its descendants');
	await page.goto('/docs/tasks/messages/');
	await expect(page.locator('.sl-markdown-content')).toContainText('Task observation and waits default to the caller');
	await expect(page.locator('.sl-markdown-content')).toContainText('Fresh native-replacement model and cross-workflow qualification is pending.');
	await page.locator('.sl-markdown-content p').getByRole('link', { name: 'Session coordination', exact: true }).click();
	await expect(page.locator('.sl-markdown-content .starlight-aside')).toContainText('Its fresh model, workflow and UI qualification is still pending.');
	const subscription = page.locator('details').filter({ has: page.locator('summary', { hasText: 'Find a run and subscribe to its result' }) });
	await expect(subscription).not.toHaveAttribute('open');
	await subscription.locator('summary').click();
	await expect(subscription).toContainText('scope="authorized"');
	await expect(subscription).toContainText('notify=True');
	await expect(subscription).toContainText('knowing a handle does not bypass it');
	await expect(page.locator('.sl-markdown-content')).toContainText('does not grant lifecycle control');
	for (const route of ['/docs/', '/docs/memory-and-evidence/', '/docs/files/connect/']) {
		await page.goto(route);
		await expect(page.locator('.sl-markdown-content a[href^="/docs/tasks/"]').first()).toBeAttached();
	}
});

test("Question guide separates asking from waiting with real service captures", async ({
	page,
}) => {
	await page.goto("/docs/questions/");
	const article = page.locator(".sl-markdown-content");
	await expect(article).toContainText("it explicitly waits on the question");
	await expect(article).toContainText(
		"Stopping its wait leaves the question open",
	);
	await expect(article).toContainText(
		"Closing the answer dialog also leaves it open",
	);
	await expect(
		article.getByRole("img", {
			name: /A real Codex\/Luna conversation remains active/,
		}),
	).toBeAttached();
	await expect(
		article.getByRole("img", {
			name: /The unanswered dataset question in a phone-width dialog/,
		}),
	).toBeAttached();
	const cancellation = article
		.locator("details")
		.filter({
			has: page.locator("summary", { hasText: "Cancel an open question" }),
		});
	await expect(cancellation).not.toHaveAttribute("open");
	await cancellation.locator("summary").click();
	await expect(
		cancellation.getByRole("img", {
			name: /A real task cancellation dialog identifies/,
		}),
	).toBeVisible();
});
