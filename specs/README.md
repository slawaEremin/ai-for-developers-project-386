# Контракт API

Источник контракта находится в `main.tsp`. Он описывает `GET /health` с ответом HTTP 200 и JSON `{"status":"ok"}`.

Из корня репозитория выполните `make generate`, чтобы получить OpenAPI JSON в `specs/generated/openapi.json`, модели Pydantic в `apps/backend/app/generated/models.py` и TypeScript SDK в `apps/frontend/src/api/generated`.

Генераторы устанавливаются через корневой npm workspace и окружение uv бэкенда. TypeSpec компилируется в OpenAPI 3.1, затем `datamodel-code-generator` создаёт модели Pydantic v2, а `@hey-api/openapi-ts` создаёт SDK на Fetch API. Маршруты FastAPI реализуются вручную с использованием сгенерированных моделей.

Сгенерированные файлы хранятся в Git и не редактируются вручную. `make lint` повторяет генерацию во временном каталоге и проверяет её соответствие сохранённым файлам.
