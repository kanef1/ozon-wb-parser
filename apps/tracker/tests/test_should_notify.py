"""Unit-тесты метода UserSubscription.should_notify — без БД."""
from decimal import Decimal

import pytest

from apps.tracker.models import UserSubscription


def _make_sub(**kwargs) -> UserSubscription:
    """Создаёт UserSubscription без сохранения в БД."""
    sub = UserSubscription.__new__(UserSubscription)
    sub.target_price = kwargs.get("target_price")
    sub.notify_on_any_drop = kwargs.get("notify_on_any_drop", False)
    sub.is_active = True
    return sub


class TestShouldNotify:
    def test_price_below_target(self):
        sub = _make_sub(target_price=Decimal("1000"))
        assert sub.should_notify(Decimal("900"), Decimal("1100")) is True

    def test_price_above_target(self):
        sub = _make_sub(target_price=Decimal("1000"))
        assert sub.should_notify(Decimal("1100"), Decimal("1200")) is False

    def test_price_equal_target_not_triggered(self):
        # Уведомляем только при строго ниже порога
        sub = _make_sub(target_price=Decimal("1000"))
        assert sub.should_notify(Decimal("1000"), Decimal("1200")) is False

    def test_notify_on_any_drop_triggers(self):
        sub = _make_sub(notify_on_any_drop=True)
        assert sub.should_notify(Decimal("900"), Decimal("1000")) is True

    def test_notify_on_any_drop_no_increase(self):
        sub = _make_sub(notify_on_any_drop=True)
        assert sub.should_notify(Decimal("1100"), Decimal("1000")) is False

    def test_notify_on_any_drop_no_previous_price(self):
        # Первый парсинг — previous_price=None, не уведомляем
        sub = _make_sub(notify_on_any_drop=True)
        assert sub.should_notify(Decimal("900"), None) is False

    def test_target_price_trumps_any_drop(self):
        # Оба флага: target_price срабатывает независимо от any_drop
        sub = _make_sub(target_price=Decimal("500"), notify_on_any_drop=True)
        # Цена снизилась, но выше порога — only any_drop triggers
        assert sub.should_notify(Decimal("800"), Decimal("900")) is True  # any_drop
        assert sub.should_notify(Decimal("400"), Decimal("900")) is True  # target
