"""Unit-тесты форматирования VK-уведомлений — без БД и без VK API."""
from decimal import Decimal

import pytest

from apps.notifications.message import build_notification_text, _fmt


@pytest.fixture(autouse=True)
def patch_site_domain(settings):
    settings.SITE_DOMAIN = "https://example.com"


class TestFmt:
    def test_integer_price(self):
        assert _fmt(Decimal("1234")) == "1 234"

    def test_kopecks(self):
        assert _fmt(Decimal("1234.50")) == "1 234.5"

    def test_large_price(self):
        assert _fmt(Decimal("99999")) == "99 999"

    def test_round_thousands(self):
        assert _fmt(Decimal("1000")) == "1 000"

    def test_small_price(self):
        assert _fmt(Decimal("99")) == "99"


class TestBuildNotificationText:
    def _build(self, new_price="900", old_price="1000", target_price=None):
        return build_notification_text(
            product_title="Наушники Sony",
            marketplace_display="Wildberries",
            article="12345678",
            product_url="https://www.wildberries.ru/catalog/12345678/detail.aspx",
            new_price=Decimal(new_price),
            old_price=Decimal(old_price) if old_price else None,
            target_price=Decimal(target_price) if target_price else None,
            dashboard_token="test-uuid-token",
        )

    def test_contains_title(self):
        assert "Наушники Sony" in self._build()

    def test_contains_article(self):
        assert "12345678" in self._build()

    def test_price_arrow_present(self):
        text = self._build(old_price="1000", new_price="900")
        assert "1 000" in text
        assert "900" in text
        assert "->" in text

    def test_drop_percentage(self):
        assert "-10%" in self._build(old_price="1000", new_price="900")

    def test_target_price_shown_when_below(self):
        text = self._build(new_price="800", old_price="1000", target_price="850")
        assert "850" in text
        assert "порог" in text.lower()

    def test_target_price_not_shown_when_above(self):
        text = self._build(new_price="900", old_price="1000", target_price="800")
        assert "порог" not in text.lower()

    def test_dashboard_url_present(self):
        assert "https://example.com/dashboard/test-uuid-token/" in self._build()

    def test_no_old_price(self):
        text = self._build(old_price=None)
        assert "->" not in text
        assert "900" in text
