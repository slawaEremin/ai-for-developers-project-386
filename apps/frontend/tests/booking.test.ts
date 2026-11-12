import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

const meeting = { id: 'consultation', name: 'Консультация', description: '<b>Вопросы</b>\n**Текст**', durationMinutes: 45 };
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
function stubFetch(transport: (request: Request) => unknown) {
  vi.stubGlobal('fetch', (request: Request) => request.url.endsWith('/availability')
    ? Promise.resolve(json({ serverTime: '2026-11-12T12:00:00Z', timeZone: 'Europe/Moscow', windowStartDate: '2026-11-13', windowEndDate: '2026-11-26', days: Array.from({ length: 14 }, (_, index) => ({ date: `2026-11-${13 + index}`, slots: [] })) }))
    : transport(request));
}
afterEach(() => {
  window.history.replaceState(null, '', '/');
  vi.unstubAllGlobals();
});

test('гость видит каталог и выбирает тип на той же странице с адресом только типа', async () => {
  window.history.replaceState(null, '', '/#/booking');
  stubFetch(vi.fn().mockResolvedValueOnce(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] })).mockResolvedValueOnce(json(meeting)));
  const wrapper = mount(App);
  try {
    expect(wrapper.text()).toContain('Загрузка каталога');
    await flushPromises();
    expect(wrapper.get('h1').text()).toBe('Запись на звонок');
    expect(wrapper.get('[aria-label="Типы встреч"]').text()).toContain('45 минут');
    expect(wrapper.find('b').exists()).toBe(false);
    expect(wrapper.text()).toContain('<b>Вопросы</b>');
    expect(wrapper.find('[aria-label="Выбранный тип встречи"]').exists()).toBe(false);
    wrapper.get<HTMLAnchorElement>('a[href="#/booking?type=consultation"]').element.click();
    await vi.waitFor(() => expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация'));
    expect(wrapper.find('[aria-label="Типы встреч"]').exists()).toBe(true);
    expect(window.location.hash).toBe('#/booking?type=consultation');
    expect(wrapper.text()).toContain('Календарь');
  } finally { wrapper.unmount(); }
});

test('ошибка каталога отличается от пустого результата и позволяет явный повтор', async () => {
  window.history.replaceState(null, '', '/#/booking');
  stubFetch(vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(json({ serverTime: '2026-11-12T12:00:00Z', items: [] })));
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('Не удалось загрузить каталог');
    expect(wrapper.text()).not.toContain('Владелец пока не создал');
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Владелец пока не создал типы встреч');
  } finally { wrapper.unmount(); }
});

test('неизвестный тип по прямой ссылке оставляет каталог доступным', async () => {
  window.history.replaceState(null, '', '/#/booking?type=missing');
  stubFetch(vi.fn().mockResolvedValueOnce(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] })).mockResolvedValueOnce(json({ code: 'MEETING_TYPE_NOT_FOUND', message: 'Тип встречи не найден' }, 404)));
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('Тип встречи не найден');
    expect(wrapper.get('[aria-label="Типы встреч"]').text()).toContain('Консультация');
    expect(wrapper.find('[aria-label="Выбранный тип встречи"]').exists()).toBe(false);
  } finally { wrapper.unmount(); }
});

test('прямая ссылка и повторное открытие страницы заново загружают выбранный тип', async () => {
  window.history.replaceState(null, '', '/#/booking?type=consultation');
  const fetch = vi.fn();
  for (const name of ['Консультация', 'Актуальное название']) {
    fetch.mockResolvedValueOnce(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] })).mockResolvedValueOnce(json({ ...meeting, name }));
  }
  stubFetch(fetch);
  const first = mount(App);
  await flushPromises();
  expect(first.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация');
  first.unmount();
  const reloaded = mount(App);
  try {
    await flushPromises();
    expect(reloaded.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Актуальное название');
    expect(window.location.hash).toBe('#/booking?type=consultation');
    for (const [request] of fetch.mock.calls) expect((request as Request).method).toBe('GET');
  } finally { reloaded.unmount(); }
});

test('ошибка получения выбранного типа позволяет повторить загрузку без потери каталога', async () => {
  window.history.replaceState(null, '', '/#/booking?type=consultation');
  stubFetch(vi.fn().mockResolvedValueOnce(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] })).mockResolvedValueOnce(json({ code: 'SERVICE_UNAVAILABLE', message: 'Недоступно' }, 503)).mockResolvedValueOnce(json(meeting)));
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('Не удалось загрузить выбранный тип');
    expect(wrapper.get('[aria-label="Типы встреч"]').text()).toContain('Консультация');
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация');
  } finally { wrapper.unmount(); }
});

test('поздний ответ предыдущего выбора не заменяет новый тип', async () => {
  window.history.replaceState(null, '', '/#/booking?type=slow');
  let resolve: (response: Response) => void = () => {};
  stubFetch(vi.fn().mockResolvedValueOnce(json({ serverTime: '2026-11-12T12:00:00Z', items: [meeting] })).mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; })).mockResolvedValueOnce(json(meeting)));
  const wrapper = mount(App);
  try {
    await flushPromises();
    expect(wrapper.text()).toContain('Загрузка выбранного типа');
    wrapper.get<HTMLAnchorElement>('a[href="#/booking?type=consultation"]').element.click();
    await vi.waitFor(() => expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).toContain('Консультация'));
    resolve(json({ ...meeting, id: 'slow', name: 'Старый тип' }));
    await flushPromises();
    expect(wrapper.get('[aria-label="Выбранный тип встречи"]').text()).not.toContain('Старый тип');
  } finally { wrapper.unmount(); }
});
