import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

const meeting = { id: 'consultation', name: 'Консультация', description: 'Вопросы', durationMinutes: 45 };
const slot = { startsAt: '2026-11-14T06:00:00Z', endsAt: '2026-11-14T06:45:00Z' };
const booking = { id: '070a4050-22f5-4465-a34c-046209ff8067', meetingTypeId: meeting.id, meetingTypeName: meeting.name, ...slot, durationMinutes: 45, timeZone: 'Europe/Moscow' };
function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function api(send: (request: Request) => Promise<Response>) {
  let occupied = false;
  let readsFailed = false;
  const fetch = vi.fn((request: Request) => {
    if (request.method === 'POST') return send(request);
    if (readsFailed) return Promise.reject(new Error('reads unavailable'));
    if (request.url.endsWith('/availability')) return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', timeZone: 'Europe/Moscow', windowStartDate: '2026-11-13', windowEndDate: '2026-11-26', days: Array.from({ length: 14 }, (_, i) => ({ date: `2026-11-${13 + i}`, slots: i === 1 && !occupied ? [slot] : [] })) }));
    if (request.url.endsWith('/consultation')) return Promise.resolve(json(meeting));
    if (request.url.endsWith('/bookings/upcoming')) return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', items: [] }));
    return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] }));
  });
  vi.stubGlobal('fetch', fetch);
  window.history.replaceState(null, '', '/#/booking?type=consultation');
  return { fetch, occupy: () => { occupied = true; }, failReads: () => { readsFailed = true; } };
}
function button(wrapper: ReturnType<typeof mount>, label: string) { return wrapper.findAll('button').find((item) => item.text() === label)!; }
afterEach(() => { window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); sessionStorage.clear(); vi.useRealTimers(); });

test('продолжение показывает итог, отдельное подтверждение блокирует изменения и показывает сохранённую запись', async () => {
  let resolve: (response: Response) => void = () => {};
  const { fetch } = api(() => new Promise<Response>((done) => { resolve = done; }));
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(button(wrapper, 'Продолжить').attributes('disabled')).toBeDefined();
    await wrapper.get('[data-slot]').trigger('click');
    expect(wrapper.find('[aria-label="Итог записи"]').exists()).toBe(false);
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(button(wrapper, 'Подтвердить запись').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[aria-label="Итог записи"]').text()).toContain('Консультация');
    expect(wrapper.get('[aria-label="Итог записи"]').text()).toContain('45 минут');
    expect(wrapper.find('[data-slot]').exists()).toBe(false);
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
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Это время уже занято. Выберите другой слот');
    expect(wrapper.get('[data-date="2026-11-14"]').attributes('aria-pressed')).toBe('true');
    expect(wrapper.text()).toContain('В этот день нет свободного времени');
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация');
    expect(button(wrapper, 'Продолжить').attributes('disabled')).toBeDefined();
  } finally { wrapper.unmount(); }
});

test.each(['network', 'technical', 'internal', 'malformed'] as const)('неопределённый результат %s сохраняет ключ и исходный выбор для явного повтора', async (kind) => {
  let calls = 0;
  const control = api(async () => {
    calls++;
    if (calls > 1) return json(booking, 200);
    if (kind === 'network') throw new Error('lost response');
    if (kind === 'internal') return json({ code: 'INTERNAL_ERROR', message: 'Ошибка' }, 500);
    if (kind === 'technical') return json({ code: 'SERVICE_UNAVAILABLE', message: 'Временно недоступно' }, 503);
    return json({ id: booking.id }, 201);
  });
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Результат записи неизвестен');
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(false);
    expect(wrapper.find('[data-date]').exists()).toBe(false);
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
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Время вне окна записи. Выберите другой слот');
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(control.fetch.mock.calls.filter(([request]) => request.url.endsWith('/availability'))).toHaveLength(2);
  } finally { wrapper.unmount(); }
});

