# Фронтенд

Vue 3, TypeScript в строгом режиме и Vite. Нужны Node.js 24.22.2 из корневого `.nvmrc` и npm 10.8.2 из `packageManager` корневого `package.json`. Зависимости входят в корневой npm workspace и закреплены общим `package-lock.json`.

Из корня репозитория выполните `make setup`, затем запустите Vite.

```sh
npm run dev --workspace apps/frontend
```

Корневая страница доступна по адресу `http://127.0.0.1:5173`. Она пустая, не выполняет запросы к API и не требует запущенного бэкенда.

```sh
npm run lint --workspace apps/frontend
npm run test --workspace apps/frontend
npm run build
```

Один дымовой тест Vitest монтирует корневой компонент в DOM через Vue Test Utils и проверяет отсутствие видимого содержимого. Линтинг включает ESLint и проверку типов `vue-tsc`. Сборка сохраняется в `apps/frontend/dist`.

Из корня репозитория доступны `make test` для тестов обоих приложений и `make build` для сборки фронтенда. Единая команда `make check` последовательно запускает линтинг, проверку генерации, тесты и сборку; она же выполняется в GitHub Actions на каждый push.

SDK в `src/api/generated` генерируется командой `make generate` и пока не используется страницей. Генерация SDK и установка зависимостей выполняются из корня репозитория.
