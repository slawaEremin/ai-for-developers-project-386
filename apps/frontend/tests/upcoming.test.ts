import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

const booking = {
  id: 'e4b1ab55-349b-43a1-8b3f-a32b179b0d99', meetingTypeId: 'consultation',
  meetingTypeName: 'Консультация', startsAt: '2026-11-14T07:00:00Z',
  endsAt: '2026-11-14T07:45:00Z', durationMinutes: 45, timeZone: 'Europe/Moscow',
};
const response = (items = [booking]) => new Response(JSON.stringify({ serverTime: '2026-11-12T12:00:00Z', items }),
  { headers: { 'Content-Type': 'application/json' } });

afterEach(() => {
  window.history.replaceState(null, '', '/');
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

test('при открытии страницы владельца список загружается отдельно от формы и показывает полную московскую запись', async () => {
  window.history.replaceState(null, '', '/#/owner');
  let resolve: (response: Response) => void = () => {};
  const fetch = vi.fn().mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  vi.stubGlobal('fetch', fetch);
  const wrapper = mount(App);
  try {
    expect(wrapper.text()).toContain('Загрузка встреч');
    await wrapper.get('#meeting-name').setValue('Черновик');
    expect(wrapper.get('fieldset').attributes('disabled')).toBeUndefined();
    resolve(response());
    await flushPromises();
    const request = fetch.mock.calls[0]?.[0] as Request;
    expect(new URL(request.url).pathname).toBe('/api/bookings/upcoming');
    const list = wrapper.get('[aria-labelledby="upcoming-title"]');
    expect(list.text()).toContain('Консультация');
    expect(list.text()).toContain('14 ноября 2026');
    expect(list.text()).toContain('10:00–10:45');
    expect(list.text()).toContain('45 мин');
    expect(list.text()).toContain('Europe/Moscow');
    expect(wrapper.get<HTMLInputElement>('#meeting-name').element.value).toBe('Черновик');
  } finally { wrapper.unmount(); }
});

test('пустой список отличается от ошибки и явный повтор восстанавливает загрузку', async () => {
  window.history.replaceState(null, '', '/#/owner');
  const fetch = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(response([]));
  vi.stubGlobal('fetch', fetch);
  const wrapper = mount(App);
  try {
    await flushPromises();
    const list = wrapper.get('[aria-labelledby="upcoming-title"]');
    expect(list.get('[role="alert"]').text()).toContain('Не удалось загрузить встречи');
    expect(list.text()).not.toContain('Предстоящих встреч пока нет');
    await list.get('button').trigger('click');
    await flushPromises();
    expect(list.text()).toContain('Предстоящих встреч пока нет');
    expect(list.find('[role="alert"]').exists()).toBe(false);
  } finally { wrapper.unmount(); }
});

test('ошибка обновления сохраняет отмеченный устаревший список и черновик, не мешая созданию типа', async () => {
  window.history.replaceState(null, '', '/#/owner');
  let resolve: (response: Response) => void = () => {};
  const fetch = vi.fn().mockResolvedValueOnce(response())
    .mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'new', name: 'Новый', description: 'Описание', durationMinutes: 30 }),
      { status: 201, headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fetch);
  const wrapper = mount(App);
  try {
    await flushPromises();
    await wrapper.get('#meeting-id').setValue('new');
    await wrapper.get('#meeting-name').setValue('Новый');
    await wrapper.get('#meeting-description').setValue('Описание');
    await wrapper.get('#meeting-duration').setValue('30');
    const list = wrapper.get('[aria-labelledby="upcoming-title"]');
    await list.get('button').trigger('click');
    expect(list.text()).toContain('Загрузка встреч');
    expect(list.text()).toContain('Консультация');
    expect(wrapper.get('fieldset').attributes('disabled')).toBeUndefined();
    resolve(new Response(JSON.stringify({ code: 'SERVICE_UNAVAILABLE', message: 'Недоступно' }), { status: 503, headers: { 'Content-Type': 'application/json' } }));
    await flushPromises();
    expect(list.get('[role="alert"]').text()).toContain('данные могли устареть');
    expect(list.text()).toContain('Консультация');
    expect(wrapper.get<HTMLInputElement>('#meeting-name').element.value).toBe('Новый');
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(wrapper.text()).toContain('Тип встречи «Новый» создан');
    expect(list.text()).toContain('Консультация');
    expect(fetch).toHaveBeenCalledTimes(3);
  } finally { wrapper.unmount(); }
});

test('возвращение во вкладку и ручное обновление убирают начавшиеся встречи, без опроса по таймеру', async () => {
  window.history.replaceState(null, '', '/#/owner');
  vi.useFakeTimers();
  const fetch = vi.fn().mockResolvedValueOnce(response()).mockResolvedValueOnce(response([])).mockResolvedValueOnce(response()).mockResolvedValueOnce(response([]));
  vi.stubGlobal('fetch', fetch);
  const wrapper = mount(App);
  try {
    await flushPromises();
    const list = wrapper.get('[aria-labelledby="upcoming-title"]');
    expect(list.text()).toContain('Консультация');
    await vi.advanceTimersByTimeAsync(60 * 60 * 1000);
    expect(fetch).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();
    expect(fetch).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();
    expect(list.text()).toContain('Предстоящих встреч пока нет');
    await list.get('button').trigger('click');
    await flushPromises();
    expect(list.text()).toContain('Консультация');
    window.dispatchEvent(new Event('focus'));
    await flushPromises();
    expect(list.text()).toContain('Предстоящих встреч пока нет');
    wrapper.unmount();
    document.dispatchEvent(new Event('visibilitychange'));
    window.dispatchEvent(new Event('focus'));
    await flushPromises();
    expect(fetch).toHaveBeenCalledTimes(4);
  } finally { if (wrapper.exists()) wrapper.unmount(); }
});
