import logging
from decimal import Decimal

from curl_cffi import requests as curl_requests

from .base import BaseParser, ProductInfo

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Алгоритм вычисления basket-хоста
# --------------------------------------------------------------------------- #
# WB делит артикулы на "тома" (vol = article // 100_000).
# Каждый том обслуживается одним basket-сервером.
# Пары (максимальный_vol_включительно, номер_basket) зафиксированы ниже.
# Для артикулов, вышедших за последнюю запись таблицы, basket продолжает
# расти с шагом 216 томов на один сервер (эмпирическое наблюдение).
# --------------------------------------------------------------------------- #
_BASKET_THRESHOLDS: list[tuple[int, int]] = [
    (143, 1),   (287, 2),   (431, 3),   (719, 4),   (1007, 5),
    (1061, 6),  (1115, 7),  (1169, 8),  (1313, 9),  (1601, 10),
    (1655, 11), (1919, 12), (2045, 13), (2189, 14), (2405, 15),
    (2621, 16), (2837, 17), (3053, 18), (3269, 19), (3485, 20),
    (3701, 21), (3917, 22), (4133, 23), (4349, 24),
]
_LAST_VOL, _LAST_BASKET = _BASKET_THRESHOLDS[-1]
# Эмпирический шаг для артикулов за пределами таблицы (проверено на реальных данных)
_STEP = 296


def _basket_host(article_id: int) -> str:
    """Вернуть URL basket-хоста для заданного артикула WB."""
    vol = article_id // 100_000
    for threshold, basket_num in _BASKET_THRESHOLDS:
        if vol <= threshold:
            return f"https://basket-{basket_num:02d}.wbbasket.ru"
    # Для артикулов за пределами таблицы: basket = 25 + floor((vol - 4350) / 296)
    extra = (vol - (_LAST_VOL + 1)) // _STEP
    return f"https://basket-{_LAST_BASKET + 1 + extra:02d}.wbbasket.ru"


def _basket_urls(article_id: int) -> tuple[str, str]:
    """Вернуть (card_url, price_history_url) для basket-сервера."""
    host = _basket_host(article_id)
    vol = article_id // 100_000
    part = article_id // 1_000
    base = f"{host}/vol{vol}/part{part}/{article_id}/info"
    return f"{base}/ru/card.json", f"{base}/price-history.json"


# --------------------------------------------------------------------------- #
# Парсер
# --------------------------------------------------------------------------- #

_CARD_API_URL = "https://card.wb.ru/cards/v2/detail"

_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Origin": "https://www.wildberries.ru",
}


class WildberriesParser(BaseParser):
    """Парсер цен Wildberries.

    Основной путь: card.wb.ru/cards/v2/detail (официальный JSON-эндпоинт).
    Fallback: basket-NN.wbbasket.ru — прямой запрос к CDN-карточке.
    """

    def __init__(self, timeout: float = 15.0) -> None:
        from django.conf import settings
        self._client = curl_requests.Session(impersonate="chrome124")
        self._client.headers.update(_HEADERS)
        if settings.WB_PROXY_URL:
            self._client.proxies = {"http": settings.WB_PROXY_URL, "https": settings.WB_PROXY_URL}
        self._timeout = timeout
        self._warmed_up = False

    def _warm_up(self) -> None:
        if self._warmed_up:
            return
        try:
            self._client.get("https://www.wildberries.ru/", timeout=self._timeout)
            self._warmed_up = True
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Основной эндпоинт
    # ------------------------------------------------------------------ #

    def _fetch_via_card_api(self, article: str) -> dict | None:
        """Запрос к card.wb.ru. Возвращает dict продукта или None."""
        params = {
            "appType": "1",
            "curr": "rub",
            # dest=-1257786 соответствует Москве; влияет на финальную цену
            "dest": "-1257786",
            "nm": article,
        }
        self._warm_up()
        referer = f"https://www.wildberries.ru/catalog/{article}/detail.aspx"
        try:
            resp = self._client.get(
                _CARD_API_URL,
                params=params,
                headers={"Referer": referer},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            products = resp.json().get("data", {}).get("products", [])
            return products[0] if products else None
        except Exception as exc:
            logger.warning("WB card.wb.ru error for article=%s: %s", article, exc)
            return None

    # ------------------------------------------------------------------ #
    # Fallback: basket CDN
    # ------------------------------------------------------------------ #

    def _fetch_via_basket(self, article: str) -> tuple[dict | None, list | None]:
        """Запросить price-history.json и card.json с basket CDN.

        Формула вычисления basket-номера не всегда точна для новых артикулов,
        поэтому пробуем расчётный basket и ±2 вокруг него.
        """
        try:
            article_id = int(article)
        except ValueError:
            return None, None

        vol = article_id // 100_000
        part = article_id // 1_000
        _, est_price_url = _basket_urls(article_id)
        # Извлекаем расчётный номер basket из URL
        est_basket = int(est_price_url.split("basket-")[1].split(".")[0])

        for basket in [est_basket, est_basket - 1, est_basket + 1,
                       est_basket - 2, est_basket + 2]:
            if basket < 1:
                continue
            host = f"https://basket-{basket:02d}.wbbasket.ru"
            base = f"{host}/vol{vol}/part{part}/{article_id}/info"
            try:
                r = self._client.get(f"{base}/price-history.json", timeout=5)
                if r.status_code != 200:
                    continue
                price_history = r.json()
                card_data = None
                try:
                    rc = self._client.get(f"{base}/ru/card.json", timeout=5)
                    if rc.status_code == 200:
                        card_data = rc.json()
                except Exception:
                    pass
                return card_data, price_history
            except Exception as exc:
                logger.debug("WB basket-%02d error for article=%s: %s", basket, article, exc)

        logger.warning("WB basket fallback error for article=%s: basket not found", article)
        return None, None

    # ------------------------------------------------------------------ #
    # Извлечение цены из каждого источника
    # ------------------------------------------------------------------ #

    @staticmethod
    def _price_from_card_api(product: dict) -> Decimal | None:
        # salePriceU — цена в копейках (price * 100)
        price_u = product.get("salePriceU")
        if price_u is None:
            return None
        return Decimal(price_u) / Decimal(100)

    @staticmethod
    def _price_from_history(history: list) -> Decimal | None:
        # price-history.json: список {"dt": unix_ts, "price": {"RUB": kopecks}}
        # Последний элемент — самая свежая цена. Значение в копейках (÷100).
        if not history:
            return None
        last = history[-1]
        raw = last.get("price", {}).get("RUB")
        if raw is None:
            return None
        return Decimal(raw) / Decimal(100)

    # ------------------------------------------------------------------ #
    # Публичный интерфейс
    # ------------------------------------------------------------------ #

    def fetch_product_info(self, article: str) -> ProductInfo:
        """Получить цену и название товара WB по артикулу."""
        product = self._fetch_via_card_api(article)
        if product is not None:
            return ProductInfo(
                price=self._price_from_card_api(product),
                title=product.get("name"),
            )

        # Fallback на basket CDN
        card_data, price_history = self._fetch_via_basket(article)
        title = card_data.get("imt_name") if card_data else None
        price = self._price_from_history(price_history) if price_history else None
        if title or price:
            return ProductInfo(price=price, title=title)

        return ProductInfo(price=None, title=None)

    def fetch_price(self, article: str) -> Decimal | None:
        return self.fetch_product_info(article).price

    def __enter__(self) -> "WildberriesParser":
        return self

    def __exit__(self, *_) -> None:
        self._client.__exit__(None, None, None)
