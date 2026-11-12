import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

const meeting = { id: 'consultation', name: 'Консультация', description: 'Вопросы', durationMinutes: 45 };
const slot = { startsAt: '2026-11-14T06:00:00Z', endsAt: '2026-11-14T06:45:00Z' };
const booking = { id: '070a4050-22f5-4465-a34c-046209ff8067', meetingTypeId: meeting.id, meetingTypeName: meeting.name, ...slot, durationMinutes: 45, timeZone: 'Europe/Moscow' };
function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function api(send: (request: Request) => Promise<Response>) {
  let occupied = false;
  const fetch = vi.fn((request: Request) => {
    if (request.method === 'POST') return send(request);
    if (request.url.endsWith('/availability')) return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', timeZone: 'Europe/Moscow', windowStartDate: '2026-11-13', windowEndDate: '2026-11-26', days: Array.from({ length: 14 }, (_, i) => ({ date: `2026-11-${13 + i}`, slots: i === 1 && !occupied ? [slot] : [] })) }));
    if (request.url.endsWith('/consultation')) return Promise.resolve(json(meeting));
    return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] }));
  });
  vi.stubGlobal('fetch', fetch);
  window.history.replaceState(null, '', '/#/booking?type=consultation');
  return { fetch, occupy: () => { occupied = true; } };
}
function button(wrapper: ReturnType<typeof mount>, label: string) { return wrapper.findAll('button').find((item) => item.text() === label)!; }
afterEach(() => { window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); });

test('выбор показывает итог, отдельное подтверждение блокирует изменения и показывает сохранённую запись', async () => {
  let resolve: (response: Response) => void = () => {};
  const { fetch } = api(() => new Promise<Response>((done) => { resolve = done; }));
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(button(wrapper, 'Подтвердить запись').attributes('disabled')).toBeDefined();
    await wrapper.get('[data-slot]').trigger('click');
    expect(wrapper.get('[aria-label="Итог записи"]').text()).toContain('Консультация');
    expect(wrapper.get('[aria-label="Итог записи"]').text()).toContain('45 минут');
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(button(wrapper, 'Подтвердить запись').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-slot]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-date]').attributes('disabled')).toBeDefined();
    expect(wrapper.find('a[href="#/booking?type=consultation"]').exists()).toBe(false);
    const request = fetch.mock.calls.map(([item]) => item).find((item) => item.method === 'POST')!;
    expect(await request.json()).toEqual({ meetingTypeId: 'consultation', startsAt: slot.startsAt });
    expect(request.headers.get('Idempotency-Key')).toMatch(/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i);
    resolve(json(booking, 201));
    await flushPromises();
    const success = wrapper.get('[aria-label="Запись подтверждена"]');
    expect(success.text()).toContain('Консультация');
    expect(success.text()).toContain('14 ноября 2026');
    expect(success.text()).toContain('09:00–09:45');
    expect(success.text()).toContain('45 минут');
    expect(success.text()).toContain('Europe/Moscow');
    await button(wrapper, 'Выбрать другое время').trigger('click');
    await flushPromises();
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(fetch.mock.calls.filter(([request]) => request.url.endsWith('/availability'))).toHaveLength(2);
  } finally { wrapper.unmount(); }
});

test('конфликт сохраняет тип и дату, сбрасывает слот и обновляет опустевший день', async () => {
  const control = api(async () => { control.occupy(); return json({ code: 'SLOT_CONFLICT', message: 'Это время уже занято. Выберите другой слот' }, 409); });
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Это время уже занято. Выберите другой слот');
    expect(wrapper.get('[data-date="2026-11-14"]').attributes('aria-pressed')).toBe('true');
    expect(wrapper.text()).toContain('В этот день нет свободного времени');
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация');
    expect(button(wrapper, 'Подтвердить запись').attributes('disabled')).toBeDefined();
  } finally { wrapper.unmount(); }
});

test.each(['network', 'technical', 'malformed'] as const)('неопределённый результат %s сохраняет ключ и исходный выбор для явного повтора', async (kind) => {
  let calls = 0;
  const control = api(async () => {
    calls++;
    if (calls > 1) return json(booking, 200);
    if (kind === 'network') throw new Error('lost response');
    if (kind === 'technical') return json({ code: 'SERVICE_UNAVAILABLE', message: 'Временно недоступно' }, 503);
    return json({ id: booking.id }, 201);
  });
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Результат записи неизвестен');
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(false);
    expect(wrapper.get('[data-date]').attributes('disabled')).toBeDefined();
    const before = control.fetch.mock.calls.length;
    window.dispatchEvent(new Event('focus'));
    await flushPromises();
    expect(control.fetch.mock.calls).toHaveLength(before);
    await button(wrapper, 'Повторить подтверждение').trigger('click');
    await flushPromises();
    const attempts = control.fetch.mock.calls.map(([request]) => request).filter((request) => request.method === 'POST');
    expect(attempts).toHaveLength(2);
    expect(attempts[0]!.headers.get('Idempotency-Key')).toBe(attempts[1]!.headers.get('Idempotency-Key'));
    expect(await attempts[0]!.json()).toEqual(await attempts[1]!.json());
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(true);
  } finally { wrapper.unmount(); }
});

test('отказ окна обновляет календарь и предлагает новый выбор', async () => {
  const control = api(async () => json({ code: 'OUTSIDE_BOOKING_WINDOW', message: 'Время вне окна записи. Выберите другой слот' }, 422));
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Время вне окна записи. Выберите другой слот');
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(control.fetch.mock.calls.filter(([request]) => request.url.endsWith('/availability'))).toHaveLength(2);
  } finally { wrapper.unmount(); }
});
