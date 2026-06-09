"""Бизнес-логика VK-бота: обработка команд и текстового ввода."""
import json
import logging
import random
from decimal import Decimal, InvalidOperation

import vk_api as vk_module

from . import keyboards, state as st

logger = logging.getLogger(__name__)


# ── VK API ────────────────────────────────────────────────────────────────────

def _get_vk():
    from django.conf import settings
    return vk_module.VkApi(token=settings.VK_COMMUNITY_TOKEN).get_api()


def _send(vk, user_id: int, text: str, keyboard: str | None = None) -> None:
    kwargs: dict = {
        "user_id": user_id,
        "message": text,
        "random_id": random.randint(1, 2 ** 31),
    }
    if keyboard:
        kwargs["keyboard"] = keyboard
    vk.messages.send(**kwargs)


# ── Получение / создание пользователя ────────────────────────────────────────

def _get_or_create_vk_user(vk_user_id: int):
    """Вернуть Django User по VK ID, создав его при первом обращении."""
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    try:
        return UserProfile.objects.select_related("user").get(
            vk_user_id=vk_user_id
        ).user
    except UserProfile.DoesNotExist:
        user = User.objects.create_user(username=f"vk_{vk_user_id}")
        user.profile.vk_user_id = vk_user_id
        user.profile.save(update_fields=["vk_user_id"])
        return user


# ── Точка входа ───────────────────────────────────────────────────────────────

def handle_event(event: dict) -> None:
    """Обработать входящее событие от VK Callback API."""
    event_type = event.get("type")
    if event_type == "message_new":
        _handle_message(event["object"]["message"])


def _handle_message(message: dict) -> None:
    vk = _get_vk()
    user_id: int = message["from_id"]
    text: str = message.get("text", "").strip()

    # Парсим payload кнопки (если нажата кнопка)
    raw_payload = message.get("payload", "")
    payload: dict = {}
    if raw_payload:
        try:
            payload = json.loads(raw_payload)
        except (json.JSONDecodeError, TypeError):
            pass

    if payload.get("cmd"):
        _handle_cmd(vk, user_id, payload)
        return

    # Если есть активное состояние диалога — ждём текстовый ввод
    current = st.get(user_id)
    if current:
        _handle_input(vk, user_id, text, current)
        return

    # Иначе — показываем главное меню
    _show_main_menu(vk, user_id)


# ── Команды от кнопок ─────────────────────────────────────────────────────────

def _handle_cmd(vk, user_id: int, payload: dict) -> None:
    cmd = payload.get("cmd", "")

    match cmd:
        case "main_menu":
            st.clear(user_id)
            _show_main_menu(vk, user_id)

        case "subscriptions":
            st.clear(user_id)
            _show_subscriptions(vk, user_id)

        case "add_start":
            st.clear(user_id)
            _send(vk, user_id, "Выберите маркетплейс:", keyboards.marketplace_select())

        case "add_marketplace":
            mp = payload["mp"]
            st.set(user_id, {"step": "add_article", "marketplace": mp})
            _send(vk, user_id,
                  "Введите артикул товара на Wildberries.\nПример: 529983943",
                  keyboards.cancel_only())

        case "add_price":
            current = st.get(user_id)
            if not current or current.get("step") != "add_price":
                _show_main_menu(vk, user_id)
                return
            any_drop = payload.get("any_drop", False)
            skip = payload.get("skip", False)
            _finish_add(vk, user_id, current,
                        price=None,
                        any_drop=any_drop,
                        no_notify=skip)

        case "dashboard":
            _show_dashboard(vk, user_id)

        case "sub_detail":
            _show_sub_detail(vk, user_id, payload["sub_id"])

        case "sub_activate" | "sub_deactivate":
            _toggle_sub(vk, user_id, payload["sub_id"], activate=(cmd == "sub_activate"))

        case "sub_delete":
            _delete_sub(vk, user_id, payload["sub_id"])

        case "sub_change_price":
            st.set(user_id, {"step": "change_price", "sub_id": payload["sub_id"]})
            _send(vk, user_id,
                  "Введите новый порог цены в рублях.\n"
                  "Когда цена упадёт ниже — пришлю уведомление.\n"
                  "Или нажмите «Любое снижение»:",
                  keyboards.change_price_kb())

        case "change_price_any_drop":
            current = st.get(user_id)
            if not current or current.get("step") != "change_price":
                _show_main_menu(vk, user_id)
                return
            _update_price(vk, user_id, current["sub_id"], price=None, any_drop=True)

        case _:
            _show_main_menu(vk, user_id)


