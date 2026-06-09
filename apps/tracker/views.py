import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserProfile
from .forms import SubscriptionAddForm, SubscriptionEditForm
from .models import PriceHistory, Product, UserSubscription


# --------------------------------------------------------------------------- #
# Authenticated: список подписок
# --------------------------------------------------------------------------- #

@login_required
def product_list(request):
    subscriptions = (
        UserSubscription.objects
        .filter(user=request.user)
        .select_related("product")
        .order_by("-created_at")
    )
    return render(request, "tracker/product_list.html", {"subscriptions": subscriptions})


# --------------------------------------------------------------------------- #
# Authenticated: добавить подписку
# --------------------------------------------------------------------------- #

@login_required
def subscription_add(request):
    if request.method == "POST":
        form = SubscriptionAddForm(request.POST)
        if form.is_valid():
            product, _ = Product.objects.get_or_create(
                marketplace=form.cleaned_data["marketplace"],
                article=form.cleaned_data["article"],
            )
            sub, created = UserSubscription.objects.get_or_create(
                user=request.user,
                product=product,
                defaults={
                    "target_price": form.cleaned_data["target_price"],
                    "notify_on_any_drop": form.cleaned_data["notify_on_any_drop"],
                },
            )
            if not created:
                messages.warning(request, "Вы уже отслеживаете этот товар.")
            else:
                # Немедленный парсинг через Celery — title/цена появятся вскоре
                from apps.tracker.tasks import parse_single_product
                parse_single_product.delay(product.id)
                messages.success(request, "Товар добавлен. Цена будет загружена в ближайшее время.")
            return redirect("tracker:product_list")
    else:
        form = SubscriptionAddForm()
    return render(request, "tracker/subscription_add.html", {"form": form})


# --------------------------------------------------------------------------- #
# Authenticated: редактировать подписку
# --------------------------------------------------------------------------- #

@login_required
def subscription_edit(request, pk: int):
    sub = get_object_or_404(UserSubscription, pk=pk, user=request.user)
    if request.method == "POST":
        form = SubscriptionEditForm(request.POST, instance=sub)
        if form.is_valid():
            form.save()
            messages.success(request, "Подписка обновлена.")
            return redirect("tracker:product_list")
    else:
        form = SubscriptionEditForm(instance=sub)
    return render(request, "tracker/subscription_edit.html", {"form": form, "sub": sub})


# --------------------------------------------------------------------------- #
# Authenticated: удалить подписку
# --------------------------------------------------------------------------- #

@login_required
def subscription_delete(request, pk: int):
    sub = get_object_or_404(UserSubscription, pk=pk, user=request.user)
    if request.method == "POST":
        product_title = sub.product.title or sub.product.article
        sub.delete()
        messages.success(request, f"Подписка на «{product_title}» удалена.")
    return redirect("tracker:product_list")


# --------------------------------------------------------------------------- #
# Публичный дашборд (по токену, без логина)
# --------------------------------------------------------------------------- #

def dashboard(request, token: str):
    profile = get_object_or_404(UserProfile, dashboard_token=token)

    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    subscriptions = (
        UserSubscription.objects
        .filter(user=profile.user)
        .select_related("product")
        .order_by("product__title", "product__article")
    )

    # Для каждого товара собираем данные для Chart.js
    charts: list[dict] = []
    for sub in subscriptions:
        qs = PriceHistory.objects.filter(product=sub.product)
        if date_from:
            qs = qs.filter(parsed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(parsed_at__date__lte=date_to)
        qs = qs.order_by("parsed_at")

        records = list(qs.values("price", "parsed_at"))
        prices = [float(r["price"]) for r in records]
        labels = [r["parsed_at"].strftime("%d.%m %H:%M") for r in records]

        charts.append({
            "sub": sub,
            "product": sub.product,
            "labels_json": json.dumps(labels),
            "prices_json": json.dumps(prices),
            "current": sub.product.current_price,
            "min_price": Decimal(str(min(prices))) if prices else None,
            "max_price": Decimal(str(max(prices))) if prices else None,
            "avg_price": round(Decimal(str(sum(prices) / len(prices))), 2) if prices else None,
            "has_data": bool(prices),
        })

    return render(request, "tracker/dashboard.html", {
        "profile": profile,
        "charts": charts,
        "date_from": date_from,
        "date_to": date_to,
    })


# --------------------------------------------------------------------------- #
# AJAX: данные графика за произвольный период
# --------------------------------------------------------------------------- #

def chart_data_api(request, token: str, product_id: int):
    """Возвращает JSON с историей цен для Chart.js."""
    profile = get_object_or_404(UserProfile, dashboard_token=token)

    # Проверяем, что товар принадлежит этому пользователю
    get_object_or_404(
        UserSubscription, user=profile.user, product_id=product_id
    )

    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    qs = PriceHistory.objects.filter(product_id=product_id).order_by("parsed_at")
    if date_from:
        qs = qs.filter(parsed_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(parsed_at__date__lte=date_to)

    records = list(qs.values("price", "parsed_at"))
    return JsonResponse({
        "labels": [r["parsed_at"].strftime("%d.%m %H:%M") for r in records],
        "prices": [float(r["price"]) for r in records],
    })
