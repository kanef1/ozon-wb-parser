"""
Команда для создания/обновления расписания Celery Beat в БД.

Использование:
    python manage.py setup_beat
    python manage.py setup_beat --interval 15   # каждые 15 минут

При повторном запуске обновляет интервал, не создаёт дубли.
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Create or update periodic Celery Beat task in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=settings.PARSE_INTERVAL_MINUTES,
            help="Parse interval in minutes (default: PARSE_INTERVAL_MINUTES from settings)",
        )

    def handle(self, *args, **options):
        from django_celery_beat.models import PeriodicTask, IntervalSchedule

        interval_minutes: int = options["interval"]

        schedule, created = IntervalSchedule.objects.get_or_create(
            every=interval_minutes,
            period=IntervalSchedule.MINUTES,
        )

        task, task_created = PeriodicTask.objects.update_or_create(
            name="parse-all-active-products",
            defaults={
                "task": "apps.tracker.tasks.parse_all_active_products",
                "interval": schedule,
                "enabled": True,
            },
        )

        action = "Created" if task_created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} periodic task '{task.name}' — every {interval_minutes} minute(s)."
            )
        )
