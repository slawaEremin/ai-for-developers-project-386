import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

// Форма и список обращаются к разным публичным HTTP-операциям.
function installFormFetch(formFetch: (request: Request) => Promise<Response>) {
  vi.stubGlobal('fetch', (request: Request) => new URL(request.url).pathname === '/api/bookings/upcoming'
    ? Promise.resolve(new Response(JSON.stringify({ serverTime: '2026-11-12T12:00:00Z', items: [] }), { headers: { 'Content-Type': 'application/json' } }))
    : formFetch(request));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
  vi.unstubAllGlobals();
});

test('владелец отправляет форму через API, видит подтверждение и очищенные поля', async () => {
  window.history.replaceState(null, '', '/#/owner');
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    id: 'consultation', name: 'Консультация', description: 'Вопросы', durationMinutes: 45,
  }), { status: 201, headers: { 'Content-Type': 'application/json' } }));
  installFormFetch(fetch);
  const wrapper = mount(App);
  try {
    expect(wrapper.get('h1').text()).toBe('Страница владельца');
    await wrapper.get('#meeting-id').setValue('consultation');
    await wrapper.get('#meeting-name').setValue('Консультация');
    await wrapper.get('#meeting-description').setValue('Вопросы');
    await wrapper.get('#meeting-duration').setValue('45');
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(fetch).toHaveBeenCalledOnce();
    const request = fetch.mock.calls[0]?.[0] as Request;
    expect(new URL(request.url).pathname).toBe('/api/meeting-types');
    expect(await request.json()).toEqual({
      id: 'consultation', name: 'Консультация', description: 'Вопросы', durationMinutes: 45,
    });
    expect(wrapper.get('[role="status"]').text()).toContain('Тип встречи «Консультация» создан');
    expect(wrapper.find<HTMLAnchorElement>('main a[href="#/booking?type=consultation"]').exists()).toBe(true);
    expect(wrapper.get<HTMLInputElement>('#meeting-id').element.value).toBe('');
  } finally { wrapper.unmount(); }
});

async function completeForm(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('#meeting-id').setValue('consultation');
  await wrapper.get('#meeting-name').setValue('Консультация');
  await wrapper.get('#meeting-description').setValue('Вопросы');
  await wrapper.get('#meeting-duration').setValue('30');
}

test('поля проверяются при отправке и ошибки обновляются после исправления без запроса', async () => {
  window.history.replaceState(null, '', '/#/owner');
  const fetch = vi.fn();
  installFormFetch(fetch);
  const wrapper = mount(App);
  try {
    expect(wrapper.find('.field-error').exists()).toBe(false);
    await wrapper.get('form').trigger('submit');
    expect(wrapper.findAll('.field-error')).toHaveLength(4);
    expect(fetch).not.toHaveBeenCalled();
    await completeForm(wrapper);
    expect(wrapper.find('.field-error').exists()).toBe(false);
    await wrapper.get('#meeting-name').setValue('😀'.repeat(120));
    expect(wrapper.find('#error-name').exists()).toBe(false);
    await wrapper.get('#meeting-name').setValue('😀'.repeat(121));
    expect(wrapper.find('#error-name').exists()).toBe(true);
  } finally { wrapper.unmount(); }
});

test('во время запроса форма заблокирована, конфликт сохраняет ввод и исправляется', async () => {
  window.history.replaceState(null, '', '/#/owner');
  let resolve: (response: Response) => void = () => {};
  const fetch = vi.fn().mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  installFormFetch(fetch);
  const wrapper = mount(App);
  try {
    await completeForm(wrapper);
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined();
    await wrapper.get('form').trigger('submit');
    expect(fetch).toHaveBeenCalledOnce();
    resolve(new Response(JSON.stringify({ code: 'MEETING_TYPE_ID_CONFLICT', message: 'Тип уже существует', fieldErrors: { id: 'Этот id занят' } }), { status: 409, headers: { 'Content-Type': 'application/json' } }));
    await flushPromises();
    expect(wrapper.get('#error-id').text()).toContain('занят');
    expect(wrapper.get<HTMLInputElement>('#meeting-name').element.value).toBe('Консультация');
    expect(wrapper.get('fieldset').attributes('disabled')).toBeUndefined();
    await wrapper.get('#meeting-id').setValue('another');
    expect(wrapper.find('#error-id').exists()).toBe(false);
  } finally { wrapper.unmount(); }
});

test('при потере ответа владелец сохраняет ввод и проверяет каталог без автоматического повтора', async () => {
  window.history.replaceState(null, '', '/#/owner');
  const fetch = vi.fn().mockRejectedValue(new TypeError('Network error'));
  installFormFetch(fetch);
  const wrapper = mount(App);
  try {
    await completeForm(wrapper);
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('Проверьте каталог');
    expect(wrapper.get('[role="alert"] a').attributes('href')).toBe('#/booking?type=consultation');
    expect(wrapper.get<HTMLInputElement>('#meeting-id').element.value).toBe('consultation');
    expect(fetch).toHaveBeenCalledOnce();
  } finally { wrapper.unmount(); }
});

test('с главной есть переход владельцу без входа', async () => {
  const wrapper = mount(App, { attachTo: document.body });
  try {
    wrapper.get<HTMLAnchorElement>('a[href="#/owner"]').element.click();
    await vi.waitFor(() => expect(wrapper.get('h1').text()).toBe('Страница владельца'));
    expect(document.title).toBe('Владелец — Календарь звонков');
    expect(document.activeElement).toBe(wrapper.get('h1').element);
  } finally { wrapper.unmount(); }
});
