import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from '../src/App.vue';

beforeEach(() => window.history.replaceState(null, '', '/'));
afterEach(() => window.history.replaceState(null, '', '/'));

test('главная объясняет сервис гостю и предупреждает о недоступности записи', () => {
  const wrapper = mount(App, { attachTo: document.body });

  try {
    expect(document.body.contains(wrapper.element)).toBe(true);
    expect(wrapper.get('h1').text()).toBe('Выберите удобное время для звонка.');
    expect(wrapper.get('main').text()).toContain('без регистрации');
    expect(wrapper.get('main').text()).toContain('Онлайн-запись пока недоступна.');
    expect(wrapper.get('a[href="#/booking"]').text()).toContain('Записаться');
  } finally {
    wrapper.unmount();
  }
});

test('гость переходит с главной к заглушке записи и возвращается назад', async () => {
  const wrapper = mount(App, { attachTo: document.body });

  try {
    wrapper.get<HTMLAnchorElement>('main a[href="#/booking"]').element.click();

    await vi.waitFor(() => {
      expect(wrapper.get('h1').text()).toBe('Запись на звонок скоро появится');
      expect(document.activeElement).toBe(wrapper.get('h1').element);
    });
    expect(document.title).toBe('Запись на звонок — Календарь звонков');

    wrapper.get<HTMLAnchorElement>('main a[href="#/"]').element.click();

    await vi.waitFor(() => {
      expect(wrapper.get('h1').text()).toBe('Выберите удобное время для звонка.');
      expect(document.activeElement).toBe(wrapper.get('h1').element);
    });
    expect(document.title).toBe('Календарь звонков');
  } finally {
    wrapper.unmount();
  }
});

test('заглушка открывается по прямой ссылке, а переход к содержимому сохраняет страницу', async () => {
  window.history.replaceState(null, '', '/#/booking');
  const wrapper = mount(App, { attachTo: document.body });

  try {
    expect(wrapper.get('h1').text()).toBe('Запись на звонок скоро появится');
    expect(document.title).toBe('Запись на звонок — Календарь звонков');

    await wrapper.get<HTMLAnchorElement>('a[href="#main"]').trigger('click');

    expect(document.activeElement).toBe(wrapper.get('main').element);
    expect(window.location.hash).toBe('#/booking');
    expect(wrapper.get('h1').text()).toBe('Запись на звонок скоро появится');
  } finally {
    wrapper.unmount();
  }
});
