<script setup lang="ts">
import { reactive, ref } from 'vue';
import { createMeetingType } from '../api/generated/sdk.gen';
import type { MeetingType } from '../api/generated/types.gen';

const form = reactive({ id: '', name: '', description: '', durationMinutes: '' });
const errors = ref<Record<string, string>>({});
const attempted = ref(false);
const pending = ref(false);
const message = ref('');
const unknownId = ref<string | null>(null);
const created = ref<MeetingType | null>(null);

function validate() {
  const next: Record<string, string> = {};
  if (!/^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$/.test(form.id)) {
    next.id = 'От 1 до 64 строчных латинских букв, цифр и дефисов; по краям буква или цифра.';
  }
  const name = form.name.trim();
  // eslint-disable-next-line no-control-regex -- Unicode line separators are rejected consistently with the API.
  if ([...name].length < 1 || [...name].length > 120 || /[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/.test(name)) {
    next.name = 'Введите однострочное название от 1 до 120 символов.';
  }
  const description = form.description.trim();
  if ([...description].length < 1 || [...description].length > 2000) {
    next.description = 'Введите описание от 1 до 2000 символов.';
  }
  const duration = Number(form.durationMinutes);
  if (!String(form.durationMinutes).trim() || !Number.isInteger(duration) || duration < 1 || duration > 540) {
    next.durationMinutes = 'Введите целое число от 1 до 540 минут.';
  }
  errors.value = next;
  return Object.keys(next).length === 0;
}

function edited(field: string) {
  if (attempted.value) {
    const previous = { ...errors.value };
    validate();
    // Сохраняем серверные ошибки других полей, пока их ввод не изменился.
    for (const [key, value] of Object.entries(previous)) {
      if (key !== field && !errors.value[key]) errors.value[key] = value;
    }
  }
}

async function submit() {
  if (pending.value) return;
  attempted.value = true;
  message.value = '';
  unknownId.value = null;
  created.value = null;
  if (!validate()) return;
  pending.value = true;
  const submittedId = form.id;
  try {
    const result = await createMeetingType({
      baseUrl: window.location.origin,
      body: { id: form.id, name: form.name.trim(), description: form.description.trim(), durationMinutes: Number(form.durationMinutes) },
    });
    if (result.data) {
      created.value = result.data;
      Object.assign(form, { id: '', name: '', description: '', durationMinutes: '' });
      errors.value = {};
      attempted.value = false;
    } else {
      errors.value = result.error?.fieldErrors ?? {};
      if (result.error?.code === 'MEETING_TYPE_ID_CONFLICT') errors.value.id = 'Этот id уже занят.';
      message.value = result.error?.code && result.response && result.response.status < 500
        ? result.error.message
        : 'Результат создания неизвестен. Проверьте каталог перед повторной отправкой.';
      if (!result.error?.code || !result.response || result.response.status >= 500) unknownId.value = submittedId;
    }
  } catch {
    unknownId.value = submittedId;
    message.value = 'Результат создания неизвестен. Проверьте каталог перед повторной отправкой.';
  } finally { pending.value = false; }
}
</script>

<template>
  <section class="container owner-page">
    <h1 tabindex="-1">
      Страница владельца
    </h1>
    <h2>Создать тип встречи</h2>
    <p>Задайте вариант звонка для гостей. Все поля обязательны.</p>
    <form
      novalidate
      @submit.prevent="submit"
    >
      <fieldset :disabled="pending">
        <div class="owner-field">
          <label for="meeting-id">Идентификатор (id)</label>
          <input
            id="meeting-id"
            v-model="form.id"
            required
            :aria-invalid="!!errors.id"
            :aria-describedby="errors.id ? 'error-id' : undefined"
            @input="edited('id')"
          >
          <span
            v-if="errors.id"
            id="error-id"
            class="field-error"
          >{{ errors.id }}</span>
        </div>
        <div class="owner-field">
          <label for="meeting-name">Название</label>
          <input
            id="meeting-name"
            v-model="form.name"
            required
            :aria-invalid="!!errors.name"
            :aria-describedby="errors.name ? 'error-name' : undefined"
            @input="edited('name')"
          >
          <span
            v-if="errors.name"
            id="error-name"
            class="field-error"
          >{{ errors.name }}</span>
        </div>
        <div class="owner-field">
          <label for="meeting-description">Описание</label>
          <textarea
            id="meeting-description"
            v-model="form.description"
            required
            rows="4"
            :aria-invalid="!!errors.description"
            :aria-describedby="errors.description ? 'error-description' : undefined"
            @input="edited('description')"
          />
          <span
            v-if="errors.description"
            id="error-description"
            class="field-error"
          >{{ errors.description }}</span>
        </div>
        <div class="owner-field">
          <label for="meeting-duration">Длительность в минутах</label>
          <input
            id="meeting-duration"
            v-model="form.durationMinutes"
            type="number"
            min="1"
            max="540"
            step="1"
            required
            :aria-invalid="!!errors.durationMinutes"
            :aria-describedby="errors.durationMinutes ? 'error-duration' : undefined"
            @input="edited('durationMinutes')"
          >
          <span
            v-if="errors.durationMinutes"
            id="error-duration"
            class="field-error"
          >{{ errors.durationMinutes }}</span>
        </div>
        <button
          class="button button-primary"
          type="submit"
        >
          {{ pending ? 'Сохранение…' : 'Создать тип встречи' }}
        </button>
      </fieldset>
    </form>
    <p
      v-if="message"
      role="alert"
    >
      {{ message }} <a
        v-if="unknownId"
        :href="`#/booking?type=${encodeURIComponent(unknownId)}`"
      >Проверить id «{{ unknownId }}» в каталоге</a>
    </p>
    <p
      v-if="created"
      role="status"
    >
      Тип встречи «{{ created.name }}» создан. <a :href="`#/booking?type=${encodeURIComponent(created.id)}`">Открыть гостевую страницу</a>
    </p>
  </section>
</template>

<style scoped>
.owner-page { padding-block: 4rem; max-width: 760px; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.owner-field { display: grid; gap: .5rem; margin-block: 1.3rem; }
label { font-weight: 600; }
input, textarea { width: 100%; box-sizing: border-box; padding: .8rem; border: 1px solid #949b95; border-radius: .5rem; font: inherit; color: inherit; background: #fff; }
[aria-invalid="true"] { border-color: #a92b28; }
.field-error, [role="alert"] { color: #a92b28; }
:disabled { opacity: .7; }
</style>
