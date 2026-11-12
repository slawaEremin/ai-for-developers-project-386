import { expect, test } from '@playwright/test';

test('владелец создаёт тип, гость подтверждает слот, запись появляется у владельца', async ({ page, context }) => {
  await page.goto('/#/owner');
  await expect(page.getByText('Предстоящих встреч пока нет.')).toBeVisible();
  await page.getByLabel('Идентификатор (id)').fill('browser-consultation');
  await page.getByLabel('Название', { exact: true }).fill('Браузерная консультация');
  await page.getByLabel('Описание', { exact: true }).fill('Настоящие Vue, SDK, API и PostgreSQL');
  await page.getByLabel('Длительность в минутах').fill('45');
  const createdType = page.waitForResponse((response) => response.url().endsWith('/api/meeting-types') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Создать тип встречи', exact: true }).click();
  expect((await createdType).status()).toBe(201);
  await expect(page.getByText('Тип встречи «Браузерная консультация» создан.')).toBeVisible();
  const guestLink = await page.getByRole('link', { name: 'Открыть гостевую страницу' }).getAttribute('href');

  const guest = await context.newPage();
  await guest.goto(`/${guestLink}`);
  const slot = guest.locator('[data-slot]').first();
  await expect(slot).toHaveText('09:00–09:45');
  const startsAt = await slot.getAttribute('data-slot');
  await slot.click();
  await expect(guest.getByRole('status', { name: 'Итог записи' })).toContainText('45 минут');
  const confirmed = guest.waitForResponse((response) => response.url().endsWith('/api/bookings') && response.request().method() === 'POST');
  await guest.getByRole('button', { name: 'Подтвердить запись', exact: true }).click();
  const bookingResponse = await confirmed;
  expect(bookingResponse.status()).toBe(201);
  const booking = await bookingResponse.json();
  expect(booking.startsAt).toBe(startsAt);
  const success = guest.getByRole('status', { name: 'Запись подтверждена' });
  await expect(success).toContainText('Браузерная консультация');
  await expect(success).toContainText('09:00–09:45');
  await expect(success).toContainText('Europe/Moscow');

  await page.bringToFront();
  await page.getByRole('button', { name: 'Обновить встречи', exact: true }).click();
  const upcoming = page.getByRole('region', { name: 'Предстоящие встречи' });
  await expect(upcoming.getByRole('heading', { name: 'Браузерная консультация' })).toBeVisible();
  await expect(upcoming).toContainText('09:00–09:45');
  await expect(upcoming).toContainText('45 мин');
  await expect(upcoming).toContainText('Europe/Moscow');
  await expect(upcoming).toContainText(new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow', day: 'numeric', month: 'long', year: 'numeric',
  }).format(new Date(startsAt!)));
  // Настоящая перезагрузка читает сохранённую запись, а не локальное состояние.
  await page.reload();
  await expect(page.getByRole('region', { name: 'Предстоящие встречи' })).toContainText('Браузерная консультация');
});
