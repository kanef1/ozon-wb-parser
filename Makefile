DC = docker compose

# ── Запуск / остановка ────────────────────────────────────────────────────────

.PHONY: up
up:
	$(DC) up

.PHONY: up-d
up-d:
	$(DC) up -d

.PHONY: build
build:
	$(DC) up --build

.PHONY: run
run:
	$(DC) up --build -d

.PHONY: down
down:
	$(DC) down

.PHONY: restart
restart:
	$(DC) restart

.PHONY: stop
stop:
	$(DC) stop

# ── Пересборка с нуля (удаляет volumes) ──────────────────────────────────────

.PHONY: reset
reset:
	$(DC) down -v --remove-orphans
	$(DC) up --build

# ── Логи ─────────────────────────────────────────────────────────────────────

.PHONY: logs
logs:
	$(DC) logs -f

.PHONY: logs-web
logs-web:
	$(DC) logs -f web

.PHONY: logs-worker
logs-worker:
	$(DC) logs -f celery_worker

.PHONY: logs-beat
logs-beat:
	$(DC) logs -f celery_beat

# ── Django manage.py ──────────────────────────────────────────────────────────

.PHONY: migrate
migrate:
	$(DC) exec web python manage.py migrate

.PHONY: migrations
migrations:
	$(DC) exec web python manage.py makemigrations

.PHONY: shell
shell:
	$(DC) exec web python manage.py shell

.PHONY: superuser
superuser:
	$(DC) exec web python manage.py createsuperuser

.PHONY: collectstatic
collectstatic:
	$(DC) exec web python manage.py collectstatic --noinput

# ── Тесты ─────────────────────────────────────────────────────────────────────

.PHONY: test
test:
	$(DC) exec web pytest

.PHONY: test-v
test-v:
	$(DC) exec web pytest -v

# ── Утилиты ───────────────────────────────────────────────────────────────────

.PHONY: ps
ps:
	$(DC) ps

.PHONY: bash
bash:
	$(DC) exec web bash

.PHONY: ngrok
ngrok:
	ngrok http 8000

.PHONY: help
help:
	@echo ""
	@echo "  Запуск"
	@echo "  make build       — собрать и запустить (foreground)"
	@echo "  make run         — собрать и запустить (background)"
	@echo "  make up          — запустить без пересборки"
	@echo "  make up-d        — запустить в фоне"
	@echo "  make down        — остановить и удалить контейнеры"
	@echo "  make stop        — остановить контейнеры"
	@echo "  make restart     — перезапустить контейнеры"
	@echo "  make reset       — пересобрать с нуля (удаляет данные БД)"
	@echo ""
	@echo "  Логи"
	@echo "  make logs        — все сервисы"
	@echo "  make logs-web    — только Django"
	@echo "  make logs-worker — только Celery worker"
	@echo "  make logs-beat   — только Celery beat"
	@echo ""
	@echo "  Django"
	@echo "  make migrate     — применить миграции"
	@echo "  make migrations  — создать миграции"
	@echo "  make shell       — Django shell"
	@echo "  make superuser   — создать суперпользователя"
	@echo ""
	@echo "  Тесты"
	@echo "  make test        — запустить тесты"
	@echo "  make test-v      — тесты с подробным выводом"
	@echo ""
	@echo "  Прочее"
	@echo "  make ps          — статус контейнеров"
	@echo "  make bash        — bash внутри web-контейнера"
	@echo "  make ngrok       — туннель на порт 8000"
	@echo ""
