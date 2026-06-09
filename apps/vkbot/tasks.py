from celery import shared_task


@shared_task(ignore_result=True)
def handle_vk_event(event: dict) -> None:
    from .handlers import handle_event
    handle_event(event)
