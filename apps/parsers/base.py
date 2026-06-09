from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ProductInfo:
    """Результат одного парсинга карточки товара."""
    price: Decimal | None
    title: str | None


class BaseParser(ABC):
    """Базовый класс для парсеров маркетплейсов.

    Каждый парсер принимает на вход АРТИКУЛ (str), не URL.
    URL генерируется внутри модели Product.
    """

    @abstractmethod
    def fetch_price(self, article: str) -> Decimal | None:
        """Вернуть текущую цену товара или None при ошибке."""
        ...

    @abstractmethod
    def fetch_product_info(self, article: str) -> ProductInfo:
        """Вернуть цену и название товара за один запрос."""
        ...
