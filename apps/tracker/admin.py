from django.contrib import admin
from .models import Product, UserSubscription, PriceHistory, NotificationLog


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("marketplace", "article", "title", "current_price", "created_at")
    list_filter = ("marketplace",)
    search_fields = ("article", "title")
    readonly_fields = ("product_url", "created_at")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "target_price", "notify_on_any_drop", "is_active")
    list_filter = ("is_active", "notify_on_any_drop")
    search_fields = ("user__username", "product__article")


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "price", "parsed_at")
    list_filter = ("product__marketplace",)
    date_hierarchy = "parsed_at"


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("subscription", "sent_at", "message_preview")
    date_hierarchy = "sent_at"
    readonly_fields = ("sent_at",)
