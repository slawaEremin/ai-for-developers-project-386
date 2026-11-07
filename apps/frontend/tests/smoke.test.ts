import { mount } from '@vue/test-utils';
import { expect, test } from 'vitest';
import App from '../src/App.vue';

test('корневая страница открывается и остаётся пустой', () => {
  const wrapper = mount(App, { attachTo: document.body });

  try {
    expect(document.body.contains(wrapper.element)).toBe(true);
    expect(wrapper.get('main').text()).toBe('');
    expect(wrapper.get('main').element.childElementCount).toBe(0);
  } finally {
    wrapper.unmount();
  }
});
