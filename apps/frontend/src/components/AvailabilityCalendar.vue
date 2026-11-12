<script setup lang="ts">
import { clearAttempt, restoreAttempt, saveAttempt, type BookingAttempt } from '../bookingAttempt';
import { formatMoscowDate, formatMoscowInterval, formatMoscowTime } from '../moscowTime';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { createBooking, getAvailability } from '../api/generated/sdk.gen';
import type { Availability, AvailableSlot, Booking } from '../api/generated/types.gen';

const props = defineProps<{ meetingTypeId: string; meetingTypeName: string; durationMinutes: number }>();
const emit = defineEmits<{ locked: [value: boolean] }>();
const pending = ref(false);
const unknown = ref(false);
const confirmed = ref<Booking | null>(null);
let attempt: BookingAttempt | null = null;
const storageFailed = ref(false);
try { attempt = restoreAttempt(); unknown.value = !!attempt; } catch { storageFailed.value = true; }
if (attempt) emit('locked', true);
const locked = computed(() => pending.value || unknown.value);
const data = ref<Availability | null>(null);
const selectedDate = ref(attempt?.startsAt.slice(0, 10) ?? '');
const selectedSlot = ref<AvailableSlot | null>(null);
const loading = ref(true);
const failed = ref(false);
const notice = ref('');
let request = 0;
let bookingRequest = 0;
let bookingController: AbortController | undefined;
let bookingTimer: ReturnType<typeof setTimeout> | undefined;
let rolloverTimer: ReturnType<typeof setTimeout> | undefined;
const day = computed(() => data.value?.days.find((item) => item.date === selectedDate.value));
function dateLabel(date: string) { return formatMoscowDate(`${date}T09:00:00+03:00`); }
function chooseSlot(slot: AvailableSlot) { if (locked.value) return; selectedSlot.value = slot; notice.value = ''; }
function chooseDate(date: string) { if (locked.value) return; selectedDate.value = date; selectedSlot.value = null; notice.value = ''; }
function scheduleRollover(serverTime: string) {
  clearTimeout(rolloverTimer);
  const now = new Date(serverTime);
  const moscow = new Date(now.getTime() + 3 * 60 * 60 * 1000);
  const midnight = Date.UTC(moscow.getUTCFullYear(), moscow.getUTCMonth(), moscow.getUTCDate() + 1) - 3 * 60 * 60 * 1000;
  rolloverTimer = setTimeout(() => { void refresh(); }, Math.max(1, midnight - now.getTime()));
}
async function refresh() {
  if (locked.value || confirmed.value) return;
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
function isBooking(value: Booking): boolean {
  return typeof value.id === 'string' && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value.id)
    && value.meetingTypeId === attempt!.meetingTypeId && typeof value.meetingTypeName === 'string'
    && value.durationMinutes === props.durationMinutes && value.timeZone === 'Europe/Moscow'
    && Number.isFinite(Date.parse(value.startsAt)) && Date.parse(value.startsAt) === Date.parse(attempt!.startsAt)
    && Date.parse(value.endsAt) - Date.parse(value.startsAt) === value.durationMinutes * 60000;
}
async function confirmBooking() {
  if (pending.value || storageFailed.value || (!attempt && !selectedSlot.value)) return;
  if (!attempt) {
    const original = { key: crypto.randomUUID(), meetingTypeId: props.meetingTypeId, startsAt: selectedSlot.value!.startsAt, meetingTypeName: props.meetingTypeName, durationMinutes: props.durationMinutes };
    try { saveAttempt(original); attempt = original; }
    catch { storageFailed.value = true; return; }
  }
  pending.value = true;
  unknown.value = false;
  emit('locked', true);
  const current = ++bookingRequest;
  bookingController = new AbortController();
  bookingTimer = setTimeout(() => {
    if (current !== bookingRequest) return;
    bookingRequest++;
    bookingController?.abort();
    pending.value = false;
    unknown.value = true;
    emit('locked', true);
  }, 15000);
  const timer = bookingTimer;
  try {
    const result = await createBooking({ baseUrl: window.location.origin, signal: bookingController.signal,
      headers: { 'Idempotency-Key': attempt.key },
      body: { meetingTypeId: attempt.meetingTypeId, startsAt: attempt.startsAt } });
    if (current !== bookingRequest) return;
    if ((result.response?.status === 200 || result.response?.status === 201) && result.data && isBooking(result.data)) {
      confirmed.value = result.data;
      selectedSlot.value = null;
      try { clearAttempt(); } catch { storageFailed.value = true; }
      attempt = null;
      notice.value = '';
    } else if (result.error && ['SLOT_CONFLICT', 'OUTSIDE_BOOKING_WINDOW', 'INVALID_SLOT', 'MEETING_TYPE_NOT_FOUND', 'IDEMPOTENCY_KEY_REUSED', 'VALIDATION_ERROR'].includes(result.error.code)
      && typeof result.error.message === 'string' && result.error.message.length > 0
      && ({ SLOT_CONFLICT: 409, OUTSIDE_BOOKING_WINDOW: 422, INVALID_SLOT: 422, MEETING_TYPE_NOT_FOUND: 404, IDEMPOTENCY_KEY_REUSED: 409, VALIDATION_ERROR: 422 } as Record<string, number>)[result.error.code] === result.response?.status) {
      notice.value = result.error.code === 'SLOT_CONFLICT' ? 'Это время уже занято. Выберите другой слот' : result.error.message;
      selectedSlot.value = null;
      try { clearAttempt(); } catch { storageFailed.value = true; }
      attempt = null;
    } else { unknown.value = true; }
  } catch { if (current === bookingRequest) unknown.value = true; }
  finally {
    clearTimeout(timer);
    if (current === bookingRequest) {
      pending.value = false;
      emit('locked', unknown.value);
      if (!unknown.value && !confirmed.value) await refresh();
    }
  }
}
async function chooseAnother() {
  confirmed.value = null;
  selectedSlot.value = null;
  notice.value = '';
  await refresh();
}
function onVisibility() { if (document.visibilityState === 'visible') void refresh(); }
onMounted(() => {
  void refresh();
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', onVisibility);
});
onBeforeUnmount(() => {
  request++;
  bookingRequest++;
  bookingController?.abort();
  clearTimeout(bookingTimer);
  clearTimeout(rolloverTimer);
  window.removeEventListener('focus', refresh);
  document.removeEventListener('visibilitychange', onVisibility);
});
</script>