# ── Текстовый ввод (многошаговые сценарии) ────────────────────────────────────

def _handle_input(vk, user_id: int, text: str, current: dict) -> None:
    step = current.get("step")

    if step == "add_article":
        if not text.isdigit():
            _send(vk, user_id,
                  "Артикул должен содержать только цифры. Попробуйте ещё раз:",
                  keyboards.cancel_only())
            return
        mp = current["marketplace"]
        st.set(user_id, {"step": "add_price", "marketplace": mp, "article": text})
        _send(vk, user_id,
              f"Артикул {text} принят.\n\n"
              f"Введите порог цены в рублях — уведомлю, когда цена упадёт ниже.\n"
              f"Или выберите режим кнопкой:",
              keyboards.price_input())

    elif step == "add_price":
        price = _parse_price(text)
        if price is None:
            _send(vk, user_id,
                  "Введите число, например: 1500 или 1500.50\n"
                  "Или выберите режим кнопкой:",
                  keyboards.price_input())
            return
        _finish_add(vk, user_id, current, price=price, any_drop=False, no_notify=False)

    elif step == "change_price":
        price = _parse_price(text)
        if price is None:
            _send(vk, user_id,
                  "Введите число, например: 1500",
                  keyboards.change_price_kb())
            return
        _update_price(vk, user_id, current["sub_id"], price=price, any_drop=False)

    else:
        st.clear(user_id)
        _show_main_menu(vk, user_id)


# ── Сценарии ──────────────────────────────────────────────────────────────────

def _show_main_menu(vk, user_id: int) -> None:
    _get_or_create_vk_user(user_id)
    _send(vk, user_id, "Привет! Выберите действие:", keyboards.main_menu())


def _show_subscriptions(vk, user_id: int) -> None:
    from apps.tracker.models import UserSubscription

    user = _get_or_create_vk_user(user_id)

    subs = list(
        UserSubscription.objects
        .filter(user=user)
        .select_related("product")
        .order_by("-created_at")
    )
    if not subs:
        _send(vk, user_id,
              "У вас нет отслеживаемых товаров. Добавьте первый!",
              keyboards.main_menu())
        return

    _send(vk, user_id, f"Ваши подписки ({len(subs)}):", keyboards.subscription_list(subs))


def _finish_add(vk, user_id: int, current: dict,
                price: Decimal | None,
                any_drop: bool,
                no_notify: bool) -> None:
    from apps.tracker.models import Product, UserSubscription
    from apps.tracker.tasks import parse_single_product

    user = _get_or_create_vk_user(user_id)

    mp = current["marketplace"]
    article = current["article"]
    product, _ = Product.objects.get_or_create(marketplace=mp, article=article)
    sub, created = UserSubscription.objects.get_or_create(
        user=user,
        product=product,
        defaults={
            "target_price": price,
            "notify_on_any_drop": any_drop and not no_notify,
            "is_active": True,
        },
    )
    st.clear(user_id)

    if not created:
        _send(vk, user_id, "Вы уже отслеживаете этот товар.", keyboards.main_menu())
        return

    parse_single_product.delay(product.id)

    if price:
        notify_str = f"Порог: {price} ₽"
    elif any_drop and not no_notify:
        notify_str = "Уведомлять при любом снижении"
    else:
        notify_str = "Без уведомлений о цене"

    _send(vk, user_id,
          f"Товар добавлен!\n\n"
          f"Маркетплейс: Wildberries\n"
          f"Артикул: {article}\n"
          f"{notify_str}\n\n"
          f"Получаю актуальную цену...",
          keyboards.main_menu())


