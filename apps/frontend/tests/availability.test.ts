import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

const meeting = { id: 'consultation', name: 'Консультация', description: 'Вопросы', durationMinutes: 45 };
const slot = { startsAt: '2026-11-14T06:00:00Z', endsAt: '2026-11-14T06:45:00Z' };
function availability() {
  return { serverTime: '2026-11-12T12:00:00Z', timeZone: 'Europe/Moscow', windowStartDate: '2026-11-13', windowEndDate: '2026-11-26', days: Array.from({ length: 14 }, (_, i) => ({ date: `2026-11-${13 + i}`, slots: i === 1 ? [slot] : [] })) };
}
function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function api(load: () => Promise<Response>) {
  const fetch = vi.fn((request: Request) => {
    if (request.url.endsWith('/availability')) return load();
    if (request.url.endsWith('/consultation')) return Promise.resolve(json(meeting));
    return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] }));
  });
  vi.stubGlobal('fetch', fetch);
  window.history.replaceState(null, '', '/#/booking?type=consultation');
  return fetch;
}
afterEach(() => { window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); vi.useRealTimers(); });

test('календарь показывает все дни, выбирает ближайший свободный и полный московский интервал', async () => {
  const fetch = api(async () => json(availability()));
  const wrapper = mount(App);
  try {
    await flushPromises();
    const calendar = wrapper.get('[aria-label="Календарь"]');
    expect(wrapper.get('[aria-label="Типы встреч"]').text()).toContain('Консультация');
    expect(calendar.findAll('[data-date]')).toHaveLength(14);
    expect(calendar.get('[data-date="2026-11-14"]').attributes('aria-pressed')).toBe('true');
    expect(calendar.text()).toContain('14 ноября 2026');
    expect(calendar.text()).toContain('09:00–09:45');
    expect(calendar.text()).toContain('Europe/Moscow');
    await calendar.get('[data-slot]').trigger('click');
    expect(calendar.text()).toContain('Выбрано:');
    expect(window.location.hash).toBe('#/booking?type=consultation');
    await calendar.get('[data-date="2026-11-13"]').trigger('click');
    expect(calendar.text()).toContain('В этот день нет свободного времени');
    expect(calendar.text()).not.toContain('Выбрано:');
    for (const [request] of fetch.mock.calls) expect(request.method).toBe('GET');
  } finally { wrapper.unmount(); }
});

test('загрузка, ошибка с повтором и пустое окно различаются', async () => {
  let reject: (reason: Error) => void = () => {};
  let resolve: (response: Response) => void = () => {};
  let pending = new Promise<Response>((_, fail) => { reject = fail; });
  api(() => pending);
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(wrapper.text()).toContain('Загрузка доступности');
    expect(wrapper.find('[data-slot]').exists()).toBe(false);
    reject(new Error('offline'));
    await flushPromises();
    expect(wrapper.text()).toContain('Не удалось загрузить доступность');
    expect(wrapper.text()).not.toContain('Во всём окне нет свободного времени');
    pending = new Promise<Response>((done) => { resolve = done; });
    await wrapper.get('[aria-label="Календарь"] button').trigger('click');
    expect(wrapper.text()).toContain('Загрузка доступности');
    resolve(json({ ...availability(), days: availability().days.map((day) => ({ ...day, slots: [] })) }));
    await flushPromises();
    expect(wrapper.text()).toContain('Во всём окне нет свободного времени');
    expect(wrapper.findAll('[data-date]')).toHaveLength(14);
    expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация');
  } finally { wrapper.unmount(); }
});

