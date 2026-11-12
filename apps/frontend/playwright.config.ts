import { defineConfig } from '@playwright/test';

if (!process.env.E2E_BASE_URL) throw new Error('Запустите npm run test:e2e из корня');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL,
    browserName: 'chromium',
    channel: process.env.E2E_BROWSER_CHANNEL,
    // Проверяем московское отображение на устройстве с другим часовым поясом.
    timezoneId: 'America/Los_Angeles',
    locale: 'ru-RU',
    trace: 'retain-on-failure',
  },
});
