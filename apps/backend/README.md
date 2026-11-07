# Бэкенд

FastAPI и Uvicorn работают на Python 3.13.18 из `.python-version`. Зависимости и инструменты разработки закреплены в `uv.lock`, окружением управляет uv 0.13.7 из `tool.uv.required-version` в `pyproject.toml`.

Из корня репозитория установите зависимости командой `make setup`, затем запустите сервер.

```sh
cd apps/backend
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` возвращает `{"status":"ok"}`. Swagger UI доступен по адресу `http://127.0.0.1:8000/docs`.

```sh
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Один дымовой тест проверяет запуск приложения и ответ `/health`. Модель ответа в `app/generated/models.py` генерируется из TypeSpec через OpenAPI. Обновляйте её корневой командой `make generate`.

Из корня репозитория `make test` запускает тесты бэкенда и фронтенда, а `make check` последовательно проверяет линтинг, актуальность генерации, тесты и сборку фронтенда. Та же команда используется в GitHub Actions на каждый push.

Сервер отдаёт собранный фронтенд из каталога `dist` рядом с `pyproject.toml`, если он существует. Другой путь можно задать переменной `STATIC_DIR`. Без собранного фронтенда API работает самостоятельно.
