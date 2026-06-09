#!/bin/sh
set -e

echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Setting up Celery Beat schedule..."
python manage.py setup_beat

echo "[entrypoint] Done. Starting: $*"
exec "$@"
