import logging
from decimal import Decimal

from celery import shared_task
from django.db import transaction

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Периодическая точка входа
# --------------------------------------------------------------------------- #

@shared_task(ignore_result=True)
def parse_all_active_products() -> None:
    """Ставит задачи парсинга для всех товаров с хотя бы одной активной подпиской."""
    from apps.tracker.models import UserSubscription

    product_ids = list(
        UserSubscription.objects.filter(is_active=True)
        .values_list("product_id", flat=True)
        .distinct()
    )

    for product_id in product_ids:
        parse_single_product.delay(product_id)

    logger.info("Queued %d products for parsing", len(product_ids))


# --------------------------------------------------------------------------- #
# Парсинг одного товара
# --------------------------------------------------------------------------- #

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def parse_single_product(self, product_id: int) -> dict:
    """Спарсить цену одного товара, записать в историю, обновить current_price.

    При сетевой ошибке делает до 3 попыток с интервалом 60 сек.
    Передаёт строковые представления Decimal, т.к. JSON-сериализатор
    Celery не умеет в Decimal напрямую.
    """
    from apps.tracker.models import Product, PriceHistory
    from apps.parsers.registry import get_parser

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        logger.warning("parse_single_product: product %d not found", product_id)
        return {"status": "not_found", "product_id": product_id}

    # ---------- парсинг ----------
    try:
        parser = get_parser(product.marketplace)
        info = parser.fetch_product_info(product.article)
    except Exception as exc:
        logger.error(
            "parse_single_product: parser error product_id=%d: %s", product_id, exc
        )
        raise self.retry(exc=exc)

    if info.price is None:
        logger.warning(
            "parse_single_product: no price for product_id=%d (%s %s)",
            product_id, product.marketplace, product.article,
        )
        return {"status": "no_price", "product_id": product_id}

    new_price: Decimal = info.price
    previous_price: Decimal | None = product.current_price

    # ---------- атомарная запись ----------
    with transaction.atomic():
        history = PriceHistory.objects.create(product=product, price=new_price)

        update_fields = ["current_price"]
        product.current_price = new_price
        # Запишем название, если его ещё нет
        if info.title and not product.title:
            product.title = info.title
            update_fields.append("title")
        product.save(update_fields=update_fields)

    logger.info(
        "parse_single_product: product_id=%d %s → %s",
        product_id, previous_price, new_price,
    )

    # ---------- проверка подписок ----------
    # Передаём через Celery как строки — Decimal не JSON-сериализуем
    check_subscriptions_and_notify.delay(
        product_id,
        str(new_price),
        str(previous_price) if previous_price is not None else None,
    )

    return {
        "status": "ok",
        "product_id": product_id,
        "price": str(new_price),
        "previous_price": str(previous_price) if previous_price is not None else None,
        "history_id": history.id,
    }


# --------------------------------------------------------------------------- #
# Проверка порогов и постановка уведомлений
# --------------------------------------------------------------------------- #

@shared_task(ignore_result=True)
def check_subscriptions_and_notify(
    product_id: int,
    new_price_str: str,
    previous_price_str: str | None,
) -> None:
    """Проверить все подписки на товар и поставить задачи уведомлений.

    Защита от дублей: не создаёт NotificationLog, если для этой подписки
    уже есть запись с той же PriceHistory.
    """
    from apps.tracker.models import UserSubscription, PriceHistory, NotificationLog
    from apps.notifications.tasks import send_vk_notification

    new_price = Decimal(new_price_str)
    previous_price = Decimal(previous_price_str) if previous_price_str else None

    # Последняя запись истории — именно ту цену мы только что записали
    latest_history = (
        PriceHistory.objects.filter(product_id=product_id).first()
    )

    subscriptions = (
        UserSubscription.objects
        .filter(product_id=product_id, is_active=True)
        .select_related("user", "user__profile", "product")
    )

    for sub in subscriptions:
        if not sub.should_notify(new_price, previous_price):
            continue

        # Дедупликация: одна запись лога на одну PriceHistory-запись
        if latest_history and NotificationLog.objects.filter(
            subscription=sub,
            price_history=latest_history,
        ).exists():
            logger.debug(
                "Skipping duplicate notification sub_id=%d history_id=%d",
                sub.id, latest_history.id,
            )
            continue

        log = NotificationLog.objects.create(
            subscription=sub,
            price_history=latest_history,
            old_price=previous_price,
            message_preview=(
                f"{sub.product.marketplace} {sub.product.article}: "
                f"{previous_price} → {new_price}"
            ),
        )
        send_vk_notification.delay(log.id)
        logger.info(
            "Queued VK notification: sub_id=%d log_id=%d price %s→%s",
            sub.id, log.id, previous_price, new_price,
        )
