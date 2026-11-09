<template>
  <section
    class="booking-placeholder container"
    aria-labelledby="booking-title"
  >
    <div
      class="placeholder-icon"
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 48 48"
        fill="none"
      >
        <path
          d="M15 9v8m18-8v8M10 23h28M14 13h20a4 4 0 0 1 4 4v19a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4V17a4 4 0 0 1 4-4Z"
          stroke="currentColor"
          stroke-width="2.2"
          stroke-linecap="round"
        />
        <path
          d="M20 31h8"
          stroke="currentColor"
          stroke-width="2.2"
          stroke-linecap="round"
        />
      </svg>
    </div>
    <p class="eyebrow">
      Готовимся к первому звонку
    </p>
    <h1
      id="booking-title"
      tabindex="-1"
    >
      Запись на звонок скоро появится
    </h1>
    <p class="placeholder-description">
      Здесь можно будет выбрать тип встречи и удобное время.
      Пока мы готовим календарь — онлайн-запись ещё недоступна.
    </p>
    <a
      class="button button-primary"
      href="#/"
    >
      <span aria-hidden="true">←</span> Вернуться на главную
    </a>
  </section>
</template>
