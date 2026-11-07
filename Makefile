SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: help setup generate lint test build check

help:
	@echo 'make setup     Установить зависимости и сгенерировать контракт'
	@echo 'make generate  Обновить OpenAPI, модели Python и SDK TypeScript'
	@echo 'make lint      Проверить Python, Vue, TypeScript и контракт'
	@echo 'make test      Запустить тесты бэкенда и фронтенда'
	@echo 'make build     Собрать фронтенд'
	@echo 'make check     Последовательно выполнить lint, test и build'

setup:
	cd "$(ROOT)" && npm ci
	cd "$(ROOT)/apps/backend" && uv sync --locked
	$(MAKE) -C "$(ROOT)" generate

generate:
	cd "$(ROOT)" && npm run generate

lint:
	cd "$(ROOT)/apps/backend" && uv run --locked ruff check .
	cd "$(ROOT)/apps/backend" && uv run --locked ruff format --check .
	cd "$(ROOT)" && npm run lint

test:
	cd "$(ROOT)/apps/backend" && uv run --locked pytest
	cd "$(ROOT)" && npm run test --workspace apps/frontend

build:
	cd "$(ROOT)" && npm run build

check:
	$(MAKE) -C "$(ROOT)" lint
	$(MAKE) -C "$(ROOT)" test
	$(MAKE) -C "$(ROOT)" build
