<template>
  <section
    class="hero container"
    aria-labelledby="home-title"
  >
    <div class="hero-copy">
      <p class="eyebrow">
        <span class="status-dot" /> Место для вашего следующего разговора
      </p>
      <h1
        id="home-title"
        tabindex="-1"
      >
        Выберите удобное время <span>для звонка.</span>
      </h1>
      <p class="hero-description">
        Хороший разговор начинается без долгой переписки.
        Выберите тип встречи и свободное время — без регистрации.
      </p>
      <a
        class="button button-primary"
        href="#/booking"
      >
        Записаться на звонок <span aria-hidden="true">→</span>
      </a>
      <p class="availability-note">
        Готовимся к запуску. Онлайн-запись пока недоступна.
      </p>
    </div>

    <figure
      class="booking-preview"
      aria-labelledby="preview-caption"
    >
      <figcaption
        id="preview-caption"
        class="preview-label"
      >
        Пример записи
      </figcaption>
      <div class="preview-card">
        <div class="preview-card-header">
          <span
            class="preview-icon"
            aria-hidden="true"
          >↗</span>
          <span class="preview-service">Календарь звонков</span>
        </div>
        <h2>Консультация</h2>
        <p class="preview-duration">
          <svg
            viewBox="0 0 20 20"
            fill="none"
            aria-hidden="true"
          >
            <circle
              cx="10"
              cy="10"
              r="7"
              stroke="currentColor"
              stroke-width="1.5"
            />
            <path
              d="M10 6v4l3 2"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            />
          </svg>
          30 минут · один на один
        </p>
        <div class="preview-divider" />
        <p class="preview-prompt">
          Время, которое подходит вам
        </p>
        <div
          class="preview-days"
          aria-hidden="true"
        >
          <div><span>ПН</span><strong>12</strong></div>
          <div><span>ВТ</span><strong>13</strong></div>
          <div class="preview-day-selected">
            <span>СР</span><strong>14</strong><i />
          </div>
          <div><span>ЧТ</span><strong>15</strong></div>
          <div><span>ПТ</span><strong>16</strong></div>
        </div>
        <div
          class="preview-times"
          aria-hidden="true"
        >
          <span>09:00</span><span class="preview-time-selected">10:00 <b>✓</b></span><span>11:30</span>
        </div>
        <div class="preview-summary">
          <span
            class="preview-check"
            aria-hidden="true"
          >✓</span>
          <div><strong>Время для разговора</strong><span>Среда, 14-е · 10:00–10:30</span></div>
        </div>
      </div>
      <p class="preview-footnote">
        Ваш день. Ваше удобное время.
      </p>
    </figure>
  </section>

  <section
    id="how-it-works"
    class="how-section"
    aria-labelledby="how-title"
  >
    <div class="container">
      <div class="section-heading">
        <div>
          <p class="eyebrow">
            Без лишних согласований
          </p>
          <h2 id="how-title">
            До звонка — три простых шага
          </h2>
        </div>
        <p>Так будет устроена запись<br class="desktop-break"> после запуска сервиса.</p>
      </div>
      <ol class="steps">
        <li>
          <span
            class="step-number"
            aria-hidden="true"
          >01</span>
          <h3>Выберите тип встречи</h3>
          <p>Посмотрите описание и длительность. Найдите встречу, которая подходит для вашего вопроса.</p>
        </li>
        <li>
          <span
            class="step-number"
            aria-hidden="true"
          >02</span>
          <h3>Найдите удобное время</h3>
          <p>Выберите день и свободный слот в календаре на ближайшие 14 дней.</p>
        </li>
        <li>
          <span
            class="step-number"
            aria-hidden="true"
          >03</span>
          <h3>Подтвердите запись</h3>
          <p>Проверьте дату и время звонка. После подтверждения этот интервал будет закреплён за вами.</p>
        </li>
      </ol>
      <div class="section-bottom">
        <p>Меньше времени на согласования — больше на сам разговор.</p>
        <a
          class="text-link"
          href="#/booking"
        >Перейти к записи <span aria-hidden="true">→</span></a>
      </div>
    </div>
  </section>
</template>
