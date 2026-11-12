<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { getAvailability } from '../api/generated/sdk.gen';
import type { Availability, AvailableSlot } from '../api/generated/types.gen';

const props = defineProps<{ meetingTypeId: string }>();
const data = ref<Availability | null>(null);
const selectedDate = ref('');
const selectedSlot = ref<AvailableSlot | null>(null);
const loading = ref(true);
const failed = ref(false);
const notice = ref('');
let request = 0;
let rolloverTimer: ReturnType<typeof setTimeout> | undefined;
const day = computed(() => data.value?.days.find((item) => item.date === selectedDate.value));
const dateFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', day: 'numeric', month: 'long', year: 'numeric' });
const timeFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
function dateLabel(date: string) { return dateFormat.format(new Date(`${date}T09:00:00+03:00`)); }
function interval(slot: AvailableSlot) { return `${timeFormat.format(new Date(slot.startsAt))}–${timeFormat.format(new Date(slot.endsAt))}`; }
function chooseSlot(slot: AvailableSlot) { selectedSlot.value = slot; notice.value = ''; }
function chooseDate(date: string) { selectedDate.value = date; selectedSlot.value = null; notice.value = ''; }
function scheduleRollover(serverTime: string) {
  clearTimeout(rolloverTimer);
  const now = new Date(serverTime);
  const moscow = new Date(now.getTime() + 3 * 60 * 60 * 1000);
  const midnight = Date.UTC(moscow.getUTCFullYear(), moscow.getUTCMonth(), moscow.getUTCDate() + 1) - 3 * 60 * 60 * 1000;
  rolloverTimer = setTimeout(() => { void refresh(); }, Math.max(1, midnight - now.getTime()));
}
async function refresh() {
  const current = ++request;
  loading.value = true;
  failed.value = false;
  try {
    const result = await getAvailability({ baseUrl: window.location.origin, path: { id: props.meetingTypeId } });
    if (current !== request) return;
    if (!result.data) throw new Error('Availability unavailable');
    data.value = result.data;
    scheduleRollover(result.data.serverTime);
    if (!result.data.days.some((item) => item.date === selectedDate.value)) {
      selectedDate.value = result.data.days.find((item) => item.slots.length)?.date ?? result.data.days[0]?.date ?? '';
    }
    if (selectedSlot.value && !day.value?.slots.some((slot) => slot.startsAt === selectedSlot.value?.startsAt && slot.endsAt === selectedSlot.value?.endsAt)) {
      selectedSlot.value = null;
      notice.value = 'Выбранный интервал больше недоступен. Выберите другое время.';
    }
  } catch { if (current === request) failed.value = true; }
  finally { if (current === request) loading.value = false; }
}
function onVisibility() { if (document.visibilityState === 'visible') void refresh(); }
onMounted(() => {
  void refresh();
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', onVisibility);
});
onBeforeUnmount(() => {
  request++;
  clearTimeout(rolloverTimer);
  window.removeEventListener('focus', refresh);
  document.removeEventListener('visibilitychange', onVisibility);
});
</script>

<template>
  <section aria-label="Календарь">
    <h3>Календарь</h3>
    <p>Московское время (Europe/Moscow), UTC+03:00</p>
    <p
      v-if="loading"
      role="status"
    >
      Загрузка доступности…
    </p>
    <div
      v-else-if="failed"
      role="alert"
    >
      <p>Не удалось загрузить доступность.</p>
      <button
        class="button button-secondary"
        @click="refresh"
      >
        Повторить загрузку доступности
      </button>
    </div>
    <template v-else-if="data">
      <p
        v-if="notice"
        role="status"
      >
        {{ notice }}
      </p>
      <p v-if="data.days.every((item) => item.slots.length === 0)">
        Во всём окне нет свободного времени.
      </p>
      <div
        class="dates"
        aria-label="Даты окна записи"
      >
        <button
          v-for="item in data.days"
          :key="item.date"
          class="button button-secondary"
          :data-date="item.date"
          :aria-pressed="selectedDate === item.date"
          @click="chooseDate(item.date)"
        >
          {{ dateLabel(item.date) }}
        </button>
      </div>
      <h4 v-if="selectedDate">
        {{ dateLabel(selectedDate) }}
      </h4>
      <p v-if="day?.slots.length === 0">
        В этот день нет свободного времени.
      </p>
      <div
        v-else
        class="slots"
      >
        <button
          v-for="slot in day?.slots"
          :key="slot.startsAt"
          class="button button-secondary"
          :data-slot="slot.startsAt"
          :aria-pressed="selectedSlot?.startsAt === slot.startsAt"
          @click="chooseSlot(slot)"
        >
          {{ interval(slot) }}
        </button>
      </div>
      <p
        v-if="selectedSlot"
        role="status"
      >
        Выбрано: {{ dateLabel(selectedDate) }}, {{ interval(selectedSlot) }}. Московское время (Europe/Moscow).
      </p>
      <p>Подтверждение записи скоро появится.</p>
    </template>
  </section>
</template>

<style scoped>
.dates, .slots { display: flex; flex-wrap: wrap; gap: .5rem; margin-block: 1rem; }
[aria-pressed="true"] { outline: 3px solid #315b41; outline-offset: 2px; }
</style>
