# Инструкции для агента

Учебный монорепозиторий сервиса записи на звонки. Требования к календарю описаны в [README.md](README.md); текущая реализация содержит каркас FastAPI и Vue, контракт TypeSpec и Docker-сборку.

## Навигация

Перед изменением соответствующей части проекта прочитай её документацию.

| Область | Документация |
| --- | --- |
| Сценарии и ограничения календаря | [README.md](README.md) |
| FastAPI, запуск API и pytest | [apps/backend/README.md](apps/backend/README.md) |
| Vue, Vite, TypeScript и Vitest | [apps/frontend/README.md](apps/frontend/README.md) |
| Контракт API и генерация | [specs/README.md](specs/README.md) |
| Docker и раздача фронтенда через FastAPI | [apps/infra/README.md](apps/infra/README.md) |

## Окружение и команды

Нужны Node.js 24 с npm и uv. Python 3.13 при необходимости устанавливается uv. Команды Make запускаются из корня или через `make -C /путь/к/репозиторию`.

- `make setup` устанавливает зависимости из lock-файлов и генерирует OpenAPI, модели и SDK.
- После изменений кода запускай `make lint` и `make check`. Линтинг включает проверку типов фронтенда и актуальности генерации; тесты выполняются без watch-режима.
- После изменений фронтенда проверяй сборку командой `npm run build`.
- После изменений контейнеризации проверяй сборку и запуск по инструкции в `apps/infra/README.md`. В контейнере должны быть доступны страница, её ресурсы и API.

JavaScript-зависимости управляются npm workspaces с одним корневым `package-lock.json`. Python-зависимости задаются в `apps/backend/pyproject.toml` и закрепляются в `apps/backend/uv.lock`. При изменении зависимостей обновляй соответствующий lock-файл.

## Контракт и сгенерированный код

При изменении API сначала обновляй `specs/main.tsp`, затем запускай `make generate`. Маршруты FastAPI реализуются вручную с использованием сгенерированных Pydantic-моделей. Для обращений фронтенда к API используй сгенерированный SDK.

Результаты генерации хранятся в Git вместе с изменениями контракта. Следующие файлы обновляй генератором, а не вручную.

- `specs/generated/openapi.json`
- `apps/backend/app/generated/models.py`
- `apps/frontend/src/api/generated/`

Процесс генерации и проверка расхождений реализованы в `scripts/generate.mjs`. Если `make lint` сообщает об устаревших результатах, выполни `make generate` и проверь полученный diff.

## Документация и учебные проверки

Документацию пиши по-русски. В корневом README различай требования к будущему календарю и уже реализованные возможности.

Файл `.github/workflows/hexlet-check.yml` управляется Hexlet. Не редактируй и не удаляй его; назначение описано в [.github/workflows/README.md](.github/workflows/README.md).
