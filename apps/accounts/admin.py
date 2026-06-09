from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "vk_user_id", "dashboard_token")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("dashboard_token",)