<template>
  <section aria-label="Календарь">
    <h3>Календарь</h3>
    <p
      v-if="storageFailed"
      role="alert"
    >
      Не удалось сохранить попытку в этой вкладке. Подтверждение недоступно. Проверьте доступность хранилища и перезагрузите страницу.
    </p>
    <p>Московское время (Europe/Moscow), UTC+03:00</p>
    <section
      v-if="confirmed"
      aria-label="Запись подтверждена"
      role="status"
    >
      <h4>Запись подтверждена</h4>
      <p>{{ confirmed.meetingTypeName }}. {{ dateLabel(confirmed.startsAt.slice(0, 10)) }}, {{ formatMoscowInterval(confirmed) }}. {{ confirmed.durationMinutes }} минут. Московское время (Europe/Moscow).</p>
      <button
        class="button button-secondary"
        @click="chooseAnother"
      >
        Выбрать другое время
      </button>
    </section>
    <div
      v-else-if="unknown"
      role="alert"
    >
      <p>Результат записи неизвестен. Повторите подтверждение той же попытки.</p>
      <p v-if="attempt">
        {{ attempt.meetingTypeName }}, {{ dateLabel(attempt.startsAt.slice(0, 10)) }}, {{ formatMoscowTime(attempt.startsAt) }}. Московское время (Europe/Moscow).
      </p>
      <button
        class="button button-secondary"
        @click="confirmBooking"
      >
        Повторить подтверждение
      </button>
    </div>
    <p
      v-else-if="pending && !data"
      role="status"
    >
      Подтверждаем запись…
    </p>
    <p
      v-else-if="loading"
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
          :disabled="locked"
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
          :disabled="locked"
          @click="chooseSlot(slot)"
        >
          {{ formatMoscowInterval(slot) }}
        </button>
      </div>
      <p
        v-if="selectedSlot"
        role="status"
        aria-label="Итог записи"
      >
        Выбрано: {{ meetingTypeName }}, {{ durationMinutes }} минут, {{ dateLabel(selectedDate) }}, {{ formatMoscowInterval(selectedSlot) }}. Московское время (Europe/Moscow).
      </p>
      <p
        v-if="pending"
        role="status"
      >
        Подтверждаем запись…
      </p>
      <button
        class="button button-primary"
        :disabled="!selectedSlot || loading || pending || storageFailed"
        @click="confirmBooking"
      >
        Подтвердить запись
      </button>
    </template>
  </section>
</template>

<style scoped>
.dates, .slots { display: flex; flex-wrap: wrap; gap: .5rem; margin-block: 1rem; }
[aria-pressed="true"] { outline: 3px solid #315b41; outline-offset: 2px; }
</style>
