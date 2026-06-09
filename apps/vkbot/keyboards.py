"""Построители JSON-клавиатур для VK Bots API."""
import json


def _kb(buttons: list[list[dict]], one_time: bool = False) -> str:
    return json.dumps({"one_time": one_time, "buttons": buttons}, ensure_ascii=False)


def _btn(label: str, payload: dict, color: str = "secondary") -> dict:
    # VK ограничивает лейбл кнопки 40 символами
    if len(label) > 40:
        label = label[:37] + "..."
    return {
        "action": {
            "type": "text",
            "label": label,
            "payload": json.dumps(payload, ensure_ascii=False),
        },
        "color": color,
    }


# ── Главное меню ──────────────────────────────────────────────────────────────

def main_menu() -> str:
    return _kb([
        [
            _btn("Мои подписки", {"cmd": "subscriptions"}, "primary"),
            _btn("Добавить товар", {"cmd": "add_start"}, "positive"),
        ],
        [
            _btn("Мой дашборд", {"cmd": "dashboard"}, "secondary"),
        ],
    ])


# ── Добавление товара ─────────────────────────────────────────────────────────

def marketplace_select() -> str:
    return _kb([
        [_btn("Wildberries", {"cmd": "add_marketplace", "mp": "WB"}, "negative")],
        [_btn("Отмена", {"cmd": "main_menu"}, "secondary")],
    ], one_time=True)


def price_input() -> str:
    return _kb([
        [
            _btn("Любое снижение", {"cmd": "add_price", "any_drop": True}, "positive"),
            _btn("Без уведомлений", {"cmd": "add_price", "skip": True}, "secondary"),
        ],
        [_btn("Отмена", {"cmd": "main_menu"}, "negative")],
    ], one_time=True)


def cancel_only() -> str:
    return _kb([[_btn("Отмена", {"cmd": "main_menu"}, "negative")]], one_time=True)


# ── Список подписок ───────────────────────────────────────────────────────────

_MAX_SUB_BUTTONS = 9  # VK limit: 10 rows max, последняя — «Главное меню»


def subscription_list(subscriptions) -> str:
    buttons = []
    all_subs = list(subscriptions)
    shown = all_subs[:_MAX_SUB_BUTTONS]
    hidden = max(0, len(all_subs) - _MAX_SUB_BUTTONS)
    for sub in shown:
        p = sub.product
        name = p.title or p.article
        price_part = f" — {p.current_price}₽" if p.current_price else ""
        status = "" if sub.is_active else " ⏸"
        label = f"[{p.marketplace}] {name}{price_part}{status}"
        buttons.append([_btn(label, {"cmd": "sub_detail", "sub_id": sub.id}, "primary")])
    menu_label = f"Главное меню (ещё {hidden})" if hidden else "Главное меню"
    buttons.append([_btn(menu_label, {"cmd": "main_menu"}, "secondary")])
    return _kb(buttons, one_time=True)


# ── Детали подписки ───────────────────────────────────────────────────────────

def subscription_detail(sub_id: int, is_active: bool) -> str:
    toggle_label = "Выключить" if is_active else "Включить"
    toggle_cmd = "sub_deactivate" if is_active else "sub_activate"
    return _kb([
        [
            _btn("Изменить порог", {"cmd": "sub_change_price", "sub_id": sub_id}, "primary"),
            _btn(toggle_label, {"cmd": toggle_cmd, "sub_id": sub_id}, "secondary"),
        ],
        [
            _btn("Удалить", {"cmd": "sub_delete", "sub_id": sub_id}, "negative"),
            _btn("К списку", {"cmd": "subscriptions"}, "secondary"),
        ],
    ], one_time=True)


def change_price_kb() -> str:
    return _kb([
        [_btn("Любое снижение", {"cmd": "change_price_any_drop"}, "positive")],
        [_btn("Отмена", {"cmd": "main_menu"}, "negative")],
    ], one_time=True)