def _show_sub_detail(vk, user_id: int, sub_id: int) -> None:
    from apps.tracker.models import UserSubscription

    user = _get_or_create_vk_user(user_id)

    try:
        sub = UserSubscription.objects.select_related("product").get(
            id=sub_id, user=user
        )
    except UserSubscription.DoesNotExist:
        _send(vk, user_id, "Подписка не найдена.", keyboards.main_menu())
        return

    p = sub.product
    price_str = f"{p.current_price} ₽" if p.current_price else "неизвестна"
    if sub.target_price:
        thresh = f"{sub.target_price} ₽"
    elif sub.notify_on_any_drop:
        thresh = "любое снижение"
    else:
        thresh = "нет"

    text = (
        f"{p.title or p.article}\n"
        f"Маркетплейс: {p.get_marketplace_display()}\n"
        f"Артикул: {p.article}\n"
        f"Текущая цена: {price_str}\n"
        f"Порог уведомления: {thresh}\n"
        f"Статус: {'Активна' if sub.is_active else 'На паузе'}"
    )
    _send(vk, user_id, text, keyboards.subscription_detail(sub_id, sub.is_active))


def _toggle_sub(vk, user_id: int, sub_id: int, activate: bool) -> None:
    from apps.tracker.models import UserSubscription

    user = _get_or_create_vk_user(user_id)
    try:
        sub = UserSubscription.objects.get(id=sub_id, user=user)
        sub.is_active = activate
        sub.save(update_fields=["is_active"])
        word = "включена" if activate else "выключена"
        _send(vk, user_id, f"Подписка {word}.",
              keyboards.subscription_detail(sub_id, activate))
    except UserSubscription.DoesNotExist:
        _send(vk, user_id, "Подписка не найдена.", keyboards.main_menu())


def _delete_sub(vk, user_id: int, sub_id: int) -> None:
    from apps.tracker.models import UserSubscription

    user = _get_or_create_vk_user(user_id)
    try:
        sub = UserSubscription.objects.select_related("product").get(
            id=sub_id, user=user
        )
        title = sub.product.title or sub.product.article
        sub.delete()
        _send(vk, user_id, f"Подписка на «{title}» удалена.", keyboards.main_menu())
    except UserSubscription.DoesNotExist:
        _send(vk, user_id, "Подписка не найдена.", keyboards.main_menu())


def _show_dashboard(vk, user_id: int) -> None:
    from django.conf import settings

    user = _get_or_create_vk_user(user_id)
    token = user.profile.dashboard_token
    url = f"{settings.SITE_DOMAIN}/dashboard/{token}/"
    _send(vk, user_id, f"Ваш дашборд с графиками цен:\n{url}", keyboards.main_menu())


def _update_price(vk, user_id: int, sub_id: int,
                  price: Decimal | None, any_drop: bool) -> None:
    from apps.tracker.models import UserSubscription

    user = _get_or_create_vk_user(user_id)
    try:
        sub = UserSubscription.objects.get(id=sub_id, user=user)
        sub.target_price = price
        sub.notify_on_any_drop = any_drop
        sub.save(update_fields=["target_price", "notify_on_any_drop"])
        st.clear(user_id)
        if price:
            msg = f"Порог изменён: {price} ₽"
        else:
            msg = "Включено уведомление при любом снижении." if any_drop else "Порог сброшен."
        _send(vk, user_id, msg, keyboards.subscription_detail(sub_id, sub.is_active))
    except UserSubscription.DoesNotExist:
        st.clear(user_id)
        _send(vk, user_id, "Подписка не найдена.", keyboards.main_menu())


# ── Хелперы ───────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ".").strip())
    except InvalidOperation:
        return None
