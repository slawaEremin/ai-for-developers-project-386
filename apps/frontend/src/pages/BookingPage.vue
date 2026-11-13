<script setup lang="ts">
import { restoreAttempt } from '../bookingAttempt';
import AvailabilityCalendar from '../components/AvailabilityCalendar.vue';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import HostProfile from '../components/HostProfile.vue';
import { getMeetingType, listMeetingTypes } from '../api/generated/sdk.gen';
import type { MeetingType } from '../api/generated/types.gen';

const heading = ref<HTMLElement | null>(null);
const bookingLocked = ref(false);
const items = ref<MeetingType[]>([]);
const loading = ref(true);
const catalogError = ref(false);
const selectionMessage = ref('');
const selectionLoading = ref(false);
const selectionFailed = ref(false);
let selectionRequest = 0;
const selected = ref<MeetingType | null>(null);
try {
  const saved = restoreAttempt();
  if (saved) {
    selected.value = { id: saved.meetingTypeId, name: saved.meetingTypeName, durationMinutes: saved.durationMinutes, description: '' };
    bookingLocked.value = true;
  }
} catch { /* Календарь покажет ошибку хранилища и заблокирует отправку. */ }

async function loadCatalog() {
  loading.value = true;
  catalogError.value = false;
  try {
    const result = await listMeetingTypes({ baseUrl: window.location.origin });
    if (!result.data) throw new Error('Catalog unavailable');
    items.value = result.data.items;
  } catch { catalogError.value = true; }
  finally { loading.value = false; }
}

async function selectFromAddress() {
  if (window.location.hash.split('?')[0] !== '#/booking') return;
  if (bookingLocked.value) {
    window.history.replaceState(null, '', `/#/booking?type=${encodeURIComponent(selected.value!.id)}`);
    return;
  }
  const id = new URLSearchParams(window.location.hash.split('?')[1]).get('type');
  const request = ++selectionRequest;
  selected.value = null;
  selectionMessage.value = '';
  selectionFailed.value = false;
  selectionLoading.value = !!id;
  if (!id) return;
  try {
    const result = await getMeetingType({ baseUrl: window.location.origin, path: { id } });
    if (request !== selectionRequest) return;
    if (result.data) selected.value = result.data;
    else if (result.response?.status === 404 || result.response?.status === 422) {
      selectionMessage.value = 'Тип встречи не найден. Выберите другой тип в каталоге.';
    } else throw new Error('Meeting type unavailable');
  } catch {
    if (request !== selectionRequest) return;
    selectionFailed.value = true;
    selectionMessage.value = 'Не удалось загрузить выбранный тип встречи.';
  } finally {
    if (request === selectionRequest) selectionLoading.value = false;
  }
}
watch(() => selected.value?.id, async () => {
  await nextTick();
  heading.value?.focus();
});

onMounted(() => {
  void loadCatalog();
  void selectFromAddress();
  window.addEventListener('hashchange', selectFromAddress);
});
onBeforeUnmount(() => {
  selectionRequest++;
  window.removeEventListener('hashchange', selectFromAddress);
});
</script>

<template>
  <section
    class="container booking-page"
    :class="{ 'catalog-page': !selected }"
  >
    <template v-if="!selected">
      <div class="panel catalog-intro">
        <HostProfile />
        <h1
          ref="heading"
          tabindex="-1"
        >
          Выберите тип встречи
        </h1>
        <p>Нажмите на карточку, чтобы открыть календарь и выбрать удобный слот.</p>
      </div>
      <section
        class="catalog"
        aria-label="Типы встреч"
      >
        <p
          v-if="loading"
          role="status"
        >
          Загрузка каталога…
        </p>
        <div
          v-else-if="catalogError"
          class="panel feedback"
          role="alert"
        >
          <p>Не удалось загрузить каталог.</p>
          <button
            class="button button-secondary"
            @click="loadCatalog"
          >
            Повторить загрузку каталога
          </button>
        </div>
        <p v-else-if="items.length === 0">
          Владелец пока не создал типы встреч.
        </p>
        <ul
          v-else
          class="meeting-types"
        >
          <li
            v-for="item in items"
            :key="item.id"
          >
            <a
              class="panel meeting-type"
              :href="`#/booking?type=${encodeURIComponent(item.id)}`"
              :aria-label="`Выбрать «${item.name}»`"
            >
              <div class="meeting-title"><h2>{{ item.name }}</h2><span class="duration">{{ item.durationMinutes }} мин</span></div>
              <p class="meeting-description">{{ item.description }}</p>
            </a>
          </li>
        </ul>
      </section>
      <p
        v-if="selectionLoading"
        class="selection-feedback"
        role="status"
      >
        Загрузка выбранного типа…
      </p>
      <div
        v-if="selectionMessage"
        class="panel feedback selection-feedback"
        role="alert"
      >
        <p>{{ selectionMessage }}</p>
        <button
          v-if="selectionFailed"
          class="button button-secondary"
          @click="selectFromAddress"
        >
          Повторить загрузку типа
        </button>
      </div>
      <a
        class="back-home"
        href="#/"
      >Вернуться на главную</a>
    </template>
    <section
      v-else
      aria-label="Выбранный тип встречи"
    >
      <h1
        ref="heading"
        class="booking-title"
        tabindex="-1"
      >
        {{ selected.name }}
      </h1>
      <AvailabilityCalendar
        :key="selected.id"
        :meeting-type-id="selected.id"
        :meeting-type-name="selected.name"
        :meeting-description="selected.description"
        :duration-minutes="selected.durationMinutes"
        @locked="bookingLocked = $event"
      />
    </section>
  </section>
</template>
