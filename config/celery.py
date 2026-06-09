import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ozon_wb_parser")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Автоматически обнаруживает tasks.py во всех INSTALLED_APPS
app.autodiscover_tasks()
