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
const isBooking = ref(page.value === '#/booking');
const main = ref<HTMLElement | null>(null);

function updateTitle() {
  document.title = page.value === '#/owner' ? 'Владелец — Календарь звонков' : isBooking.value ? 'Запись на звонок — Календарь звонков' : 'Календарь звонков';
}

async function syncPage() {
  const nextPage = currentPage();
  if (nextPage === page.value) return;
  page.value = nextPage;
  isBooking.value = nextPage === '#/booking';
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
  <div class="app-shell">
    <header class="site-header container">
      <a
        class="brand"
        href="#/"
        aria-label="Календарь звонков — главная"
      >
        <svg
          class="brand-mark"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <rect
            width="32"
            height="32"
            rx="10"
            fill="currentColor"
          />
          <path
            d="M10 8v4m12-4v4M8 15h16M10 10h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V12a2 2 0 0 1 2-2Z"
            stroke="white"
            stroke-width="1.7"
            stroke-linecap="round"
          />
          <path
            d="m12 20 3 3 5-5"
            stroke="white"
            stroke-width="1.7"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span>Календарь звонков</span>
      </a>
      <nav aria-label="Основная навигация">
        <a
          class="nav-link"
          href="#/owner"
        >Владельцу</a>
        <a
          v-if="!isBooking"
          class="nav-link"
          href="#how-it-works"
        >Как это работает</a>
        <a
          v-else
          class="nav-link"
          href="#/"
        >На главную</a>
        <a
          v-if="!isBooking"
          class="button button-small button-secondary"
          href="#/booking"
        >
          Записаться <span aria-hidden="true">→</span>
        </a>
      </nav>
    </header>

    <main
      id="main"
      ref="main"
      tabindex="-1"
    >
      <BookingPage v-if="isBooking" />
      <OwnerPage v-else-if="page === '#/owner'" />
      <HomePage v-else />
    </main>

    <footer class="site-footer container">
      <span class="footer-brand">Календарь звонков</span>
      <span>Удобное время. Хороший разговор.</span>
    </footer>
  </div>
</template>
