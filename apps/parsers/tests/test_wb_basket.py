"""Unit-тесты алгоритма basket-хоста — не требуют сети."""
import pytest
from apps.parsers.wb import _basket_host, _basket_card_url


def test_basket_host_small_article():
    # артикул 10_000_000 → vol=100 → basket 01
    assert _basket_host(10_000_000) == "https://basket-01.wbbasket.ru"


def test_basket_host_mid_article():
    # артикул 100_000_000 → vol=1000 → попадает в диапазон (1007, 5)
    assert _basket_host(100_000_000) == "https://basket-05.wbbasket.ru"


def test_basket_host_large_article():
    # артикул 200_000_000 → vol=2000 → попадает в (2045, 13)
    assert _basket_host(200_000_000) == "https://basket-13.wbbasket.ru"


def test_basket_card_url_structure():
    # Проверяем формат URL карточки
    url = _basket_card_url(12345678)
    assert "wbbasket.ru" in url
    assert "/vol123/" in url
    assert "/part12345/" in url
    assert "/12345678/info/ru/card.json" in url
