import json
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import UserProfile
from .models import PriceHistory, UserSubscription


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


def chart_data_api(request, token: str, product_id: int):
    profile = get_object_or_404(UserProfile, dashboard_token=token)

    get_object_or_404(UserSubscription, user=profile.user, product_id=product_id)

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
