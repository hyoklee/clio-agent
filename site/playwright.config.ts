import { defineConfig, devices } from '@playwright/test';

const port = Number.parseInt(process.env['CLIO_SITE_TEST_PORT'] ?? '4389', 10);
if (!Number.isSafeInteger(port) || port < 1 || port > 65535) throw new Error('Invalid CLIO_SITE_TEST_PORT');

export default defineConfig({
  testDir: './e2e',
  retries: 0,
  workers: 1,
  use: { baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure' },
  webServer: {
    command: `pnpm preview --host 127.0.0.1 --port ${port} --ignore-lock`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
