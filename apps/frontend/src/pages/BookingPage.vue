<script setup lang="ts">
import AvailabilityCalendar from '../components/AvailabilityCalendar.vue';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { getMeetingType, listMeetingTypes } from '../api/generated/sdk.gen';
import type { MeetingType } from '../api/generated/types.gen';

const items = ref<MeetingType[]>([]);
const loading = ref(true);
const catalogError = ref(false);
const selectionMessage = ref('');
const selectionLoading = ref(false);
const selectionFailed = ref(false);
let selectionRequest = 0;
const selected = ref<MeetingType | null>(null);

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
  <section class="container booking-page">
    <p class="eyebrow">
      Выберите формат разговора
    </p>
    <h1 tabindex="-1">
      Запись на звонок
    </h1>
    <p>Выберите тип встречи и свободное время для звонка.</p>
    <section aria-label="Типы встреч">
      <h2>Типы встреч</h2>
      <p
        v-if="loading"
        role="status"
      >
        Загрузка каталога…
      </p>
      <div
        v-else-if="catalogError"
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
          class="meeting-type"
        >
          <h3>{{ item.name }}</h3>
          <p class="meeting-description">
            {{ item.description }}
          </p>
          <p>{{ item.durationMinutes }} минут</p>
          <a
            class="button button-secondary"
            :href="`#/booking?type=${encodeURIComponent(item.id)}`"
          >Выбрать «{{ item.name }}»</a>
        </li>
      </ul>
    </section>
    <p
      v-if="selectionLoading"
      role="status"
    >
      Загрузка выбранного типа…
    </p>
    <div
      v-if="selectionMessage"
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
    <section
      v-if="selected"
      aria-label="Выбранный тип встречи"
      class="selected-type"
    >
      <h2>{{ selected.name }}</h2>
      <p class="meeting-description">
        {{ selected.description }}
      </p>
      <p>{{ selected.durationMinutes }} минут</p>
      <AvailabilityCalendar
        :key="selected.id"
        :meeting-type-id="selected.id"
      />
    </section>
    <a href="#/">Вернуться на главную</a>
  </section>
</template>

<style scoped>
.booking-page { padding-block: 4rem; }
.meeting-types { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 1rem; padding: 0; list-style: none; }
.meeting-type, .selected-type { border: 1px solid #c5cec5; border-radius: 1rem; padding: 1.5rem; }
.meeting-description { white-space: pre-wrap; overflow-wrap: anywhere; }
.selected-type { margin-block: 2rem; background: #eef3ed; }
</style>
