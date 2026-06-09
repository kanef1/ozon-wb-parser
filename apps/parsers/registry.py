from .base import BaseParser
from .wb import WildberriesParser

_PARSERS: dict[str, type[BaseParser]] = {
    "WB": WildberriesParser,
}


def get_parser(marketplace: str) -> BaseParser:
    """Вернуть экземпляр парсера по коду маркетплейса."""
    cls = _PARSERS.get(marketplace.upper())
    if cls is None:
        raise ValueError(f"Unknown marketplace: {marketplace!r}")
    return cls()
