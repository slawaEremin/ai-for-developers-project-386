<script setup lang="ts">
import { clearAttempt, restoreAttempt, saveAttempt, type BookingAttempt } from '../bookingAttempt';
import { formatMoscowDate, formatMoscowInterval, formatMoscowTime } from '../moscowTime';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import HostProfile from './HostProfile.vue';
import { createBooking, getAvailability } from '../api/generated/sdk.gen';
import type { Availability, AvailableSlot, Booking } from '../api/generated/types.gen';

const props = defineProps<{ meetingTypeId: string; meetingTypeName: string; durationMinutes: number; meetingDescription: string }>();
const emit = defineEmits<{ locked: [value: boolean] }>();
const pending = ref(false);
const reviewing = ref(false);
const panelHeading = ref<HTMLElement | null>(null);
const displayedMonth = ref('');
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
function chooseSlot(slot: AvailableSlot) { if (locked.value) return; reviewing.value = false; selectedSlot.value = slot; notice.value = ''; }
function chooseDate(date: string) { if (locked.value) return; reviewing.value = false; selectedDate.value = date; selectedSlot.value = null; notice.value = ''; }

const monthFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', month: 'long', year: 'numeric' });
const monthLabel = computed(() => displayedMonth.value ? monthFormat.format(new Date(`${displayedMonth.value}-01T00:00:00Z`)) : '');
const months = computed(() => [...new Set(data.value?.days.map((item) => item.date.slice(0, 7)) ?? [])]);
const monthIndex = computed(() => months.value.indexOf(displayedMonth.value));
const cells = computed(() => {
  if (!displayedMonth.value) return [];
  const first = new Date(`${displayedMonth.value}-01T00:00:00Z`);
  const mondayOffset = (first.getUTCDay() + 6) % 7;
  return Array.from({ length: 42 }, (_, index) => {
    const value = new Date(first);
    value.setUTCDate(1 - mondayOffset + index);
    const date = value.toISOString().slice(0, 10);
    const available = data.value?.days.find((item) => item.date === date);
    return { date, number: value.getUTCDate(), available, outsideMonth: date.slice(0, 7) !== displayedMonth.value };
  });
});
const summarySlot = computed(() => confirmed.value ?? (attempt && locked.value ? {
  startsAt: attempt.startsAt,
  endsAt: new Date(Date.parse(attempt.startsAt) + attempt.durationMinutes * 60000).toISOString(),
} : selectedSlot.value));
function changeMonth(offset: number) {
  if (locked.value || loading.value || failed.value) return;
  const month = months.value[monthIndex.value + offset];
  if (month) displayedMonth.value = month;
}
function continueBooking() {
  if (!selectedSlot.value || loading.value || failed.value || locked.value) return;
  reviewing.value = true;
}
watch(selectedDate, (date) => { if (date) displayedMonth.value = date.slice(0, 7); });
watch([reviewing, unknown, confirmed], async () => {
  await nextTick();
  panelHeading.value?.focus();
});

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
    if (!displayedMonth.value || !months.value.includes(displayedMonth.value)) displayedMonth.value = selectedDate.value.slice(0, 7);
    if (selectedSlot.value && !day.value?.slots.some((slot) => slot.startsAt === selectedSlot.value?.startsAt && slot.endsAt === selectedSlot.value?.endsAt)) {
      selectedSlot.value = null;
      reviewing.value = false;
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
  if (pending.value || storageFailed.value || (!attempt && (!reviewing.value || !selectedSlot.value || loading.value || failed.value))) return;
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
      reviewing.value = false;
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
  reviewing.value = false;
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
  <section
    class="booking-layout"
    aria-label="Календарь"
  >
    <aside
      class="panel booking-details"
      aria-label="Сведения о встрече"
    >
      <HostProfile />
      <div class="meeting-title">
        <h2>{{ meetingTypeName }}</h2><span class="duration">{{ durationMinutes }} мин</span>
      </div>
      <p class="meeting-description">
        {{ meetingDescription }}
      </p>
      <dl class="selection-summary">
        <div><dt>Выбранная дата</dt><dd>{{ selectedDate ? dateLabel(selectedDate) : 'Дата не выбрана' }}</dd></div>
        <div><dt>Выбранное время</dt><dd>{{ summarySlot ? formatMoscowInterval(summarySlot) : 'Время не выбрано' }}</dd></div>
      </dl>
      <p class="timezone">
        Московское время<br>Europe/Moscow, UTC+03:00
      </p>
    </aside>

    <section
      v-if="!unknown && !confirmed"
      class="panel calendar-panel"
      aria-label="Выбор даты"
    >
      <div class="calendar-heading">
        <h2>Календарь</h2>
        <div class="month-navigation">
          <button
            class="icon-button"
            aria-label="Предыдущий месяц"
            :disabled="locked || loading || failed || monthIndex <= 0"
            @click="changeMonth(-1)"
          >
            ←
          </button>
          <button
            class="icon-button"
            aria-label="Следующий месяц"
            :disabled="locked || loading || failed || monthIndex >= months.length - 1"
            @click="changeMonth(1)"
          >
            →
          </button>
        </div>
      </div>
      <p
        v-if="loading"
        role="status"
      >
        Загрузка доступности…
      </p>
      <div
        v-else-if="failed"
        class="feedback"
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
          class="calendar-month"
          aria-live="polite"
        >
          {{ monthLabel }}
        </p>
        <div
          class="calendar-weekdays"
          aria-hidden="true"
        >
          <span
            v-for="weekday in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']"
            :key="weekday"
          >{{ weekday }}</span>
        </div>
        <div
          class="calendar-grid"
          aria-label="Даты окна записи"
        >
          <button
            v-for="cell in cells"
            :key="cell.date"
            class="calendar-day"
            :class="{ 'outside-month': cell.outsideMonth }"
            :data-calendar-date="cell.date"
            :data-date="cell.available ? cell.date : undefined"
            :aria-label="`${dateLabel(cell.date)}${cell.available ? `, свободных слотов: ${cell.available.slots.length}` : ', вне окна записи'}`"
            :aria-pressed="selectedDate === cell.date"
            :disabled="!cell.available || locked"
            @click="chooseDate(cell.date)"
          >
            <span>{{ cell.number }}</span><small v-if="cell.available">{{ cell.available.slots.length }} св.</small>
          </button>
        </div>
      </template>
    </section>

    <section
      class="panel slots-panel"
      :class="{ 'booking-outcome': unknown || confirmed }"
      aria-label="Выбор времени и подтверждение"
    >
      <h2
        ref="panelHeading"
        tabindex="-1"
      >
        {{ confirmed ? 'Запись подтверждена' : unknown || reviewing || pending ? 'Подтверждение записи' : 'Свободное время' }}
      </h2>
      <p
        v-if="storageFailed"
        class="error-message"
        role="alert"
      >
        Не удалось сохранить попытку в этой вкладке. Подтверждение недоступно. Проверьте доступность хранилища и перезагрузите страницу.
      </p>
      <section
        v-if="confirmed"
        class="feedback"
        aria-label="Запись подтверждена"
        role="status"
      >
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
        class="feedback"
        role="alert"
      >
        <p>Результат записи неизвестен. Повторите подтверждение той же попытки.</p>
        <p v-if="attempt">
          {{ attempt.meetingTypeName }}, {{ dateLabel(attempt.startsAt.slice(0, 10)) }}, {{ summarySlot ? formatMoscowInterval(summarySlot) : formatMoscowTime(attempt.startsAt) }}. Московское время (Europe/Moscow).
        </p>
        <button
          class="button button-primary"
          :disabled="storageFailed"
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
      <template v-else>
        <p
          v-if="notice"
          class="booking-notice"
          role="status"
        >
          {{ notice }}
        </p>
        <p v-if="data && !loading && !failed && data.days.every((item) => item.slots.length === 0)">
          Во всём окне нет свободного времени.
        </p>
        <template v-if="reviewing && selectedSlot && !loading && !failed">
          <p
            class="review-summary"
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
          <div class="booking-actions review-actions">
            <button
              class="button button-secondary"
              :disabled="locked"
              @click="reviewing = false"
            >
              Назад
            </button>
            <button
              class="button button-primary"
              :disabled="pending || storageFailed"
              @click="confirmBooking"
            >
              Подтвердить запись
            </button>
          </div>
        </template>
        <template v-else>
          <p
            v-if="loading"
            class="muted"
          >
            Загружаем свободное время…
          </p>
          <p
            v-else-if="failed"
            class="muted"
          >
            Свободное время появится после загрузки календаря.
          </p>
          <div
            v-else-if="data"
            class="slot-list"
          >
            <p v-if="day?.slots.length === 0">
              В этот день нет свободного времени.
            </p>
            <button
              v-for="slot in day?.slots"
              :key="slot.startsAt"
              class="slot-button"
              :data-slot="slot.startsAt"
              :aria-label="formatMoscowInterval(slot)"
              :aria-pressed="selectedSlot?.startsAt === slot.startsAt"
              :disabled="locked"
              @click="chooseSlot(slot)"
            >
              <span>{{ formatMoscowInterval(slot) }}</span><strong>{{ selectedSlot?.startsAt === slot.startsAt ? 'Выбрано' : 'Свободно' }}</strong>
            </button>
          </div>
          <div class="booking-actions">
            <a
              v-if="!locked"
              class="button button-secondary"
              href="#/booking"
            >Назад</a>
            <button
              class="button button-primary"
              :disabled="!selectedSlot || loading || failed || locked"
              @click="continueBooking"
            >
              Продолжить
            </button>
          </div>
        </template>
      </template>
    </section>
  </section>
</template>
