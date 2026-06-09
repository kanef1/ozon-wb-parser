from decimal import Decimal

from django.conf import settings


def build_notification_text(
    product_title: str,
    marketplace_display: str,
    article: str,
    product_url: str,
    new_price: Decimal,
    old_price: Decimal | None,
    target_price: Decimal | None,
    dashboard_token: str,
) -> str:
    """Сформировать текст VK-уведомления о снижении цены.

    Принимает плоские аргументы (не ORM-объекты) — легко тестируется без БД.
    """
    dashboard_url = f"{settings.SITE_DOMAIN}/dashboard/{dashboard_token}/"

    lines: list[str] = [
        "Снижение цены!",
        "",
        f"Товар: {product_title}",
        f"Артикул: {article}",
        f"Маркетплейс: {marketplace_display}",
        "",
    ]

    if old_price is not None:
        lines.append(f"Цена: {_fmt(old_price)} руб. -> {_fmt(new_price)} руб.")
        drop_pct = int((old_price - new_price) / old_price * 100)
        lines.append(f"Снижение: -{drop_pct}%")
    else:
        lines.append(f"Цена: {_fmt(new_price)} руб.")

    if target_price is not None and new_price < target_price:
        lines.append(f"(ниже вашего порога {_fmt(target_price)} руб.)")

    lines += [
        "",
        f"Карточка: {product_url}",
        f"Ваши графики: {dashboard_url}",
    ]

    return "\n".join(lines)


def _fmt(value: Decimal) -> str:
    """Форматировать цену: убрать лишние нули, добавить пробел-разделитель тысяч."""
    # :.2f даёт фиксированную нотацию (без 1E+3 для больших чисел)
    s = f"{value:.2f}".rstrip("0").rstrip(".")
    integer_part, _, decimal_part = s.partition(".")

    # Пробел-разделитель тысяч без зависимости от локали
    chunks: list[str] = []
    for i, ch in enumerate(reversed(integer_part)):
        if i and i % 3 == 0:
            chunks.append(" ")
        chunks.append(ch)
    formatted_int = "".join(reversed(chunks))

    return f"{formatted_int}.{decimal_part}" if decimal_part else formatted_int
