"""Хранение состояния диалога пользователя в Redis.

Нужно для многошаговых сценариев: добавление товара, изменение порога.
TTL — 10 минут: если пользователь бросил диалог, состояние сбросится само.
"""
import json
import redis
from django.conf import settings

_redis = redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
_TTL = 600


def _key(vk_user_id: int) -> str:
    return f"vkbot:state:{vk_user_id}"


def get(vk_user_id: int) -> dict | None:
    raw = _redis.get(_key(vk_user_id))
    return json.loads(raw) if raw else None


def set(vk_user_id: int, data: dict) -> None:
    _redis.setex(_key(vk_user_id), _TTL, json.dumps(data, ensure_ascii=False))


def clear(vk_user_id: int) -> None:
    _redis.delete(_key(vk_user_id))
