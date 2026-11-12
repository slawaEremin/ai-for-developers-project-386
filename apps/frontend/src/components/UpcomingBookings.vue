<script setup lang="ts">
import { formatMoscowDate, formatMoscowInterval } from '../moscowTime';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { listUpcomingBookings } from '../api/generated/sdk.gen';
import type { UpcomingBookings } from '../api/generated/types.gen';

const data = ref<UpcomingBookings | null>(null);
const loading = ref(true);
const failed = ref(false);
let request = 0;

async function refresh() {
  const current = ++request;
  loading.value = true;
  failed.value = false;
  try {
    const result = await listUpcomingBookings({ baseUrl: window.location.origin });
    if (current !== request) return;
    if (!result.data || !Array.isArray(result.data.items)) throw new Error('Upcoming bookings unavailable');
    data.value = result.data;
  } catch { if (current === request) failed.value = true; }
  finally { if (current === request) loading.value = false; }
}
function onVisibility() { if (document.visibilityState === 'visible') void refresh(); }
onMounted(() => {
  void refresh();
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('focus', onVisibility);
});
onBeforeUnmount(() => {
  request++;
  document.removeEventListener('visibilitychange', onVisibility);
  window.removeEventListener('focus', onVisibility);
});
</script>

<template>
  <section
    class="upcoming"
    aria-labelledby="upcoming-title"
  >
    <h2 id="upcoming-title">
      Предстоящие встречи
    </h2>
    <p
      v-if="loading"
      role="status"
    >
      Загрузка встреч…
    </p>
    <p
      v-if="failed"
      role="alert"
    >
      Не удалось загрузить встречи. {{ data ? 'Показан последний загруженный список; данные могли устареть.' : 'Повторите загрузку.' }}
    </p>
    <button
      type="button"
      class="button button-secondary"
      :disabled="loading"
      @click="refresh"
    >
      {{ failed ? 'Повторить загрузку встреч' : 'Обновить встречи' }}
    </button>
    <p v-if="!loading && !failed && data && !data.items.length">
      Предстоящих встреч пока нет.
    </p>
    <ul v-if="data?.items.length">
      <li
        v-for="booking in data.items"
        :key="booking.id"
      >
        <h3>{{ booking.meetingTypeName }}</h3>
        <p>{{ formatMoscowDate(booking.startsAt) }} · {{ formatMoscowInterval(booking) }}</p>
        <p>{{ booking.durationMinutes }} мин · Москва (Europe/Moscow)</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.upcoming { margin-top: 3rem; border-top: 1px solid #d7dbd5; padding-top: 2rem; }
ul { list-style: none; padding: 0; }
li { padding-block: 1rem; border-bottom: 1px solid #d7dbd5; }
h3 { margin: 0; }
p { margin-block: .6rem; }
</style>