test('возвращение во вкладку сохраняет допустимую дату и сообщает об исчезнувшем слоте', async () => {
  let next = Promise.resolve(json(availability()));
  api(() => next);
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    let resolve: (response: Response) => void = () => {};
    next = new Promise<Response>((done) => { resolve = done; });
    window.dispatchEvent(new Event('focus'));
    await flushPromises();
    expect(wrapper.text()).toContain('Загрузка доступности');
    expect(wrapper.find('[data-slot]').exists()).toBe(false);
    const updated = availability();
    updated.days[1]!.slots = [];
    updated.days[2]!.slots = [{ startsAt: '2026-11-15T06:00:00Z', endsAt: '2026-11-15T06:45:00Z' }];
    resolve(json(updated));
    await flushPromises();
    expect(wrapper.get('[data-date="2026-11-14"]').attributes('aria-pressed')).toBe('true');
    expect(wrapper.text()).toContain('В этот день нет свободного времени');
    expect(wrapper.text()).toContain('Выбранный интервал больше недоступен');
    expect(wrapper.text()).not.toContain('Выбрано:');
    next = Promise.resolve(json({ ...updated, windowStartDate: '2026-11-15', windowEndDate: '2026-11-28', days: [...updated.days.slice(2), { date: '2026-11-27', slots: [] }, { date: '2026-11-28', slots: [] }] }));
    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();
    expect(wrapper.get('[data-date="2026-11-15"]').attributes('aria-pressed')).toBe('true');
    await wrapper.get('[data-slot]').trigger('click');
    expect(wrapper.text()).not.toContain('Выбранный интервал больше недоступен');
  } finally { wrapper.unmount(); }
});

test('московская полночь обновляет окно по серверному времени независимо от часов устройства', async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] });
  vi.setSystemTime(new Date('2026-01-01T01:00:00Z'));
  let body = { ...availability(), serverTime: '2026-11-12T20:59:59Z' };
  api(async () => json(body));
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-date="2026-11-13"]').trigger('click');
    const next = availability();
    body = { ...next, serverTime: '2026-11-12T21:00:00Z', windowStartDate: '2026-11-14', windowEndDate: '2026-11-27', days: [...next.days.slice(1), { date: '2026-11-27', slots: [] }] };
    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();
    expect(wrapper.find('[data-date="2026-11-13"]').exists()).toBe(false);
    expect(wrapper.get('[data-date="2026-11-14"]').attributes('aria-pressed')).toBe('true');
    expect(wrapper.text()).toContain('09:00–09:45');
  } finally { wrapper.unmount(); }
});

test('смена типа сбрасывает дату и слот, поздняя доступность прежнего типа не заменяет новую', async () => {
  const short = { ...meeting, id: 'short', name: 'Короткая встреча', durationMinutes: 30 };
  let resolve: (response: Response) => void = () => {};
  let slow = false;
  const fetch = vi.fn((request: Request) => {
    if (request.url.endsWith('/consultation/availability')) return slow ? new Promise<Response>((done) => { resolve = done; }) : Promise.resolve(json(availability()));
    if (request.url.endsWith('/short/availability')) {
      const shortData = availability();
      shortData.days[1]!.slots = [{ startsAt: '2026-11-14T07:00:00Z', endsAt: '2026-11-14T07:30:00Z' }];
      return Promise.resolve(json(shortData));
    }
    if (request.url.endsWith('/consultation')) return Promise.resolve(json(meeting));
    if (request.url.endsWith('/short')) return Promise.resolve(json(short));
    return Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting, short] }));
  });
  vi.stubGlobal('fetch', fetch);
  window.history.replaceState(null, '', '/#/booking?type=consultation');
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('[data-slot]').trigger('click');
    expect(wrapper.text()).toContain('Выбрано:');
    slow = true;
    window.dispatchEvent(new Event('focus'));
    await flushPromises();
    window.history.replaceState(null, '', '/#/booking?type=short');
    window.dispatchEvent(new Event('hashchange'));
    await flushPromises();
    expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Короткая встреча');
    expect(wrapper.text()).not.toContain('Выбрано:');
    expect(wrapper.text()).toContain('10:00–10:30');
    resolve(json(availability()));
    await flushPromises();
    expect(wrapper.text()).toContain('10:00–10:30');
    expect(wrapper.text()).not.toContain('09:00–09:45');
    await wrapper.get('[data-slot]').trigger('click');
    await wrapper.get('[data-date="2026-11-15"]').trigger('click');
    wrapper.unmount();
    const reloaded = mount(App);
    try {
      await flushPromises();
      expect(reloaded.get('[data-date="2026-11-14"]').attributes('aria-pressed')).toBe('true');
      expect(reloaded.text()).not.toContain('Выбрано:');
      for (const [request] of fetch.mock.calls) expect(request.method).toBe('GET');
    } finally { reloaded.unmount(); }
  } finally { if (wrapper.exists()) wrapper.unmount(); }
});
