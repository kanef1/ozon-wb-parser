import logging

from celery import shared_task

from .vk import VKNotifier, VKPermissionError
from .message import build_notification_text

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, ignore_result=True)
def send_vk_notification(self, notification_log_id: int) -> None:
    """Отправить VK-уведомление по записи NotificationLog.

    Ретраит при временных ошибках API (сеть, rate-limit).
    Не ретраит при ошибках прав (пользователь закрыл сообщения) — 
    в этом случае просто логируем предупреждение.
    """
    from apps.tracker.models import NotificationLog

    try:
        log = (
            NotificationLog.objects
            .select_related(
                "subscription__user__profile",
                "subscription__product",
                "price_history",
            )
            .get(id=notification_log_id)
        )
    except NotificationLog.DoesNotExist:
        logger.warning("send_vk_notification: log_id=%d not found", notification_log_id)
        return

    sub = log.subscription
    profile = sub.user.profile

    if not profile.vk_user_id:
        logger.warning(
            "send_vk_notification: user '%s' has no vk_user_id, skipping log_id=%d",
            sub.user.username, notification_log_id,
        )
        return

    product = sub.product
    new_price = log.price_history.price if log.price_history else None

    if new_price is None:
        logger.warning(
            "send_vk_notification: no price_history for log_id=%d", notification_log_id
        )
        return

    text = build_notification_text(
        product_title=product.title or product.article,
        marketplace_display=product.get_marketplace_display(),
        article=product.article,
        product_url=product.product_url,
        new_price=new_price,
        old_price=log.old_price,
        target_price=sub.target_price,
        dashboard_token=str(profile.dashboard_token),
    )

    try:
        notifier = VKNotifier()
        # Используем log.id как random_id — гарантирует идемпотентность при ретрае
        notifier.send_message(
            vk_user_id=profile.vk_user_id,
            text=text,
            random_id=notification_log_id,
        )
    except VKPermissionError:
        # Пользователь закрыл сообщения — ретрай бессмысленен
        return
    except Exception as exc:
        logger.error(
            "send_vk_notification: API error log_id=%d: %s", notification_log_id, exc
        )
        raise self.retry(exc=exc)
