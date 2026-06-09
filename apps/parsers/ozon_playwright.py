"""
Fallback-парсер Ozon на базе Playwright.

Используется только если composer-api не вернул цену (например, Ozon поменял
структуру widgetStates или включил защиту от ботов).

Установка:
    pip install playwright
    playwright install chromium

Подключение в коде:
    from apps.parsers.ozon_playwright import OzonPlaywrightParser
    with OzonPlaywrightParser() as parser:
        info = parser.fetch_product_info("1234567890")
"""

from decimal import Decimal

from .base import BaseParser, ProductInfo
from .ozon import _parse_price_str

try:
    from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeoutError
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


_PRICE_SELECTOR = "[data-widget='webPrice'] [data-widget='price'] span"
_TITLE_SELECTOR = "[data-widget='webProductHeading'] h1"


class OzonPlaywrightParser(BaseParser):
    """Headless-браузер парсер Ozon (fallback).

    Запускает Chromium в headless-режиме, открывает страницу товара и
    извлекает цену через CSS-селекторы.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright не установлен. Выполните: pip install playwright && playwright install chromium"
            )
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._pw = None
        self._browser = None

    def __enter__(self) -> "OzonPlaywrightParser":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)
        return self

    def __exit__(self, *_) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _get_page(self, article: str) -> Page:
        page = self._browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        page.goto(
            f"https://www.ozon.ru/product/{article}/",
            timeout=self._timeout_ms,
            wait_until="domcontentloaded",
        )
        return page

    def fetch_product_info(self, article: str) -> ProductInfo:
        price: Decimal | None = None
        title: str | None = None

        page = self._get_page(article)
        try:
            # Ждём появления блока с ценой
            page.wait_for_selector(_PRICE_SELECTOR, timeout=self._timeout_ms)
            raw_price = page.locator(_PRICE_SELECTOR).first.inner_text()
            price = _parse_price_str(raw_price)

            title_el = page.locator(_TITLE_SELECTOR).first
            if title_el.count():
                title = title_el.inner_text().strip()
        except Exception:
            pass
        finally:
            page.close()

        return ProductInfo(price=price, title=title)

    def fetch_price(self, article: str) -> Decimal | None:
        return self.fetch_product_info(article).price
