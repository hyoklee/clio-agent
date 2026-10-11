import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
	resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    // The video package uses node:test and has its own dependency boundary.
    include: ['src/**/*.test.{ts,tsx,js,mjs}', 'scripts/**/*.test.{ts,js,mjs}'],
  },
});
