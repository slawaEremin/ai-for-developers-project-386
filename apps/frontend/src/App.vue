<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import BookingPage from './pages/BookingPage.vue';
import HomePage from './pages/HomePage.vue';
import OwnerPage from './pages/OwnerPage.vue';

function currentPage() {
  const hash = window.location.hash.split('?')[0];
  return hash === '#/owner' || hash === '#/booking' ? hash : '#/';
}

const page = ref(currentPage());
const main = ref<HTMLElement | null>(null);

function updateTitle() {
  document.title = page.value === '#/owner' ? 'Владелец — Календарь звонков' : page.value === '#/booking' ? 'Запись на звонок — Календарь звонков' : 'Календарь звонков';
}

async function syncPage() {
  const nextPage = currentPage();
  if (nextPage === page.value) return;
  page.value = nextPage;
  updateTitle();
  await nextTick();
  main.value?.querySelector('h1')?.focus();
}

onMounted(() => {
  updateTitle();
  window.addEventListener('hashchange', syncPage);
});
onBeforeUnmount(() => window.removeEventListener('hashchange', syncPage));
</script>

<template>
  <a
    class="skip-link"
    href="#main"
    @click.prevent="main?.focus()"
  >К содержимому</a>
  <div
    class="app-shell"
    :class="{ 'app-home': page === '#/' }"
  >
    <header class="site-header">
      <div class="container header-content">
        <a
          class="brand"
          href="#/"
          aria-label="Calendar — главная"
        >
          <svg
            class="brand-mark"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <path d="M8 2v4m8-4v4M3 10h9M9 21H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4" />
            <circle
              cx="16"
              cy="16"
              r="6"
            />
            <path d="M16 13v3l2 1" />
          </svg>
          <span>Calendar</span>
        </a>
        <nav aria-label="Основная навигация">
          <a
            class="nav-link"
            href="#/booking"
            :aria-current="page === '#/booking' ? 'page' : undefined"
          >Записаться</a>
          <a
            class="nav-link"
            href="#/owner"
            :aria-current="page === '#/owner' ? 'page' : undefined"
          >Админка</a>
        </nav>
      </div>
    </header>
    <main
      id="main"
      ref="main"
      tabindex="-1"
    >
      <BookingPage v-if="page === '#/booking'" />
      <OwnerPage v-else-if="page === '#/owner'" />
      <HomePage v-else />
    </main>
  </div>
</template>
