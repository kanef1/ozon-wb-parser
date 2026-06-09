"""Unit-тесты парсинга цены и widget-состояний Ozon — без сети."""
import json
from decimal import Decimal

import pytest

from apps.parsers.ozon import (
    _parse_price_str,
    _extract_from_widget_states,
    _extract_price_from_widget,
)


@pytest.mark.parametrize("raw, expected", [
    ("1 234 ₽", Decimal("1234")),
    ("1 234 ₽", Decimal("1234")),      # неразрывный узкий пробел
    ("12\xa0345,99 ₽", Decimal("12345.99")),      # неразрывный пробел + копейки
    ("999₽", Decimal("999")),
    ("1000", Decimal("1000")),
    ("нет в наличии", None),
    ("", None),
])
def test_parse_price_str(raw, expected):
    assert _parse_price_str(raw) == expected


def test_extract_price_from_widget_variant1():
    data = {"price": {"price": "2 490 ₽", "originalPrice": "3 000 ₽"}}
    assert _extract_price_from_widget(data) == Decimal("2490")


def test_extract_price_from_widget_variant_card_price():
    data = {"price": {"cardPrice": "1 999 ₽"}}
    assert _extract_price_from_widget(data) == Decimal("1999")


def test_extract_from_widget_states_finds_price_and_title():
    sell_widget = json.dumps({
        "price": {"price": "5 990 ₽"},
    })
    heading_widget = json.dumps({"title": "Наушники Sony WH-1000XM5"})

    widget_states = {
        "webSell-99999-default-1": sell_widget,
        "webProductHeading-99999-default-1": heading_widget,
        "someOtherWidget-1": "{}",
    }
    price, title = _extract_from_widget_states(widget_states)
    assert price == Decimal("5990")
    assert title == "Наушники Sony WH-1000XM5"


def test_extract_from_widget_states_empty():
    price, title = _extract_from_widget_states({})
    assert price is None
    assert title is None