test('перезагрузка сохраняет исходную попытку без автоматического POST даже вне окна и другого адреса', async () => {
  const control = api(async () => { throw new Error('lost'); });
  let wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    const first = control.fetch.mock.calls.map(([r]) => r).find((r) => r.method === 'POST')!;
    const payload = await first.clone().json();
    wrapper.unmount();
    window.history.replaceState(null, '', '/#/booking?type=other');
    wrapper = mount(App);
    await flushPromises();
    expect(wrapper.text()).toContain('Результат записи неизвестен');
    expect(wrapper.find('a[href="#/booking?type=consultation"]').exists()).toBe(false);
    expect(control.fetch.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(1);
    await button(wrapper, 'Повторить подтверждение').trigger('click');
    await flushPromises();
    const repeat = control.fetch.mock.calls.map(([r]) => r).filter((r) => r.method === 'POST')[1]!;
    expect(repeat.headers.get('Idempotency-Key')).toBe(first.headers.get('Idempotency-Key'));
    expect(await repeat.json()).toEqual(payload);
  } finally { wrapper.unmount(); sessionStorage.clear(); }
});

test('после 15 секунд явный повтор определяет исход, поздний ответ старой отправки игнорируется', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  let late: (response: Response) => void = () => {};
  let calls = 0;
  const control = api(async () => { calls++; if (calls === 1) return new Promise<Response>((done) => { late = done; }); return json(booking, 200); });
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(sessionStorage.length).toBe(1);
    await vi.advanceTimersByTimeAsync(14999);
    expect(wrapper.text()).toContain('Подтверждаем запись');
    await vi.advanceTimersByTimeAsync(1);
    await flushPromises();
    expect(wrapper.text()).toContain('Результат записи неизвестен');
    const first = control.fetch.mock.calls.map(([r]) => r).find((r) => r.method === 'POST')!;
    expect(first.signal.aborted).toBe(true);
    await button(wrapper, 'Повторить подтверждение').trigger('click');
    await flushPromises();
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(true);
    expect(sessionStorage.length).toBe(0);
    late(json({ code: 'SLOT_CONFLICT', message: 'Занято' }, 409));
    await flushPromises();
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Занято');
    expect(calls).toBe(2);
  } finally { wrapper.unmount(); }
});

test('успех завершает попытку, обычная перезагрузка не восстанавливает подтверждение', async () => {
  let storedBeforeSend: unknown;
  const control = api(async (request) => {
    storedBeforeSend = JSON.parse(sessionStorage.getItem(sessionStorage.key(0)!)!);
    expect(storedBeforeSend).toMatchObject({ key: request.headers.get('Idempotency-Key'), meetingTypeId: 'consultation', startsAt: slot.startsAt });
    return json(booking, 201);
  });
  let wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(sessionStorage.length).toBe(0);
    wrapper.unmount();
    wrapper = mount(App);
    await flushPromises();
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(control.fetch.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(1);
  } finally { wrapper.unmount(); }
});

test('ошибка сохранения в хранилище предотвращает отправку новой попытки', async () => {
  const control = api(async () => json(booking, 201));
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    const storage = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('quota'); });
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Не удалось сохранить попытку');
    expect(control.fetch.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(0);
    expect(button(wrapper, 'Подтвердить запись').attributes('disabled')).toBeDefined();
    storage.mockRestore();
  } finally { wrapper.unmount(); vi.restoreAllMocks(); }
});

test('однозначный отказ завершает сохранённую попытку и следующий выбор получает новый ключ', async () => {
  let calls = 0;
  const control = api(async () => { calls++; return calls === 1 ? json({ code: 'SLOT_CONFLICT', message: 'Занято' }, 409) : json(booking, 201); });
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(sessionStorage.length).toBe(0);
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    const requests = control.fetch.mock.calls.map(([r]) => r).filter((r) => r.method === 'POST');
    expect(requests[0]!.headers.get('Idempotency-Key')).not.toBe(requests[1]!.headers.get('Idempotency-Key'));
  } finally { wrapper.unmount(); }
});

