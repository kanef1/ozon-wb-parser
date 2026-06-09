from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models


class Marketplace(models.TextChoices):
    WB = "WB", "Wildberries"


def _build_product_url(marketplace: str, article: str) -> str:
    if marketplace == Marketplace.WB:
        return f"https://www.wildberries.ru/catalog/{article}/detail.aspx"
    return ""


class Product(models.Model):
    marketplace = models.CharField(max_length=10, choices=Marketplace.choices)
    article = models.CharField(
        max_length=64, help_text="Артикул / SKU товара на маркетплейсе"
    )
    product_url = models.URLField(max_length=512, blank=True)
    title = models.CharField(max_length=512, blank=True)
    current_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        constraints = [
            models.UniqueConstraint(
                fields=["marketplace", "article"], name="unique_marketplace_article"
            )
        ]

    def save(self, *args, **kwargs) -> None:
        # URL генерируется из артикула, не вводится вручную
        if not self.product_url:
            self.product_url = _build_product_url(self.marketplace, self.article)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"[{self.marketplace}] {self.title or self.article}"


class UserSubscription(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="subscriptions"
    )
    # None означает "уведомлять при любом снижении" (если notify_on_any_drop=True)
    target_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Порог цены. Уведомление придёт, когда цена опустится ниже него."
    )
    notify_on_any_drop = models.BooleanField(
        default=False,
        help_text="Уведомлять при любом снижении цены, не только при достижении порога"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_user_product_subscription"
            )
        ]

    def should_notify(self, new_price: Decimal, previous_price: Decimal | None) -> bool:
        """Определяет, нужно ли отправлять уведомление при новой цене."""
        if self.target_price is not None and new_price < self.target_price:
            return True
        if self.notify_on_any_drop and previous_price is not None:
            return new_price < previous_price
        return False

    def __str__(self) -> str:
        return f"{self.user.username} → {self.product}"


class PriceHistory(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_history"
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    parsed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Запись истории цен"
        verbose_name_plural = "История цен"
        indexes = [
            # Составной индекс для быстрых выборок по графику
            models.Index(fields=["product", "parsed_at"], name="idx_price_history_product_time")
        ]
        ordering = ["-parsed_at"]

    def __str__(self) -> str:
        return f"{self.product} — {self.price} руб. ({self.parsed_at:%Y-%m-%d %H:%M})"


class NotificationLog(models.Model):
    subscription = models.ForeignKey(
        UserSubscription, on_delete=models.CASCADE, related_name="notification_logs"
    )
    price_history = models.ForeignKey(
        PriceHistory, on_delete=models.SET_NULL, null=True, related_name="notification_logs"
    )
    # Цена ДО снижения — нужна для текста уведомления
    old_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    # Краткий текст для отладки (не полное сообщение ВКонтакте)
    message_preview = models.CharField(max_length=256, blank=True)

    class Meta:
        verbose_name = "Лог уведомления"
        verbose_name_plural = "Лог уведомлений"
        indexes = [
            models.Index(
                fields=["subscription", "sent_at"], name="idx_notification_log_sub_time"
            )
        ]

    def __str__(self) -> str:
        return f"Уведомление [{self.subscription}] в {self.sent_at:%Y-%m-%d %H:%M}"