test('восстановление не требует доступности каталога, типа или календаря', async () => {
  let calls = 0;
  const control = api(async () => { calls++; if (calls === 1) throw new Error('lost'); return json(booking, 200); });
  let wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    wrapper.unmount();
    control.failReads();
    window.history.replaceState(null, '', '/#/booking');
    wrapper = mount(App);
    await flushPromises();
    expect(wrapper.find('[aria-label="Типы встреч"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Результат записи неизвестен');
    expect(calls).toBe(1);
    await button(wrapper, 'Повторить подтверждение').trigger('click');
    await flushPromises();
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(true);
    expect(calls).toBe(2);
  } finally { wrapper.unmount(); }
});

test('нечитаемое хранилище блокирует подтверждение и не заменяется новой попыткой', async () => {
  sessionStorage.setItem('calendar.unfinishedBooking', '{');
  const control = api(async () => json(booking, 201));
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Не удалось сохранить попытку');
    expect(control.fetch.mock.calls.filter(([r]) => r.method === 'POST')).toHaveLength(0);
    expect(sessionStorage.getItem('calendar.unfinishedBooking')).toBe('{');
  } finally { wrapper.unmount(); }
});


test.each([
  ['pending', '#/owner', 'Страница владельца'],
  ['unknown', '#/owner', 'Страница владельца'],
  ['pending', '#/', 'Calendar'],
  ['unknown', '#/', 'Calendar'],
] as const)('при результате %s переход на %s сохраняет адрес страницы и исходную попытку при возвращении', async (state, destination, heading) => {
  let calls = 0;
  const control = api(async () => {
    calls++;
    if (calls > 1) return json(booking, 200);
    if (state === 'pending') return new Promise<Response>(() => {});
    throw new Error('lost response');
  });
  const wrapper = mount(App, { attachTo: document.body });
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    await button(wrapper, 'Продолжить').trigger('click');
    await button(wrapper, 'Подтвердить запись').trigger('click');
    await flushPromises();
    const first = control.fetch.mock.calls.map(([request]) => request).find((request) => request.method === 'POST')!;
    const payload = await first.clone().json();
    wrapper.get<HTMLAnchorElement>(`header a[href="${destination}"]`).element.click();
    await vi.waitFor(() => {
      expect(wrapper.get('h1').text()).toBe(heading);
      expect(window.location.hash).toBe(destination);
    });
    wrapper.get<HTMLAnchorElement>('header a[href="#/booking"]').element.click();
    await vi.waitFor(() => expect(wrapper.text()).toContain('Результат записи неизвестен'));
    expect(wrapper.get('h1').text()).toBe('Консультация');
    expect(window.location.hash).toBe('#/booking?type=consultation');
    expect(control.fetch.mock.calls.filter(([request]) => request.method === 'POST')).toHaveLength(1);
    await button(wrapper, 'Повторить подтверждение').trigger('click');
    await flushPromises();
    const repeat = control.fetch.mock.calls.map(([request]) => request).filter((request) => request.method === 'POST')[1]!;
    expect(repeat.headers.get('Idempotency-Key')).toBe(first.headers.get('Idempotency-Key'));
    expect(await repeat.json()).toEqual(payload);
    expect(wrapper.find('[aria-label="Запись подтверждена"]').exists()).toBe(true);
  } finally { wrapper.unmount(); }
});

test('продолжение открывает итог без POST и сохранения попытки, возврат сохраняет выбор', async () => {
  const { fetch } = api(async () => json(booking, 201));
  const wrapper = mount(App, { attachTo: document.body });
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    expect(wrapper.find('[aria-label="Итог записи"]').exists()).toBe(false);
    await button(wrapper, 'Продолжить').trigger('click');
    await flushPromises();
    expect(wrapper.get('[aria-label="Итог записи"]').text()).toContain('09:00–09:45');
    expect(document.activeElement).toBe(wrapper.get('.slots-panel > h2').element);
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
    expect(sessionStorage.length).toBe(0);
    await button(wrapper, 'Назад').trigger('click');
    expect(wrapper.find('[aria-label="Итог записи"]').exists()).toBe(false);
    expect(wrapper.get('[data-slot]').attributes('aria-pressed')).toBe('true');
    expect(button(wrapper, 'Продолжить').attributes('disabled')).toBeUndefined();
  } finally { wrapper.unmount(); }
});
